"""TC-SEC-07 security headers, CORS allow-list and password hashing settings (NFR-03)."""

import importlib

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_security_headers_on_api_responses():
    response = APIClient().get("/api/v1/auth/me")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Referrer-Policy"] == "same-origin"
    csp = response["Content-Security-Policy"]
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp


@pytest.mark.django_db
def test_cors_only_for_allow_listed_origins():
    allowed = APIClient().get("/api/v1/auth/me", HTTP_ORIGIN="http://localhost:5173")
    other = APIClient().get("/api/v1/auth/me", HTTP_ORIGIN="https://evil.example")
    assert allowed["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Access-Control-Allow-Origin" not in other


def test_production_settings_hash_with_argon2_and_require_12_characters():
    prod = importlib.import_module("config.settings")
    assert prod.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")
    minimum = next(v for v in prod.AUTH_PASSWORD_VALIDATORS if v["NAME"].endswith("MinimumLengthValidator"))
    assert minimum["OPTIONS"]["min_length"] == 12
