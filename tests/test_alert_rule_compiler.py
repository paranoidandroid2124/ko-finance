from __future__ import annotations

from alerts.rule_compiler import CompiledRulePlan, compile_trigger, plan_signature


def test_compile_trigger_parses_dsl_components() -> None:
    trigger = {
        "dsl": "news ticker:005930 keyword:'share buyback' entity:(Samsung,LGChem) window:24h sentiment>=0.35",
    }
    plan = compile_trigger(trigger, default_window_minutes=60)
    assert isinstance(plan, CompiledRulePlan)
    assert plan.source == "news"
    assert plan.window_minutes == 24 * 60
    assert plan.tickers == ("005930",)
    assert "share buyback" in plan.keywords
    assert plan.entities == ("Samsung", "LGChem")
    assert plan.min_sentiment == 0.35


def test_compile_trigger_merges_structured_fields() -> None:
    trigger = {
        "type": "filing",
        "tickers": ["035420"],
        "categories": ["IR"],
        "dsl": "filing ticker:005930 keyword:dividend window:2h",
    }
    plan = compile_trigger(trigger, default_window_minutes=30)
    assert plan.source == "filing"
    # Structured ticker preserved and DSL ticker appended.
    assert plan.tickers == ("035420", "005930")
    assert plan.categories == ("IR",)
    assert plan.keywords == ("dividend",)
    assert plan.window_minutes == 120  # 2h -> minutes


def test_plan_signature_changes_when_filters_change() -> None:
    base_trigger = {"type": "news", "tickers": ["0001"]}
    plan_a = compile_trigger(base_trigger, default_window_minutes=15)
    plan_b = compile_trigger(
        {**base_trigger, "dsl": "news ticker:0001 keyword:'merger'"},
        default_window_minutes=15,
    )
    assert plan_signature(plan_a) != plan_signature(plan_b)
