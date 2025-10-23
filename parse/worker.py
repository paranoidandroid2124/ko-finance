from celery.schedules import crontab

from .celery_app import app

app.conf.timezone = "Asia/Seoul"
app.conf.enable_utc = False

app.conf.beat_schedule = {
    "seed-recent-filings-hourly": {
        "task": "m1.seed_recent_filings",
        "schedule": crontab(minute=0),
        "args": (),
        "kwargs": {"days_back": 1},
    },
    "seed-news-hourly": {
        "task": "m2.seed_news_feeds",
        "schedule": crontab(minute=0),
        "args": (),
        "kwargs": {},
    },
    "market-mood-aggregate-15min": {
        "task": "m2.aggregate_news",
        "schedule": crontab(minute="*/15"),
        "args": (),
        "kwargs": {},
    },
    "daily-filing-digest": {
        "task": "m4.send_filing_digest",
        "schedule": crontab(hour=18, minute=0, day_of_week="mon-fri"),
        "args": (),
        "kwargs": {},
    },
}
