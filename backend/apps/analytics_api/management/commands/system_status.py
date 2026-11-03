import json

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count

from apps.accounts.models import User
from apps.common import today
from apps.facilities.models import Facility
from apps.inventory.models import AlertStatus, ForecastRun, StockAlert, StockTransaction
from apps.passport.models import Child


class Command(BaseCommand):
    help = "What the database holds, as JSON: migrations, loaded data, forecasts, alerts, accounts."

    def handle(self, *args, **options):
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        status = {"pending_migrations": len(pending)}
        if not pending:
            run = ForecastRun.objects.order_by("-run_at").first()
            status |= {
                "facilities": Facility.objects.count(),
                "children": Child.objects.count(),
                "stock_transactions": StockTransaction.objects.count(),
                "forecast_source": run.params.get("source") if run else None,
                "forecast_as_of": run.params.get("as_of") if run else None,
                "alerts_active": StockAlert.objects.exclude(status=AlertStatus.RESOLVED).count(),
                "users_by_role": dict(User.objects.values_list("role").annotate(n=Count("id"))),
                "clinical_today": str(today()),
            }
        self.stdout.write(json.dumps(status))
