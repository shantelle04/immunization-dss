"""TC-SEC-05 endpoint x role matrix and TC-SEC-06 cross-facility denial (FR-02, BR-08, doc 10 section 3).

Every API route must appear in MATRIX; a new route without an entry fails test_every_route_is_in_the_matrix.
"""

import pytest
from conftest import client_for
from django.urls import URLPattern, URLResolver, get_resolver

from apps.accounts.models import AuditLog
from apps.passport.models import Child

HCW, FM, SA, ANON = "hcw_a", "fm_a", "sa", "anonymous"
CLINICAL = {HCW, FM}
PUBLIC = "public"

# (route name, method): roles allowed. Everyone else must be refused before any business logic.
MATRIX = {
    ("auth-login", "post"): PUBLIC,
    ("auth-refresh", "post"): PUBLIC,
    ("auth-logout", "post"): {HCW, FM, SA},
    ("auth-me", "get"): {HCW, FM, SA},
    ("children", "get"): CLINICAL,
    ("children", "post"): CLINICAL,
    ("children-search", "get"): CLINICAL,
    ("child-detail", "get"): CLINICAL,
    ("child-immunizations", "get"): CLINICAL,
    ("child-immunizations", "post"): CLINICAL,
    ("schedule", "get"): CLINICAL,
    ("stock-balance", "get"): CLINICAL,
    ("stock-transactions", "get"): CLINICAL,
    ("stock-transactions", "post"): CLINICAL,
    ("defaulters", "get"): CLINICAL,
    ("sessions", "get"): CLINICAL,
    ("sessions", "post"): {FM},
    ("imports", "post"): {FM},
    ("audit", "get"): {FM},
    ("admin-users", "get"): {SA},
    ("admin-users", "post"): {SA},
    ("admin-facilities", "get"): {SA},
}


def _routes(resolver=None, prefix=""):
    resolver = resolver or get_resolver()
    for p in resolver.url_patterns:
        if isinstance(p, URLResolver):
            yield from _routes(p, prefix + str(p.pattern))
        elif isinstance(p, URLPattern) and p.name:
            view = p.callback.view_class
            methods = [m for m in ("get", "post", "put", "patch", "delete") if hasattr(view, m)]
            yield p.name, prefix + str(p.pattern), methods


def test_every_route_is_in_the_matrix():
    routes = {(name, method) for name, _, methods in _routes() for method in methods}
    assert routes == set(MATRIX), f"missing: {routes - set(MATRIX)}; stale: {set(MATRIX) - routes}"


def _url(pattern: str, child: Child) -> str:
    return "/" + pattern.replace("<uuid:pk>", str(child.pk))


CASES = [(name, method, role) for (name, method) in MATRIX for role in (HCW, FM, SA, ANON)]


@pytest.mark.django_db
@pytest.mark.parametrize(("name", "method", "role"), CASES, ids=lambda v: str(v))
def test_role_access(name, method, role, users, child_a):
    pattern = next(p for n, p, _ in _routes() if n == name)
    client = client_for(None if role == ANON else users[role][0])
    response = getattr(client, method)(_url(pattern, child_a), {}, format="json")
    allowed = MATRIX[(name, method)]
    if allowed == PUBLIC:
        assert response.status_code not in (403, 404, 405)
    elif role in allowed:
        assert response.status_code not in (401, 403), f"{role} should reach {name} {method}"
    elif role == ANON:
        assert response.status_code == 401
    else:
        assert response.status_code == 403, f"{role} must be refused on {name} {method}"


@pytest.mark.django_db
def test_lists_never_show_another_facilitys_children(users, child_a):
    hcw_b = client_for(users["hcw_b"][0])
    data = hcw_b.get("/api/v1/children").data
    assert child_a.system_id not in [c["system_id"] for c in data["results"]]


@pytest.mark.django_db
def test_other_facility_record_is_read_only_and_audited(users, child_a, stocked):
    hcw_b = client_for(users["hcw_b"][0])
    found = hcw_b.get("/api/v1/children/search", {"system_id": child_a.system_id}).data
    assert [c["system_id"] for c in found] == [child_a.system_id]
    history = hcw_b.get(f"/api/v1/children/{child_a.pk}/immunizations")
    assert history.status_code == 200 and history.data["read_only"] is True
    write = hcw_b.post(
        f"/api/v1/children/{child_a.pk}/immunizations", {"dose_code": "BCG-1", "given_on": "2025-06-02"}
    )
    assert write.status_code == 403
    assert AuditLog.objects.filter(user=users["hcw_b"][0], cross_facility=True).count() == 2
    assert not child_a.events.exists()


@pytest.mark.django_db
def test_search_needs_an_exact_identifier(users, child_a):
    hcw_b = client_for(users["hcw_b"][0])
    assert hcw_b.get("/api/v1/children/search", {"family_name": "Otieno"}).status_code == 400
    partial = hcw_b.get("/api/v1/children/search", {"system_id": "IMM-TST-A"}).data
    assert partial == []


@pytest.mark.django_db
def test_stock_ledger_is_facility_scoped(users, stocked):
    rows = client_for(users["hcw_b"][0]).get("/api/v1/stock/transactions").data["results"]
    assert rows and all(r["quantity_doses"] == 100 for r in rows)
    balance = client_for(users["hcw_a"][0]).get("/api/v1/stock/balance").data["rows"]
    assert {r["antigen"]: r["balance_doses"] for r in balance}["BCG"] == 100
