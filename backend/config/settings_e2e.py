"""End-to-end test settings: a separate database owned by the test role, so browser tests never touch the
application database or its evidence data."""

import os

from django.core.exceptions import ImproperlyConfigured

from .preflight import TEST_REQUIREMENTS, check_environment, credentials_distinct, format_problems
from .settings import *  # noqa: F403
from .settings import DATABASES

_problems = check_environment(os.environ, TEST_REQUIREMENTS) + credentials_distinct(os.environ)
if _problems:
    raise ImproperlyConfigured(format_problems(_problems))

DATABASES["default"]["NAME"] = os.environ["DB_NAME"] + "_e2e"
DATABASES["default"]["USER"] = os.environ["DB_TEST_USER"]
DATABASES["default"]["PASSWORD"] = os.environ["DB_TEST_PASSWORD"]

# One browser run signs in many times from one address.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"login": "300/min", "refresh": "300/min"}  # noqa: F405
