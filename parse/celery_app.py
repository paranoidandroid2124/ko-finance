from celery import Celery

app = Celery(
    "kfinance",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
    include=["parse.tasks"],
)

app.conf.task_track_started = True
