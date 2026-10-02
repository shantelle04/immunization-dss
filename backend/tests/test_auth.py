"""TC-SEC-03 login, refresh rotation, logout; TC-SEC-04 lockout and throttling (NFR-03, FR-01, FR-41)."""

from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditAction, AuditLog

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


def login(client, username, pw):
    return client.post(LOGIN, {"username": username, "password": pw}, format="json")


@pytest.mark.django_db
def test_login_returns_access_token_and_httponly_refresh_cookie(users):
    user, pw = users["hcw_a"]
    response = login(APIClient(), "hcw_a", pw)
    assert response.status_code == 200
    assert response.data["access"] and response.data["user"]["role"] == "healthcare_worker"
    assert "refresh" not in response.data, "the refresh token must never be readable by JavaScript"
    cookie = response.cookies[settings.REFRESH_COOKIE_NAME]
    assert cookie["httponly"] and cookie["secure"] and cookie["samesite"] == "Strict"
    assert cookie["path"] == settings.REFRESH_COOKIE_PATH
    me = APIClient()
    me.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert me.get(ME).data["username"] == "hcw_a"


@pytest.mark.django_db
def test_wrong_password_and_unknown_user_get_the_same_refusal(users):
    client = APIClient()
    wrong = login(client, "hcw_a", "not-the-password-123")
    unknown = login(client, "nobody", "not-the-password-123")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.data == unknown.data
    failed = AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED)
    assert failed.count() == 2
    assert not failed.filter(entity_id="nobody").exists(), "attempted usernames are not stored"


@pytest.mark.django_db
def test_lockout_after_threshold_blocks_even_the_right_password(users):
    user, pw = users["hcw_a"]
    client = APIClient()
    for _ in range(settings.LOCKOUT_THRESHOLD):
        assert login(client, "hcw_a", "wrong-password-xyz").status_code == 401
    user.refresh_from_db()
    assert user.locked_until and user.locked_until > timezone.now()
    assert login(client, "hcw_a", pw).status_code == 401
    assert AuditLog.objects.filter(user=user, action=AuditAction.LOCKOUT).count() == 1
    user.locked_until = timezone.now() - timedelta(seconds=1)
    user.save()
    assert login(client, "hcw_a", pw).status_code == 200


@pytest.mark.django_db
def test_inactive_user_cannot_log_in(users):
    user, pw = users["hcw_a"]
    user.is_active = False
    user.save()
    assert login(APIClient(), "hcw_a", pw).status_code == 401


@pytest.mark.django_db
def test_login_is_throttled(users):
    client = APIClient()
    codes = [login(client, "nobody", "x" * 12).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


@pytest.mark.django_db
def test_refresh_rotates_and_old_token_cannot_be_reused(users):
    _, pw = users["hcw_a"]
    client = APIClient()
    login(client, "hcw_a", pw)
    old = client.cookies[settings.REFRESH_COOKIE_NAME].value
    first = client.post(REFRESH)
    assert first.status_code == 200 and first.data["access"]
    assert client.cookies[settings.REFRESH_COOKIE_NAME].value != old
    replay = APIClient()
    replay.cookies[settings.REFRESH_COOKIE_NAME] = old
    assert replay.post(REFRESH).status_code == 401


@pytest.mark.django_db
def test_refresh_without_cookie_is_refused():
    assert APIClient().post(REFRESH).status_code == 401


@pytest.mark.django_db
def test_refresh_and_logout_require_the_csrf_token(users):
    _, pw = users["hcw_a"]
    client = APIClient(enforce_csrf_checks=True)
    response = login(client, "hcw_a", pw)
    assert client.post(REFRESH).status_code == 403
    token = client.cookies["csrftoken"].value
    assert client.post(REFRESH, HTTP_X_CSRFTOKEN=token).status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert client.post(LOGOUT).status_code == 403
    assert client.post(LOGOUT, HTTP_X_CSRFTOKEN=token).status_code == 204


@pytest.mark.django_db
def test_logout_revokes_the_refresh_token(users):
    _, pw = users["hcw_a"]
    client = APIClient()
    response = login(client, "hcw_a", pw)
    refresh = client.cookies[settings.REFRESH_COOKIE_NAME].value
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert client.post(LOGOUT).status_code == 204
    replay = APIClient()
    replay.cookies[settings.REFRESH_COOKIE_NAME] = refresh
    assert replay.post(REFRESH).status_code == 401


@pytest.mark.django_db
def test_missing_or_bad_token_is_rejected():
    assert APIClient().get(ME).status_code == 401
    bad = APIClient()
    bad.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
    assert bad.get(ME).status_code == 401
