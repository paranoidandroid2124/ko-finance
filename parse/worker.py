from celery.schedules import crontab

from .celery_app import app

app.conf.beat_schedule = {
    "seed-recent-filings-hourly": {
        "task": "m1.seed_recent_filings",
        "schedule": crontab(minute=0),
        "args": (),
        "kwargs": {"days_back": 1},
    },
    "market-mood-aggregate-15min": {
        "task": "m2.aggregate_news",
        "schedule": crontab(minute="*/15"),
        "args": (),
        "kwargs": {},
    },
}
