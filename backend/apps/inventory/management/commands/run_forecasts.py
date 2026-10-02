import json
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.common import today
from apps.inventory import forecasting
from apps.inventory.models import AlertStatus, StockAlert


class Command(BaseCommand):
    help = (
        "Build the weekly series from the stock ledger, store 4-week forecasts and refresh stock-out alerts. "
        "With --results, imports the files of a Colab training run; without, uses the baselines (D-14, D-13)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--results", type=Path, help="folder with the backtest results of a Colab run")
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        started = time.perf_counter()
        try:
            run = forecasting.run(today(), options["results"], options["seed"])
        except forecasting.ForecastRefused as exc:
            raise CommandError(str(exc)) from exc
        summary = {
            "run_id": run.pk,
            **run.params,
            "data_sha256": run.data_sha256,
            "forecasts": run.forecasts.count(),
            "alerts_active": StockAlert.objects.exclude(status=AlertStatus.RESOLVED).count(),
            "overall": (run.metrics or {}).get("overall", []),
            "seconds": round(time.perf_counter() - started, 1),
        }
        self.stdout.write(json.dumps(summary, indent=2, default=str))
