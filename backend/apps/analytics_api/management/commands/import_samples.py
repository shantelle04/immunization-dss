from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.analytics_api import samples
from apps.facilities.models import Facility


class Command(BaseCommand):
    help = "Write demo upload files for one facility: new valid rows plus planted errors, with an answer key."

    def add_arguments(self, parser):
        parser.add_argument("facility", help="facility code, for example SYN-S01")
        parser.add_argument("--out", type=Path, required=True)

    def handle(self, *args, facility, out, **options):
        try:
            files = samples.build(facility)
        except (Facility.DoesNotExist, ValueError) as exc:
            raise CommandError(str(exc) or f"Unknown facility {facility}.") from exc
        out.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            path = out / f"{facility}_{name}.csv"
            path.write_text(text, encoding="utf-8")
            self.stdout.write(f"wrote {path} ({text.count(chr(10)) - 1} rows)")
