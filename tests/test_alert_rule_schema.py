from __future__ import annotations

from schemas.api.alerts import (
    AlertFrequencySchema,
    AlertRuleCreateRequest,
    AlertRuleUpdateRequest,
    AlertTriggerSchema,
)


def test_create_request_hydrates_trigger_and_frequency_from_legacy_fields() -> None:
    payload = AlertRuleCreateRequest(
        name="My Alert",
        channels=[],
        evaluationIntervalMinutes=15,
        windowMinutes=10,
        cooldownMinutes=5,
        maxTriggersPerDay=7,
    )
    assert payload.trigger is not None
    assert payload.trigger.type == "filing"
    assert payload.frequency is not None
    assert payload.frequency.evaluationIntervalMinutes == 15
    # Window is clamped to evaluation interval minimum.
    assert payload.frequency.windowMinutes == 15
    assert payload.frequency.cooldownMinutes == 5
    assert payload.frequency.maxTriggersPerDay == 7


def test_create_request_respects_new_trigger_and_frequency_payloads() -> None:
    trigger = AlertTriggerSchema(type="news", tickers=["0001"])
    frequency = AlertFrequencySchema(
        evaluationIntervalMinutes=30,
        windowMinutes=90,
        cooldownMinutes=45,
        maxTriggersPerDay=2,
    )
    payload = AlertRuleCreateRequest(
        name="News Alert",
        channels=[],
        trigger=trigger,
        frequency=frequency,
    )
    assert payload.trigger.type == "news"
    assert payload.frequency.windowMinutes == 90


def test_update_request_accepts_new_trigger_and_frequency() -> None:
    update = AlertRuleUpdateRequest(
        trigger=AlertTriggerSchema(type="news", tickers=["005930"]),
        frequency=AlertFrequencySchema(
            evaluationIntervalMinutes=20,
            windowMinutes=60,
            cooldownMinutes=10,
            maxTriggersPerDay=4,
        ),
    )
    data = update.model_dump(exclude_unset=True)
    assert "trigger" in data
    assert "frequency" in data
    assert data["frequency"]["evaluationIntervalMinutes"] == 20
