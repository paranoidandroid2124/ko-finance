import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

sys.modules.setdefault("fitz", types.SimpleNamespace())

import parse.tasks as tasks

signals = [
    SimpleNamespace(
        published_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        sentiment=0.6,
        topics=["AI", "Macro"],
    ),
    SimpleNamespace(
        published_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        sentiment=-0.2,
        topics=["Macro"],
    ),
]

class DummyQuery:
    def __init__(self, model, session):
        self.model = model
        self.session = session

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        if self.model is tasks.NewsSignal:
            return signals
        return []

    def one_or_none(self):
        if self.model is tasks.NewsObservation:
            return self.session.existing_observation
        return None

class DummySession:
    def __init__(self):
        self.existing_observation = None
        self.added = []

    def query(self, model):
        return DummyQuery(model, self)

    def add(self, obj):
        self.added.append(obj)
        self.existing_observation = obj

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

original_session_local = tasks.SessionLocal
try:
    tasks.SessionLocal = lambda: DummySession()
    result = tasks.aggregate_news_metrics()
    print("aggregate_news_metrics result:\n", result)
finally:
    tasks.SessionLocal = original_session_local
