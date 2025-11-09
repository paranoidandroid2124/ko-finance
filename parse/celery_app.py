from datetime import timedelta

from celery import Celery
from kombu import Queue

from core.env import env_int, env_str

ALERT_EVALUATION_INTERVAL_SECONDS = env_int("ALERT_EVALUATION_INTERVAL_SECONDS", 60, minimum=15)
ALERT_EVALUATION_TASK_TIMEOUT = env_int("ALERT_EVALUATION_TASK_TIMEOUT", 55, minimum=15)
ALERT_EVALUATION_LIMIT = env_int("ALERT_EVALUATION_LIMIT", 200, minimum=1)
CELERY_TIMEZONE = env_str("CELERY_TIMEZONE", "Asia/Seoul") or "UTC"
CELERY_DEFAULT_QUEUE = env_str("CELERY_DEFAULT_QUEUE", "default") or "default"
CELERY_DIGEST_QUEUE = env_str("CELERY_DIGEST_QUEUE", "digest_llm") or "digest_llm"

app = Celery(
    "kfinance",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
    include=["parse.tasks"],
)

app.conf.update(
    task_track_started=True,
    timezone=CELERY_TIMEZONE,
    task_default_queue=CELERY_DEFAULT_QUEUE,
    task_queues=(
        Queue(CELERY_DEFAULT_QUEUE),
        Queue(CELERY_DIGEST_QUEUE),
    ),
    task_routes={
        "m4.send_filing_digest": {"queue": CELERY_DIGEST_QUEUE},
    },
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
