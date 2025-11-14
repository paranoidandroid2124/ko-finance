from datetime import timedelta

from celery import Celery
from kombu import Queue

from core.env import env_int, env_str
from services.schedule_loader import as_celery_schedule, load_schedule_config

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
    beat_schedule={},
)

yaml_timezone, yaml_entries, _ = load_schedule_config()
schedule_from_yaml = as_celery_schedule(yaml_entries) if yaml_entries else {}
alerts_entry = schedule_from_yaml.get("alerts-evaluate-rules")
if alerts_entry is None:
    schedule_from_yaml["alerts-evaluate-rules"] = {
        "task": "alerts.evaluate_rules",
        "schedule": timedelta(seconds=ALERT_EVALUATION_INTERVAL_SECONDS),
        "args": [],
        "kwargs": {"limit": ALERT_EVALUATION_LIMIT},
        "options": {
            "time_limit": ALERT_EVALUATION_TASK_TIMEOUT,
            "expires": ALERT_EVALUATION_TASK_TIMEOUT,
        },
    }
else:
    kwargs = alerts_entry.setdefault("kwargs", {})
    kwargs.setdefault("limit", ALERT_EVALUATION_LIMIT)
    options = alerts_entry.setdefault("options", {})
    options.setdefault("time_limit", ALERT_EVALUATION_TASK_TIMEOUT)
    options.setdefault("expires", ALERT_EVALUATION_TASK_TIMEOUT)

if schedule_from_yaml:
    app.conf.beat_schedule.update(schedule_from_yaml)
if yaml_timezone:
    app.conf.timezone = yaml_timezone
app.conf.enable_utc = (app.conf.timezone or "UTC").upper() == "UTC"
