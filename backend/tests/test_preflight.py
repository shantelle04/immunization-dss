"""TC-SEC-01: Django refuses to start on a missing, short or placeholder secret."""

import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

from config.preflight import APP_REQUIREMENTS, TEST_REQUIREMENTS, check_environment, credentials_distinct

BACKEND_DIR = Path(__file__).resolve().parent.parent
MANAGED_VARS = {r.name for r in APP_REQUIREMENTS + TEST_REQUIREMENTS}


def valid_env() -> dict[str, str]:
    return {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(50),
        "DJANGO_INITIAL_ADMIN_PASSWORD": secrets.token_urlsafe(16),
        "DB_NAME": "immdss",
        "DB_USER": "immdss_app",
        "DB_PASSWORD": secrets.token_urlsafe(24),
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "5433",
        "DB_TEST_USER": "immdss_test",
        "DB_TEST_PASSWORD": secrets.token_urlsafe(24),
    }


def run_check(env_overrides: dict[str, str], tmp_path: Path, settings: str = "config.settings"):
    empty_env_file = tmp_path / "empty.env"
    empty_env_file.write_text("")
    env = {k: v for k, v in os.environ.items() if k not in MANAGED_VARS}
    env.update(env_overrides)
    env["IMMDSS_ENV_FILE"] = str(empty_env_file)
    env["DJANGO_SETTINGS_MODULE"] = settings
    return subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_valid_environment_has_no_problems():
    env = valid_env()
    assert check_environment(env, APP_REQUIREMENTS + TEST_REQUIREMENTS) == []
    assert credentials_distinct(env) == []


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("DJANGO_SECRET_KEY", "", "is not set"),
        ("DJANGO_SECRET_KEY", "x" * 20, "at least 50 characters"),
        ("DJANGO_SECRET_KEY", "changeme-generate-a-real-one" + "x" * 30, "placeholder"),
        ("DJANGO_SECRET_KEY", "ab" * 30, "5 distinct characters"),
        ("DJANGO_INITIAL_ADMIN_PASSWORD", "short", "at least 12 characters"),
        ("DB_PASSWORD", "changeme-generate-a-real-one", "placeholder"),
        ("DB_PASSWORD", "tooshort", "at least 16 characters"),
        ("DB_HOST", "", "is not set"),
    ],
)
def test_bad_value_is_reported(name, value, expected):
    env = valid_env()
    env[name] = value
    problems = check_environment(env, APP_REQUIREMENTS)
    assert len(problems) == 1
    assert name in problems[0] or name == "DJANGO_SECRET_KEY"
    assert expected in problems[0]


def test_problem_messages_never_contain_the_value():
    env = valid_env()
    env["DB_PASSWORD"] = "short-secret-x"
    assert all("short-secret-x" not in p for p in check_environment(env, APP_REQUIREMENTS))


def test_shared_app_and_test_role_is_rejected():
    env = valid_env()
    env["DB_TEST_USER"] = env["DB_USER"]
    assert credentials_distinct(env) == ["DB_USER and DB_TEST_USER must be different roles"]


def test_django_starts_with_valid_environment(tmp_path):
    result = run_check(valid_env(), tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("missing", ["DJANGO_SECRET_KEY", "DB_PASSWORD", "DJANGO_INITIAL_ADMIN_PASSWORD"])
def test_django_refuses_to_start_when_secret_missing(tmp_path, missing):
    env = valid_env()
    del env[missing]
    result = run_check(env, tmp_path)
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert f"{missing} is not set" in result.stderr


def test_django_refuses_to_start_with_short_secret_key(tmp_path):
    env = valid_env()
    env["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(16)
    result = run_check(env, tmp_path)
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be at least 50 characters" in result.stderr


def test_test_settings_refuse_shared_role(tmp_path):
    env = valid_env()
    env["DB_TEST_USER"] = env["DB_USER"]
    result = run_check(env, tmp_path, settings="config.settings_test")
    assert result.returncode != 0
    assert "must be different roles" in result.stderr
