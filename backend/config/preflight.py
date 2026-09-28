"""Startup validation of required settings. Django refuses to start when any check fails."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

PLACEHOLDER_PREFIX = "changeme"


@dataclass(frozen=True)
class Requirement:
    name: str
    min_length: int = 1
    secret: bool = False


APP_REQUIREMENTS = (
    Requirement("DJANGO_SECRET_KEY", min_length=50, secret=True),
    Requirement("DJANGO_INITIAL_ADMIN_PASSWORD", min_length=12, secret=True),
    Requirement("DB_NAME"),
    Requirement("DB_USER"),
    Requirement("DB_PASSWORD", min_length=16, secret=True),
    Requirement("DB_HOST"),
    Requirement("DB_PORT"),
)

TEST_REQUIREMENTS = (
    Requirement("DB_TEST_USER"),
    Requirement("DB_TEST_PASSWORD", min_length=16, secret=True),
)


def check_environment(env: Mapping[str, str], requirements: tuple[Requirement, ...]) -> list[str]:
    problems = []
    for req in requirements:
        value = env.get(req.name, "")
        if not value:
            problems.append(f"{req.name} is not set")
        elif req.secret and value.lower().startswith(PLACEHOLDER_PREFIX):
            problems.append(f"{req.name} is still the .env.example placeholder")
        elif len(value) < req.min_length:
            problems.append(f"{req.name} must be at least {req.min_length} characters")
        elif req.name == "DJANGO_SECRET_KEY" and len(set(value)) < 5:
            problems.append("DJANGO_SECRET_KEY must contain at least 5 distinct characters")
    return problems


def credentials_distinct(env: Mapping[str, str]) -> list[str]:
    if env.get("DB_USER") and env.get("DB_USER") == env.get("DB_TEST_USER"):
        return ["DB_USER and DB_TEST_USER must be different roles"]
    return []


def format_problems(problems: list[str]) -> str:
    return "Refusing to start, fix these settings (see .env.example):\n  - " + "\n  - ".join(problems)
