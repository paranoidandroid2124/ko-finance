from datetime import timedelta

from celery import Celery
from kombu import Queue

from core.env import env_int, env_str
from services.schedule_loader import as_celery_schedule, load_schedule_config

CELERY_TIMEZONE = env_str("CELERY_TIMEZONE", "Asia/Seoul") or "UTC"
CELERY_DEFAULT_QUEUE = env_str("CELERY_DEFAULT_QUEUE", "default") or "default"

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
    task_queues=(Queue(CELERY_DEFAULT_QUEUE),),
    task_routes={},
    beat_schedule={},
)

yaml_timezone, yaml_entries, _ = load_schedule_config()
schedule_from_yaml = as_celery_schedule(yaml_entries) if yaml_entries else {}
if schedule_from_yaml:
    app.conf.beat_schedule.update(schedule_from_yaml)
if yaml_timezone:
    app.conf.update(timezone=yaml_timezone)
current_tz = getattr(app.conf, "timezone", None) or "UTC"
app.conf.enable_utc = str(current_tz).upper() == "UTC"
