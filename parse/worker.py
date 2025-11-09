from celery.schedules import crontab

from .celery_app import app

app.conf.timezone = "Asia/Seoul"
app.conf.enable_utc = False

app.conf.beat_schedule = {
    "seed-recent-filings-hourly": {
        "task": "m1.seed_recent_filings",
        "schedule": crontab(minute=0, day_of_week="mon-fri"),
        "args": (),
        "kwargs": {"days_back": 1},
    },
    "seed-recent-filings-weekend-catchup": {
        "task": "m1.seed_recent_filings",
        "schedule": crontab(hour=7, minute=0, day_of_week="mon"),
        "args": (),
        "kwargs": {"days_back": 3},
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
    "sector-daily-hourly": {
        "task": "m2.aggregate_sector_daily",
        "schedule": crontab(minute=10),
        "args": (),
        "kwargs": {"hours_back": 36},
    },
    "sector-window-hourly": {
        "task": "m2.aggregate_sector_windows",
        "schedule": crontab(minute=20),
        "args": (),
        "kwargs": {},
    },
    "daily-filing-digest": {
        "task": "m4.send_filing_digest",
        "schedule": crontab(hour=18, minute=0, day_of_week="mon-fri"),
        "args": (),
        "kwargs": {"timeframe": "daily"},
    },
    "weekly-filing-digest": {
        "task": "m4.send_filing_digest",
        "schedule": crontab(hour=9, minute=30, day_of_week="mon"),
        "args": (),
        "kwargs": {"timeframe": "weekly"},
    },
    "daily-brief-pdf": {
        "task": "m4.generate_daily_brief",
        "schedule": crontab(hour=7, minute=30, day_of_week="mon-fri"),
        "args": (),
        "kwargs": {},
    },
    "lightmem-longterm-update": {
        "task": "memory.promote_long_term",
        "schedule": crontab(hour=3, minute=15),
        "args": (),
        "kwargs": {},
    },
}
