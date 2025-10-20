import time
import types

from ingest import news_fetcher


class DummyEntry(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def get(self, key, default=None):
        return super().get(key, default)


def test_fetch_news_batch(monkeypatch):
    monkeypatch.setenv("NEWS_FEEDS", "https://example.com/rss")
    monkeypatch.setattr(news_fetcher, "feedparser", object(), raising=False)

    entry = DummyEntry(
        title="Sample Headline",
        link="https://example.com/news/123",
        description="Sample summary content.",
        published_parsed=time.gmtime(0),
    )

    result = types.SimpleNamespace(
        feed={"title": "Sample Feed"},
        entries=[entry],
        bozo=0,
    )

    monkeypatch.setattr(news_fetcher, "_parse_feed_retry", lambda url: result)

    articles = news_fetcher.fetch_news_batch(limit_per_feed=2)
    assert len(articles) == 1
    article = articles[0]
    assert article.headline == "Sample Headline"
    assert article.url == "https://example.com/news/123"
    assert "Sample Headline" in article.original_text


def test_fetch_news_batch_fallback(monkeypatch):
    monkeypatch.delenv("NEWS_FEEDS", raising=False)
    monkeypatch.setattr(news_fetcher, "feedparser", None, raising=False)

    sentinel = object()
    monkeypatch.setattr(news_fetcher, "_load_mock_articles", lambda limit: sentinel)

    result = news_fetcher.fetch_news_batch(limit_per_feed=1, use_mock_fallback=True)
    assert result is sentinel

