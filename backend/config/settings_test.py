"""Test settings: the suite connects with its own role, never the application's credential."""

import os

from django.core.exceptions import ImproperlyConfigured

from .preflight import TEST_REQUIREMENTS, check_environment, credentials_distinct, format_problems
from .settings import *  # noqa: F403
from .settings import DATABASES

_problems = check_environment(os.environ, TEST_REQUIREMENTS) + credentials_distinct(os.environ)
if _problems:
    raise ImproperlyConfigured(format_problems(_problems))

DATABASES["default"]["USER"] = os.environ["DB_TEST_USER"]
DATABASES["default"]["PASSWORD"] = os.environ["DB_TEST_PASSWORD"]

# Speed only: tests hash many throwaway passwords. test_security asserts production uses Argon2 first.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
