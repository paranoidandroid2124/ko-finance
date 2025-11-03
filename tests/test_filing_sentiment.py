import pytest

pytest.importorskip("multipart")

from models.filing import Filing, ANALYSIS_ANALYZED
from models.summary import Summary
from web.routers.filing import _derive_sentiment


def test_summary_sentiment_overrides_category():
    filing = Filing()
    filing.analysis_status = ANALYSIS_ANALYZED
    filing.category = "소송/분쟁"  # normally negative

    summary = Summary(sentiment_label="positive", sentiment_reason="테스트 근거")

    sentiment, reason = _derive_sentiment(filing, summary)

    assert sentiment == "positive"
    assert reason == "테스트 근거"


def test_summary_sentiment_defaults_reason_when_missing():
    filing = Filing()
    filing.analysis_status = ANALYSIS_ANALYZED
    filing.category = "기타"

    summary = Summary(sentiment_label="negative", sentiment_reason=None)

    sentiment, reason = _derive_sentiment(filing, summary)

    assert sentiment == "negative"
    assert reason == "요약 모델이 공시 내용을 검토한 결과예요."
