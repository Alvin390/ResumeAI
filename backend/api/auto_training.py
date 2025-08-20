"""
Automatic background retraining for the ML quality predictor.
Starts a daemon thread that periodically checks for new training data and retrains the
model when thresholds are met.

Environment variables:
- ML_AUTOTRAIN_ENABLED: bool (default: true) - enable/disable auto training
- ML_AUTOTRAIN_INTERVAL_SECONDS: int (default: 1800) - how often to check (30m)
- ML_AUTOTRAIN_MIN_SAMPLES: int (default: 50) - minimum samples required to train
- ML_AUTOTRAIN_MIN_DELTA: int (default: 25) - min new samples since last train
- AI_DRY_RUN: bool (default: true) - if true, skip auto training (don't learn from mock)
"""
from __future__ import annotations

import os
import threading
import time
import logging

from .ml_quality_predictor import quality_collector, retrain_quality_model

logger = logging.getLogger(__name__)

_started_lock = threading.Lock()
_started = False
_last_trained_count = 0


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _auto_train_loop():
    global _last_trained_count

    interval = int(os.environ.get("ML_AUTOTRAIN_INTERVAL_SECONDS", "1800"))
    min_samples = int(os.environ.get("ML_AUTOTRAIN_MIN_SAMPLES", "50"))
    min_delta = int(os.environ.get("ML_AUTOTRAIN_MIN_DELTA", "25"))

    logger.info(
        "ML auto-training scheduler started (interval=%ss, min_samples=%s, min_delta=%s)",
        interval, min_samples, min_delta,
    )

    while True:
        try:
            # Skip if configured to dry-run (we don't want to train on mock data)
            if _bool_env("AI_DRY_RUN", True):
                time.sleep(interval)
                continue

            current_count = len(quality_collector.training_data)
            # Check thresholds
            if current_count >= min_samples and (current_count - _last_trained_count) >= min_delta:
                logger.info(
                    "Attempting ML quality model retrain (samples=%s, last_trained_count=%s)",
                    current_count, _last_trained_count,
                )
                ok = retrain_quality_model()
                if ok:
                    _last_trained_count = current_count
                    logger.info("ML quality model retrained successfully; trained_count=%s", _last_trained_count)
                else:
                    logger.info("Retrain skipped (insufficient data)")
        except Exception as e:
            logger.warning("Auto-training loop error: %s", e)
        finally:
            time.sleep(interval)


def start_auto_training_if_enabled():
    global _started
    if not _bool_env("ML_AUTOTRAIN_ENABLED", True):
        logger.info("ML auto-training disabled via env")
        return

    with _started_lock:
        if _started:
            return
        thread = threading.Thread(target=_auto_train_loop, name="ml-auto-train", daemon=True)
        thread.start()
        _started = True
        logger.info("ML auto-training thread started")
