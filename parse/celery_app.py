from datetime import timedelta

from celery import Celery

from core.env import env_int, env_str

ALERT_EVALUATION_INTERVAL_SECONDS = env_int("ALERT_EVALUATION_INTERVAL_SECONDS", 60, minimum=15)
ALERT_EVALUATION_TASK_TIMEOUT = env_int("ALERT_EVALUATION_TASK_TIMEOUT", 55, minimum=15)
ALERT_EVALUATION_LIMIT = env_int("ALERT_EVALUATION_LIMIT", 200, minimum=1)
CELERY_TIMEZONE = env_str("CELERY_TIMEZONE", "Asia/Seoul") or "UTC"

app = Celery(
    "kfinance",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
    include=["parse.tasks"],
)

app.conf.update(
    task_track_started=True,
    timezone=CELERY_TIMEZONE,
    beat_schedule={
        "alerts-evaluate-rules": {
            "task": "alerts.evaluate_rules",
            "schedule": timedelta(seconds=ALERT_EVALUATION_INTERVAL_SECONDS),
            "options": {
                "time_limit": ALERT_EVALUATION_TASK_TIMEOUT,
                "expires": ALERT_EVALUATION_TASK_TIMEOUT,
            },
            "kwargs": {"limit": ALERT_EVALUATION_LIMIT},
        },
    },
)
