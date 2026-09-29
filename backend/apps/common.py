from datetime import date

from django.conf import settings
from django.db import models


class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def today() -> date:
    """The clinical 'today'. IMMDSS_TODAY pins it to the synthetic dataset's as-of date for demos (D-32)."""
    return date.fromisoformat(settings.IMMDSS_TODAY) if settings.IMMDSS_TODAY else date.today()
