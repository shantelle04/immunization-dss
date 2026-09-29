from django.urls import include, path

from apps.accounts import views as accounts
from apps.analytics_api import views as analytics
from apps.facilities import views as facilities
from apps.inventory import views as inventory
from apps.passport import views as passport
from apps.scheduling import views as scheduling

api = [
    path("auth/login", accounts.LoginView.as_view(), name="auth-login"),
    path("auth/refresh", accounts.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", accounts.LogoutView.as_view(), name="auth-logout"),
    path("auth/me", accounts.MeView.as_view(), name="auth-me"),
    path("children", passport.ChildListView.as_view(), name="children"),
    path("children/search", passport.ChildSearchView.as_view(), name="children-search"),
    path("children/<uuid:pk>", passport.ChildDetailView.as_view(), name="child-detail"),
    path(
        "children/<uuid:pk>/immunizations",
        passport.ChildImmunizationsView.as_view(),
        name="child-immunizations",
    ),
    path("schedule", passport.ScheduleView.as_view(), name="schedule"),
    path("stock/balance", inventory.BalanceView.as_view(), name="stock-balance"),
    path("stock/transactions", inventory.TransactionListView.as_view(), name="stock-transactions"),
    path("defaulters", scheduling.DefaulterListView.as_view(), name="defaulters"),
    path("sessions", scheduling.SessionListView.as_view(), name="sessions"),
    path("imports", analytics.ImportView.as_view(), name="imports"),
    path("audit", accounts.AuditListView.as_view(), name="audit"),
    path("admin/users", accounts.UserAdminListView.as_view(), name="admin-users"),
    path("admin/facilities", facilities.FacilityAdminListView.as_view(), name="admin-facilities"),
]

urlpatterns = [path("api/v1/", include(api))]
