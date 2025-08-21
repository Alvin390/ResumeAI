import os
import sys
from celery import Celery

# Ensure Django settings are set
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "resumeai.settings")

# Optionally enable gevent monkey patching for cooperative I/O when using gevent pool
_pool = os.getenv("CELERY_POOL", "").strip().lower()
_gevent_flag = os.getenv("GEVENT_MONKEYPATCH", "False").strip().lower() in {"1", "true", "yes", "on"}
_is_worker = os.getenv("IS_CELERY_WORKER", "").strip().lower() in {"1", "true", "yes", "on"} or (sys.argv and "celery" in (sys.argv[0] or ""))
if _is_worker and (_pool == "gevent" or (_gevent_flag and _pool != "prefork")):
    try:
        from gevent import monkey  # type: ignore

        monkey.patch_all()
    except Exception as _e:  # pragma: no cover
        # Do not crash if gevent is not installed; just warn.
        print(f"[celery] gevent monkey patch requested but unavailable: {_e}")

app = Celery("resumeai")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
