"""TC-D guard: application code never reads truth/ (doc 10 section 2); only evaluation/ may, with no URL."""

from pathlib import Path

from django.conf import settings

APPS = Path(__file__).resolve().parents[1] / "apps"
REFUSALS = ("never", "Refusing", '"truth" in')


def test_application_code_mentions_truth_only_to_refuse_it():
    offenders = [
        f"{path.relative_to(APPS)}: {line.strip()}"
        for path in APPS.rglob("*.py")
        for line in path.read_text().splitlines()
        if "truth" in line and not any(r in line for r in REFUSALS)
    ]
    assert offenders == []


def test_evaluation_package_is_not_an_installed_app():
    assert not any(app.startswith("evaluation") for app in settings.INSTALLED_APPS)
