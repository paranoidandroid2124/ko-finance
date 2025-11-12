from types import SimpleNamespace

import pytest

from services.event_extractor import extract_event_attributes, get_event_rule_metadata


def _filing(title: str, body: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        report_name=None,
        title=title,
        raw_md=body,
        notes=None,
    )


@pytest.mark.parametrize(
    "title,body,expected_type,expected_domain,expected_subtype",
    [
        ("제3자배정 방식의 유상증자 결정(정정)", "제3자배정 유상증자 정정 공시", "SEO", "FIN", None),
        ("대표이사 사임 및 신임 선임의 건", "대표이사 사임 및 신규 선임", "GOV", "GOV", "ceo_change"),
        ("환경사고 관련 보고 및 개선명령 수령", "환경 사고 발생 및 개선명령 수령", "ESG", "ESG", "incident"),
        ("장기공급계약 해지의 건", "장기공급 계약 해지 통보", "CONTRACT_TERMINATION", "FIN", None),
        ("주권매매거래정지(실질심사 사유발생)", "실질심사 대상 지정 안내", "MARKET", "MARKET", "trading_halt"),
    ],
)
def test_event_extraction_domains(title, body, expected_type, expected_domain, expected_subtype):
    attrs = extract_event_attributes(_filing(title, body))
    assert attrs.event_type == expected_type
    assert attrs.domain == expected_domain or attrs.domain is None
    if expected_subtype:
        assert attrs.subtype == expected_subtype

    rule_meta = get_event_rule_metadata(expected_type)
    if rule_meta:
        assert rule_meta["domain"] == expected_domain


def test_restatement_modifier_and_method_override():
    attrs = extract_event_attributes(_filing("제3자배정 방식의 유상증자 결정(정정)", "제3자배정 유증 정정"))
    assert attrs.event_type == "SEO"
    assert attrs.is_restatement
    assert attrs.method == "private"
