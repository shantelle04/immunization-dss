"""The Django models match docs/diagrams/schema.yaml, the source of F-ERD, F-LDS and the data dictionary."""

import re
from pathlib import Path

import pytest
import yaml
from django.apps import apps
from django.db import connection

SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "diagrams" / "schema.yaml"
TIMESTAMPS = {"created_at", "updated_at"}


def spec() -> dict:
    return yaml.safe_load(SCHEMA.read_text())


def tables():
    for app_label, app_tables in spec()["apps"].items():
        for name, table in app_tables.items():
            yield app_label, name, table


def normalise(db_type: str) -> str:
    db_type = db_type.replace("timestamp with time zone", "timestamptz")
    return re.sub(r",\s+", ",", db_type)


@pytest.mark.parametrize(
    ("app_label", "name", "table"), list(tables()), ids=lambda v: v if isinstance(v, str) else ""
)
def test_model_matches_schema(app_label, name, table):
    model = apps.get_model(app_label, name)
    assert model._meta.db_table == f"{app_label}_{name}"
    fields = {f.column: f for f in model._meta.concrete_fields}
    expected = {col[0] for col in table["columns"]} | TIMESTAMPS
    assert set(fields) == expected, f"columns differ: {sorted(set(fields) ^ expected)}"
    for column, db_type, flags, _source in table["columns"]:
        field = fields[column]
        flags = str(flags)
        assert normalise(field.db_type(connection)) == db_type.replace(" ", ""), f"{name}.{column} type"
        assert field.null == (" NULL" in f" {flags}".replace("NOT NULL", "")), f"{name}.{column} nullability"
        if flags.startswith("UK"):
            assert field.unique, f"{name}.{column} should be unique"
        if flags.startswith("PK"):
            assert field.primary_key, f"{name}.{column} should be the primary key"
    composite = {
        tuple(model._meta.get_field(f).column for f in c.fields)
        for c in model._meta.constraints
        if getattr(c, "fields", None) and len(c.fields) > 1
    }
    for group in table.get("unique", []):
        assert tuple(group) in composite, f"{name}: missing UNIQUE {group}"


def test_every_project_model_is_in_the_schema():
    documented = {(a, n) for a, n, _ in tables()}
    project = {
        (m._meta.app_label, m._meta.model_name) for m in apps.get_models() if m.__module__.startswith("apps.")
    }
    assert project == documented


@pytest.mark.django_db
def test_views_exist():
    with connection.cursor() as cursor:
        cursor.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'public'")
        views = {row[0] for row in cursor.fetchall()}
    assert set(spec()["views"]) <= views
