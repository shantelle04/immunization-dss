"""D-14: model fitting runs on Google Colab only, never on the development laptop."""

from __future__ import annotations

import importlib.util
import os


class TrainingRefused(RuntimeError):
    pass


def on_training_host() -> bool:
    if os.environ.get("IMMDSS_ALLOW_TRAINING") == "1":
        return True
    try:
        return importlib.util.find_spec("google.colab") is not None
    except ModuleNotFoundError:  # no "google" package at all: certainly not Colab
        return False


def require_training_host(what: str) -> None:
    if not on_training_host():
        raise TrainingRefused(
            f"{what} fits models and runs only on Google Colab (D-14). Open "
            "notebooks/immdss_colab_pipeline.ipynb in Colab, or set IMMDSS_ALLOW_TRAINING=1 "
            "on another approved GPU host."
        )
