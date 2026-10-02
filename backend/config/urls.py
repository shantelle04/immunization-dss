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
    path("children/<uuid:pk>/fhir", passport.ChildFhirView.as_view(), name="child-fhir"),
    path("schedule", passport.ScheduleView.as_view(), name="schedule"),
    path("dashboard", scheduling.DashboardView.as_view(), name="dashboard"),
    path("stock/balance", inventory.BalanceView.as_view(), name="stock-balance"),
    path("stock/transactions", inventory.TransactionListView.as_view(), name="stock-transactions"),
    path("stock/policies", inventory.PolicyListView.as_view(), name="stock-policies"),
    path("stock/policies/<str:code>", inventory.PolicyDetailView.as_view(), name="stock-policy"),
    path("forecasts", inventory.ForecastView.as_view(), name="forecasts"),
    path("alerts", inventory.AlertListView.as_view(), name="alerts"),
    path("alerts/<int:pk>/acknowledge", inventory.AlertAcknowledgeView.as_view(), name="alert-acknowledge"),
    path("defaulters", scheduling.DefaulterListView.as_view(), name="defaulters"),
    path("sessions", scheduling.SessionListView.as_view(), name="sessions"),
    path("sessions/<int:pk>", scheduling.SessionDetailView.as_view(), name="session-detail"),
    path("sessions/<int:pk>/plan", scheduling.SessionPlanView.as_view(), name="session-plan"),
    path(
        "sessions/<int:pk>/attendance", scheduling.SessionAttendanceView.as_view(), name="session-attendance"
    ),
    path("imports", analytics.ImportView.as_view(), name="imports"),
    path("audit", accounts.AuditListView.as_view(), name="audit"),
    path("admin/overview", accounts.AdminOverviewView.as_view(), name="admin-overview"),
    path("admin/users", accounts.UserAdminListView.as_view(), name="admin-users"),
    path("admin/users/<int:pk>", accounts.UserAdminDetailView.as_view(), name="admin-user"),
    path("admin/facilities", facilities.FacilityAdminListView.as_view(), name="admin-facilities"),
    path("admin/schedule", passport.ScheduleAdminListView.as_view(), name="admin-schedule"),
    path(
        "admin/schedule/<str:dose_code>",
        passport.ScheduleAdminDetailView.as_view(),
        name="admin-schedule-dose",
    ),
]

urlpatterns = [path("api/v1/", include(api))]
