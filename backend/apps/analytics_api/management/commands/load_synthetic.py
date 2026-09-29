from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.analytics_api.loader import LoadRefused, load


class Command(BaseCommand):
    help = "Load a validated synthetic run's app/ folder (never truth/) into the database."

    def add_arguments(self, parser):
        parser.add_argument("run_dir", type=Path)
        parser.add_argument("--replace", action="store_true", help="replace previously loaded synthetic data")

    def handle(self, *args, run_dir: Path, replace: bool, **options):
        try:
            counts = load(run_dir, replace=replace)
        except LoadRefused as exc:
            raise CommandError(str(exc)) from exc
        for name, value in counts.items():
            self.stdout.write(f"{name}: {value}")
