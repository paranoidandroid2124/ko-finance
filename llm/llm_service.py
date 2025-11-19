"""LLM interaction helpers for filings, news analysis, and RAG answers."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, cast

import litellm
from langfuse import Langfuse

from core.env import env_bool
from core.logging import get_logger
from llm import guardrails
from llm.prompts import (
    analyze_news,
    chat_summary,
    daily_brief_trend,
    classify_filing,
    extract_info,
    judge_guard,
    semantic_router,
    rag_qa,
    self_check,
    summarize_report,
    table_aware_rag,
    value_chain_extract,
)
from services import deeplink_service

logger = get_logger(__name__)

DEFAULT_LITELLM_CONFIG = Path(__file__).resolve().parent.parent / "litellm_config.yaml"

if not os.getenv("LITELLM_CONFIG_PATH") and DEFAULT_LITELLM_CONFIG.exists():
    os.environ["LITELLM_CONFIG_PATH"] = str(DEFAULT_LITELLM_CONFIG)


def _apply_litellm_aliases() -> None:
    config_path = os.getenv("LITELLM_CONFIG_PATH")
    if not config_path:
        return
    path = Path(config_path)
    if not path.is_file():
        return
    try:
        import yaml
    except ImportError:
        logger.debug("PyYAML not available; skipping LiteLLM alias load.")
        return
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse LiteLLM config for aliases: %s", exc)
        return
    model_list = config.get("model_list") if isinstance(config, dict) else None
    if not isinstance(model_list, list):
        return
    alias_map: Dict[str, str] = {}
    for entry in model_list:
        if not isinstance(entry, dict):
            continue
        alias = entry.get("model_name")
        params = entry.get("litellm_params")
        if not alias or not isinstance(params, dict):
            continue
        target = params.get("model")
        if isinstance(target, str) and target:
            alias_map.setdefault(alias, target)
    if alias_map:
        litellm.model_alias_map.update(alias_map)


_apply_litellm_aliases()


def _extract_usage_payload(response: Any) -> Optional[Dict[str, int]]:
    """Normalize token usage info from various response shapes."""

    def _normalize(raw: Any) -> Optional[Dict[str, int]]:
        if raw is None:
            return None
        if isinstance(raw, dict):
            data = raw
        else:
            data = {key: getattr(raw, key, None) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
        cleaned = {key: int(value) for key, value in data.items() if isinstance(value, (int, float))}
        return cleaned or None

    usage = getattr(response, "usage", None)
    payload = _normalize(usage)
    if payload:
        return payload
    if hasattr(response, "model_dump"):  # pydantic-style objects
        dumped = response.model_dump()
        if isinstance(dumped, dict):
            return _normalize(dumped.get("usage"))
    if isinstance(response, dict):
        return _normalize(response.get("usage"))
    return None

LANGFUSE_CLIENT: Optional[Any] = None
if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
    try:
        LANGFUSE_CLIENT = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST"),
        )
        logger.info("Langfuse client initialised.")
    except Exception as exc:
        logger.error("Failed to initialise Langfuse client: %s", exc, exc_info=True)
        LANGFUSE_CLIENT = None

CLASSIFICATION_MODEL = os.getenv("LLM_CLASSIFICATION_MODEL", "baseline")
SUMMARY_MODEL = os.getenv("LLM_SUMMARY_MODEL", "baseline")
EXTRACTION_MODEL = os.getenv("LLM_EXTRACTION_MODEL", "baseline")
SELF_CHECK_MODEL = os.getenv("LLM_SELF_CHECK_MODEL", "baseline")
NEWS_ANALYSIS_MODEL = os.getenv("LLM_NEWS_MODEL", "baseline")
RAG_MODEL = os.getenv("LLM_RAG_MODEL", "baseline")
QUALITY_FALLBACK_MODEL = os.getenv("LLM_QUALITY_FALLBACK_MODEL", "fallback_model")
JUDGE_MODEL = os.getenv("LLM_GUARD_JUDGE_MODEL", "judge_model")
ROUTER_MODEL = os.getenv("LLM_ROUTER_MODEL", QUALITY_FALLBACK_MODEL)

RAG_REQUIRE_SNIPPET = env_bool("RAG_REQUIRE_SNIPPET", False)
RAG_LINK_DEEPLINK = env_bool("RAG_LINK_DEEPLINK", False)
MAX_CITATIONS_PER_BUCKET = 5

JUDGE_BLOCK_MESSAGE = guardrails.SAFE_MESSAGE


def set_guardrail_copy(message: Optional[str]) -> None:
    """Update the guardrail fallback copy used by streaming responses."""
    guardrails.update_safe_message(message)
    global JUDGE_BLOCK_MESSAGE
    JUDGE_BLOCK_MESSAGE = guardrails.SAFE_MESSAGE

def _record_langfuse_event(
    model: str,
    messages: List[Dict[str, Any]],
    *,
    response_content: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    if not LANGFUSE_CLIENT:
        return
    try:
        user_input = ""
        if messages:
            last_message = messages[-1].get("content")
            user_input = last_message if isinstance(last_message, str) else json.dumps(last_message, ensure_ascii=False)
        trace = LANGFUSE_CLIENT.trace(name="llm_call", metadata={"model": model})
        trace.generation(
            name="completion",
            model=model,
            input=user_input[:2000],
            output=(response_content or "")[:2000],
            metadata={"error": error} if error else None,
        )
        if error:
            trace.update(status="error")
        LANGFUSE_CLIENT.flush()
    except Exception as exc:
        logger.debug("Langfuse logging skipped: %s", exc, exc_info=True)


def _choice_content(response: Any) -> str:
    """Best-effort extraction of the first choice's message content from litellm responses."""
    try:
        response_any = cast(Any, response)
        choices = getattr(response_any, "choices", None)
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message is None and isinstance(first_choice, Mapping):
                message = first_choice.get("message")
            if message is None:
                return ""
            if isinstance(message, Mapping):
                content = message.get("content")
            else:
                content = getattr(message, "content", None)
            if isinstance(content, str):
                return content
    except Exception:
        pass
    return ""


def _safe_completion(
    model: str,
    messages: List[Dict[str, Any]],
    *,
    response_format: Optional[Dict[str, Any]] = None,
    fallback_model: Optional[str] = None,
) -> Tuple[Optional[Any], Optional[str]]:
    try:
        response = litellm.completion(model=model, messages=messages, response_format=response_format)
        response_content = _choice_content(response)
        _record_langfuse_event(model, messages, response_content=response_content)
        return response, model
    except Exception as primary_err:
        logger.warning("LLM call failed for %s: %s", model, primary_err, exc_info=True)
        _record_langfuse_event(model, messages, error=str(primary_err))

        if fallback_model and fallback_model != model:
            try:
                response = litellm.completion(
                    model=fallback_model,
                    messages=messages,
                    response_format=response_format,
                )
                logger.info("Fallback model %s succeeded after %s failure.", fallback_model, model)
                response_content = _choice_content(response)
                _record_langfuse_event(fallback_model, messages, response_content=response_content)
                return response, fallback_model
            except Exception as fallback_err:
                error_message = (
                    f"Primary model {model} error: {primary_err}; fallback {fallback_model} error: {fallback_err}"
                )
                logger.error(error_message, exc_info=True)
                _record_langfuse_event(fallback_model, messages, error=str(fallback_err))
                return None, error_message

        error_message = f"LLM call failed for model {model}: {primary_err}"
        logger.error(error_message, exc_info=True)
        return None, error_message


def _json_completion(
    model: str,
    messages: List[Dict[str, Any]],
    *,
    fallback_model: Optional[str] = QUALITY_FALLBACK_MODEL,
) -> Dict[str, Any]:
    response, model_used = _safe_completion(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        fallback_model=fallback_model,
    )
    if response is None:
        return {"error": model_used}

    try:
        payload = json.loads(_choice_content(response) or "{}")
        payload["model_used"] = model_used
        return payload
    except Exception as exc:
        logger.error("JSON decode failure: %s", exc, exc_info=True)
        return {"error": f"JSON decode failure: {exc}", "model_used": model_used}


def _run_json_prompt(
    *,
    label: str,
    model: str,
    messages: List[Dict[str, Any]],
    fallback_model: Optional[str] = QUALITY_FALLBACK_MODEL,
    normalizer: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    default_on_error: Optional[Dict[str, Any]] = None,
    log_level: str = "error",
) -> Dict[str, Any]:
    log_method = getattr(logger, log_level, logger.error)
    result = _json_completion(
        model=model,
        messages=messages,
        fallback_model=fallback_model,
    )
    if "error" in result:
        log_method("%s failed: %s", label, result["error"])
        if default_on_error is not None:
            payload = dict(default_on_error)
            payload["error"] = result["error"]
            if result.get("model_used") and "model_used" not in payload:
                payload["model_used"] = result["model_used"]
            return payload
        return result
    if normalizer is None:
        return result
    try:
        normalized = normalizer(result)
    except Exception as exc:
        log_method("%s normalizer failed: %s", label, exc, exc_info=True)
        return {"error": f"normalizer_failed: {exc}", "raw": result}
    if "model_used" not in normalized and result.get("model_used"):
        normalized["model_used"] = result.get("model_used")
    if "error" in normalized:
        log_method("%s validation returned error: %s", label, normalized["error"])
    return normalized


def _format_guard_result(result: Dict[str, Any]) -> Dict[str, Any]:
    decision_raw = str(result.get("decision") or "").strip().lower()
    decision = decision_raw if decision_raw in {"pass", "semi_pass", "block", "unknown"} else "unknown"
    rag_mode_raw = str(result.get("rag_mode") or "").strip().lower()
    rag_mode = rag_mode_raw if rag_mode_raw in {"vector", "optional", "none"} else None
    if decision in {"block", "semi_pass"}:
        rag_mode = "none"
    if rag_mode is None:
        rag_mode = "vector" if decision == "pass" else "none"
    return {
        "decision": decision or "unknown",
        "rag_mode": rag_mode,
        "reason": result.get("reason"),
        "model_used": result.get("model_used"),
    }


def classify_filing_content(raw_md: str) -> Dict[str, Any]:
    snippet = raw_md[:12000]
    messages = classify_filing.get_prompt(snippet)
    return _run_json_prompt(
        label="Filing classification",
        model=CLASSIFICATION_MODEL,
        messages=messages,
    )


_ROUTER_FALLBACK = {
    "intent": "rag_answer",
    "reason": "semantic_router_fallback",
    "confidence": 0.0,
    "tool_call": {"name": "rag.answer", "arguments": {}},
    "ui_container": "inline_card",
    "paywall": "free",
    "requires_context": [],
    "safety": {"block": False, "reason": None, "keywords": []},
    "tickers": [],
    "metadata": {"fallback": True},
}


def route_chat_query(question: str) -> Dict[str, Any]:
    """Invoke the SemanticRouter prompt to classify a query into actions."""

    messages = semantic_router.get_prompt(question)
    return _run_json_prompt(
        label="Semantic router",
        model=ROUTER_MODEL,
        messages=messages,
        default_on_error=dict(_ROUTER_FALLBACK),
        log_level="warning",
    )


def extract_structured_info(raw_md: str) -> Dict[str, Any]:
    snippet = raw_md[:24000]
    messages = extract_info.get_prompt(snippet)
    return _run_json_prompt(
        label="Filing extraction",
        model=EXTRACTION_MODEL,
        messages=messages,
    )


def _normalize_topics(topics: Any) -> Tuple[List[str], List[str]]:
    normalized: List[str] = []
    warnings: List[str] = []

    def _append(value: str) -> None:
        text = value.strip()
        if text and text not in normalized:
            normalized.append(text)

    if topics is None:
        return normalized, warnings

    if isinstance(topics, str):
        for chunk in topics.split(","):
            _append(chunk)
        warnings.append("topics provided as string; normalised to list")
        return normalized, warnings

    if isinstance(topics, list):
        for item in topics:
            if isinstance(item, str):
                _append(item)
            elif isinstance(item, dict):
                label = (
                    item.get("topic")
                    or item.get("label")
                    or item.get("name")
                )
                if label:
                    _append(str(label))
                else:
                    warnings.append("topic dictionary missing topic/label/name")
            else:
                warnings.append(f"unsupported topic type {type(item).__name__}")
        return normalized, warnings

    warnings.append(f"topics provided as {type(topics).__name__}; coerced to list")
    _append(str(topics))
    return normalized, warnings


def _normalize_rationale(rationale: Any) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    if rationale is None:
        return "", warnings

    if isinstance(rationale, str):
        return rationale.strip(), warnings

    if isinstance(rationale, list):
        lines = []
        for item in rationale:
            if isinstance(item, str):
                trimmed = item.strip()
                if trimmed:
                    lines.append(trimmed)
            else:
                warnings.append(f"ignored non-string rationale item ({type(item).__name__})")
        return "\n".join(lines), warnings

    warnings.append(f"rationale provided as {type(rationale).__name__}; coerced to string")
    return str(rationale), warnings


def validate_news_analysis_result(result: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    sanitized: Dict[str, Any] = dict(result)

    sentiment_raw = result.get("sentiment")
    sentiment_value: Optional[float] = None
    if sentiment_raw is None:
        errors.append("sentiment missing")
    else:
        try:
            sentiment_value = float(sentiment_raw)
            if not math.isfinite(sentiment_value):
                raise ValueError("non-finite sentiment")
            if sentiment_value < -1.0 or sentiment_value > 1.0:
                warnings.append("sentiment outside [-1,1]; clamped")
                sentiment_value = max(min(sentiment_value, 1.0), -1.0)
        except Exception:
            errors.append("sentiment not numeric")

    topics_normalized, topic_warnings = _normalize_topics(result.get("topics"))
    warnings.extend(topic_warnings)

    rationale_text, rationale_warnings = _normalize_rationale(result.get("rationale"))
    warnings.extend(rationale_warnings)
    if not rationale_text:
        warnings.append("rationale empty after normalisation")

    if errors:
        logger.error("News analysis validation errors: %s", errors)
        return {"error": "validation_failed", "details": errors, "raw": result}

    sanitized["sentiment"] = sentiment_value
    sanitized["topics"] = topics_normalized
    sanitized["rationale"] = rationale_text
    if warnings:
        sanitized["validation_warnings"] = warnings
    sanitized["validated"] = True
    return sanitized


def analyze_news_article(article_text: str) -> Dict[str, Any]:
    snippet = article_text[:12000]
    messages = analyze_news.get_prompt(snippet)
    validated = _run_json_prompt(
        label="News analysis",
        model=NEWS_ANALYSIS_MODEL,
        messages=messages,
        fallback_model=QUALITY_FALLBACK_MODEL,
        normalizer=validate_news_analysis_result,
    )
    if "error" in validated:
        return validated
    logger.info("News analysis sentiment=%s", validated.get("sentiment"))
    return validated


def extract_value_chain_relations(ticker: str, context_text: str) -> Dict[str, Any]:
    """Extract suppliers/customers/competitors from unstructured text."""

    normalized_context = (context_text or "").strip()
    if not normalized_context:
        return {"suppliers": [], "customers": [], "competitors": []}

    messages = value_chain_extract.get_prompt(ticker, normalized_context)
    fallback = {"suppliers": [], "customers": [], "competitors": []}
    result = _run_json_prompt(
        label="Value chain extraction",
        model=QUALITY_FALLBACK_MODEL,
        messages=messages,
        default_on_error=dict(fallback),
        log_level="warning",
    )
    if not isinstance(result, dict):
        return dict(fallback)

    def _sanitize(entries: Any) -> List[Dict[str, str]]:
        sanitized: List[Dict[str, str]] = []
        if not isinstance(entries, list):
            return sanitized
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            ticker_value = str(entry.get("ticker") or entry.get("symbol") or "").strip()
            label_value = str(entry.get("label") or entry.get("name") or ticker_value or "").strip()
            sanitized.append({"ticker": ticker_value, "label": label_value or ticker_value or ""})
            if len(sanitized) >= 5:
                break
        return sanitized

    return {
        "suppliers": _sanitize(result.get("suppliers")),
        "customers": _sanitize(result.get("customers")),
        "competitors": _sanitize(result.get("competitors")),
    }


def self_check_extracted_info(raw_md: str, candidate_facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    snippet = raw_md[:24000]
    candidate_json = json.dumps(candidate_facts, ensure_ascii=False, indent=2)
    user_prompt = self_check.USER_PROMPT_TEMPLATE.replace("{{FILING_MD_SNIPPET}}", snippet).replace(
        "{{CANDIDATE_JSON}}", candidate_json
    )
    messages = [
        {"role": "system", "content": self_check.SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    return _run_json_prompt(
        label="Self-check verification",
        model=SELF_CHECK_MODEL,
        messages=messages,
    )


def summarize_filing_content(raw_md: str) -> Dict[str, Any]:
    snippet = raw_md[:24000]
    messages = summarize_report.get_prompt(snippet)
    return _run_json_prompt(
        label="Filing summary",
        model=SUMMARY_MODEL,
        messages=messages,
    )


def generate_daily_brief_trend(context: Mapping[str, Any]) -> Dict[str, Any]:
    """Create the headline and summary sentence for the daily brief."""
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    default_headline = str(context.get("date") or "일일 브리프")
    default_payload = {"headline": default_headline, "summary": ""}
    result = _run_json_prompt(
        label="Daily brief trend",
        model=SUMMARY_MODEL,
        messages=daily_brief_trend.get_prompt(context_json),
        fallback_model=QUALITY_FALLBACK_MODEL,
        default_on_error=default_payload,
        log_level="warning",
    )
    headline = str(result.get("headline") or default_headline).strip()
    summary = str(result.get("summary") or result.get("overview") or "").strip()
    normalized = dict(result)
    normalized["headline"] = headline
    normalized["summary"] = summary
    return normalized


def _categorize_context(context_chunks: List[Dict[str, Any]]) -> Dict[str, bool]:
    required = {"page": False, "table": False, "footnote": False}
    for chunk in context_chunks:
        chunk_type = (chunk.get("type") or "").lower()
        if chunk.get("page_number"):
            required["page"] = True
        if chunk_type == "table":
            required["table"] = True
        if chunk_type == "footnote":
            required["footnote"] = True
    return required


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        value = str(value or "")
    return " ".join(value.split())


def _chunk_metadata(chunk: Dict[str, Any]) -> Dict[str, Any]:
    metadata = chunk.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _bucket_for_chunk(chunk: Dict[str, Any]) -> Optional[str]:
    chunk_type = (chunk.get("type") or "").lower()
    if chunk_type == "table":
        return "table"
    if chunk_type == "footnote":
        return "footnote"
    return "page"


def _resolve_page_number(chunk: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[int]:
    page = _coerce_int(chunk.get("page_number"))
    if page is None:
        page = _coerce_int(metadata.get("page_number"))
    return page


def _resolve_offsets(metadata: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    start = (
        _coerce_int(metadata.get("char_start"))
        or _coerce_int(metadata.get("offset_start"))
        or _coerce_int(metadata.get("start"))
    )
    end = (
        _coerce_int(metadata.get("char_end"))
        or _coerce_int(metadata.get("offset_end"))
        or _coerce_int(metadata.get("end"))
    )
    if start is not None and end is not None and end < start:
        return start, None
    return start, end


def _resolve_sentence_hash(chunk: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[str]:
    existing = metadata.get("sentence_hash")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    quote = chunk.get("quote") or chunk.get("content") or metadata.get("quote")
    normalized = _normalize_text(quote or "")
    if not normalized:
        return None
    return hashlib.sha1(normalized.encode("utf-8", errors="ignore")).hexdigest()


def _resolve_document_url(chunk: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[str]:
    for key in ("document_url", "viewer_url", "download_url"):
        value = metadata.get(key) or chunk.get(key)
        if isinstance(value, str) and value.strip():
            return value
    urls = metadata.get("urls") or chunk.get("urls") or {}
    if isinstance(urls, dict):
        for key in ("viewer", "download"):
            candidate = urls.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    return None


def _build_deeplink_url(
    document_url: Optional[str],
    page_number: Optional[int],
    *,
    char_start: Optional[int],
    char_end: Optional[int],
    sentence_hash: Optional[str],
    chunk_id: Optional[str],
    document_id: Optional[str],
    excerpt: Optional[str],
) -> Optional[str]:
    if not (RAG_LINK_DEEPLINK and document_url and page_number):
        return None
    if deeplink_service.is_enabled():
        try:
            token = deeplink_service.issue_token(
                document_url=document_url,
                page_number=page_number,
                char_start=char_start,
                char_end=char_end,
                sentence_hash=sentence_hash,
                chunk_id=chunk_id,
                document_id=document_id,
                excerpt=excerpt,
            )
            return deeplink_service.build_viewer_url(token)
        except deeplink_service.DeeplinkError as exc:
            logger.debug("Failed to issue deeplink token: %s", exc)
    separator = "&" if "#" in document_url else "#"
    return f"{document_url}{separator}page={page_number}"


def _build_citation_label(
    chunk: Dict[str, Any],
    bucket: str,
    metadata: Dict[str, Any],
    order_index: int,
) -> str:
    custom_label = metadata.get("citation_label")
    if isinstance(custom_label, str) and custom_label.strip():
        return custom_label.strip()
    page_number = _resolve_page_number(chunk, metadata)
    if bucket == "page":
        return f"(p.{page_number})" if page_number else f"(page {order_index})"
    if bucket == "table":
        table_index = _coerce_int(metadata.get("table_index") or metadata.get("tableIndex"))
        if table_index:
            return f"(Table {table_index})"
        return f"(Table p.{page_number})" if page_number else f"(Table {order_index})"
    if bucket == "footnote":
        footnote_label = metadata.get("footnote_label") or metadata.get("footnoteLabel")
        if isinstance(footnote_label, str) and footnote_label.strip():
            return f"(Footnote {footnote_label.strip()})"
        return f"(Footnote p.{page_number})" if page_number else f"(Footnote {order_index})"
    return f"({bucket} {order_index})"


def _build_citation_entry(
    chunk: Dict[str, Any],
    bucket: str,
    label: str,
) -> Dict[str, Any]:
    metadata = _chunk_metadata(chunk)
    page_number = _resolve_page_number(chunk, metadata)
    char_start, char_end = _resolve_offsets(metadata)
    sentence_hash = _resolve_sentence_hash(chunk, metadata)
    document_url = _resolve_document_url(chunk, metadata)
    document_id = chunk.get("filing_id") or metadata.get("filing_id")
    excerpt = chunk.get("quote") or chunk.get("content") or metadata.get("quote")
    chunk_identifier = chunk.get("chunk_id") or chunk.get("id")
    entry: Dict[str, Any] = {
        "label": label,
        "bucket": bucket,
        "chunk_id": chunk_identifier,
        "page_number": page_number,
        "char_start": char_start,
        "char_end": char_end,
        "sentence_hash": sentence_hash,
        "document_id": document_id,
        "document_url": document_url,
        "source": chunk.get("source") or metadata.get("source"),
        "excerpt": excerpt,
    }
    anchor = chunk.get("anchor") or metadata.get("anchor")
    if isinstance(anchor, dict) and anchor:
        entry["anchor"] = anchor
    chunk_id_value = chunk_identifier if isinstance(chunk_identifier, str) else None
    deeplink = _build_deeplink_url(
        document_url,
        page_number,
        char_start=char_start,
        char_end=char_end,
        sentence_hash=sentence_hash,
        chunk_id=chunk_id_value,
        document_id=document_id if isinstance(document_id, str) else None,
        excerpt=excerpt if isinstance(excerpt, str) else None,
    )
    if deeplink:
        entry["deeplink_url"] = deeplink
    return entry


def _build_structured_citations(context_chunks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {"page": [], "table": [], "footnote": []}
    seen_chunks: Dict[str, set[str]] = {key: set() for key in buckets}
    for chunk in context_chunks:
        bucket = _bucket_for_chunk(chunk)
        if not bucket:
            continue
        entries = buckets.setdefault(bucket, [])
        if len(entries) >= MAX_CITATIONS_PER_BUCKET:
            continue
        raw_chunk_id = chunk.get("chunk_id") or chunk.get("id")
        chunk_id = raw_chunk_id.strip() if isinstance(raw_chunk_id, str) else raw_chunk_id
        if isinstance(chunk_id, str) and chunk_id in seen_chunks[bucket]:
            continue
        metadata = _chunk_metadata(chunk)
        label = _build_citation_label(chunk, bucket, metadata, len(entries) + 1)
        entry = _build_citation_entry(chunk, bucket, label)
        entries.append(entry)
        if isinstance(chunk_id, str):
            seen_chunks[bucket].add(chunk_id)
    return {bucket: entries for bucket, entries in buckets.items() if entries}


def _has_complete_snippet(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    char_start = entry.get("char_start")
    char_end = entry.get("char_end")
    sentence_hash = entry.get("sentence_hash")
    if char_start is None or char_end is None or sentence_hash is None:
        return False
    try:
        return int(char_end) > int(char_start)
    except (TypeError, ValueError):
        return False


def _find_missing_citations(required: Dict[str, bool], citations: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    missing: List[str] = []
    for key, needed in required.items():
        if not needed:
            continue
        entries = citations.get(key) or []
        if not entries:
            missing.append(key)
            continue
        if RAG_REQUIRE_SNIPPET and not any(_has_complete_snippet(entry) for entry in entries):
            missing.append(key)
    return missing


def _collect_highlights(context_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    highlights: List[Dict[str, Any]] = []
    for chunk in context_chunks:
        highlights.append(
            {
                "chunk_id": chunk.get("id"),
                "type": chunk.get("type"),
                "page_number": chunk.get("page_number"),
                "section": chunk.get("section"),
                "source": chunk.get("source"),
                "metadata": chunk.get("metadata") or {},
            }
        )
    return highlights


def _pick_prompt_builder(context_chunks: List[Dict[str, Any]]):
    if any((chunk.get("type") or "").lower() in {"table", "footnote", "figure"} for chunk in context_chunks):
        return table_aware_rag
    return rag_qa


def _format_transcript_for_summary(transcript: List[Dict[str, str]], *, max_chars: int = 4000) -> str:
    lines: List[str] = []
    for entry in transcript:
        role = str(entry.get("role") or "").strip().lower()
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        role_label = "사용자" if role == "user" else "Copilot"
        lines.append(f"{role_label}: {content}")
    combined = "\n".join(lines)
    if len(combined) <= max_chars:
        return combined
    # Prioritise the most recent part of the transcript for brevity.
    return combined[-max_chars:]


def assess_query_risk(question: str) -> Dict[str, Any]:
    messages = judge_guard.get_prompt(question)
    return _run_json_prompt(
        label="Guardrail judge",
        model=JUDGE_MODEL,
        messages=messages,
        normalizer=_format_guard_result,
        log_level="warning",
    )


def _build_rag_payload(
    context_chunks: List[Dict[str, Any]],
    answer: str,
    model_used: Optional[str],
) -> Dict[str, Any]:
    safe_answer, guardrail_error = guardrails.apply_answer_guard(answer)

    citations = _build_structured_citations(context_chunks)
    missing = _find_missing_citations(_categorize_context(context_chunks), citations)

    payload: Dict[str, Any] = {
        "answer": safe_answer,
        "original_answer": answer if guardrail_error else None,
        "model_used": model_used or RAG_MODEL,
        "context": list(context_chunks),
        "citations": citations,
        "warnings": [],
        "highlights": _collect_highlights(context_chunks),
        "error": None,
    }

    if guardrail_error:
        payload["warnings"].append(guardrail_error)
        payload["error"] = guardrail_error

    if missing:
        payload["warnings"].append("missing_citations:" + ",".join(missing))
        payload["error"] = payload.get("error") or "missing_citations"

    return payload


def generate_rag_answer(
    question: str,
    context_chunks: List[Dict[str, Any]],
    *,
    conversation_memory: Optional[Dict[str, Any]] = None,
    judge_result: Optional[Dict[str, Any]] = None,
    prompt_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if judge_result is None:
        judge_result = assess_query_risk(question)

    judge_decision = judge_result.get("decision") if judge_result else None
    judge_reason = judge_result.get("reason") if judge_result else None
    judge_model_used = judge_result.get("model_used") if judge_result else None
    rag_mode = (judge_result.get("rag_mode") if judge_result else None) or "vector"

    if judge_result.get("error"):
        logger.warning("Pre-judge evaluation failed for question.")
        judge_decision = "unknown"

    if judge_decision and judge_decision not in {"pass", "unknown"}:
        violation_code = "guardrail_violation_judge"
        warnings: List[str] = []
        if judge_reason:
            warnings.append(f"{violation_code}:{judge_reason}")
        else:
            warnings.append(violation_code)
        payload: Dict[str, Any] = {
            "answer": JUDGE_BLOCK_MESSAGE,
            "original_answer": None,
            "model_used": None,
            "context": [],
            "citations": {"page": [], "table": [], "footnote": []},
            "warnings": warnings,
            "highlights": [],
            "error": violation_code,
            "judge_decision": judge_decision,
        }
        if judge_reason:
            payload["judge_reason"] = judge_reason
        if judge_model_used:
            payload["judge_model_used"] = judge_model_used
        payload["rag_mode"] = rag_mode
        if prompt_metadata:
            payload["meta"] = {"prompt": prompt_metadata}
        return payload

    builder = _pick_prompt_builder(context_chunks)
    prompt_mode = "flex" if judge_decision == "pass" else "strict"
    messages = builder.get_prompt(
        question,
        context_chunks,
        conversation_memory=conversation_memory,
        mode=prompt_mode,
        meta=prompt_metadata,
    )
    response, model_used = _safe_completion(RAG_MODEL, messages)
    if response is None:
        return {"error": model_used or "rag_failed"}

    answer = _choice_content(response) or ""
    payload = _build_rag_payload(context_chunks, answer, model_used)
    payload["rag_mode"] = rag_mode
    if prompt_metadata:
        meta_payload = dict(payload.get("meta") or {})
        meta_payload.setdefault("prompt", prompt_metadata)
        payload["meta"] = meta_payload

    if judge_result.get("error"):
        payload["warnings"].append("judge_evaluation_failed")
        payload["judge_decision"] = judge_decision
    else:
        if judge_decision:
            payload["judge_decision"] = judge_decision
        if judge_reason:
            payload["judge_reason"] = judge_reason
        if judge_model_used:
            payload["judge_model_used"] = judge_model_used

    return payload


def stream_rag_answer(
    question: str,
    context_chunks: List[Dict[str, Any]],
    *,
    conversation_memory: Optional[Dict[str, Any]] = None,
    judge_result: Optional[Dict[str, Any]] = None,
    prompt_metadata: Optional[Dict[str, Any]] = None,
):
    if judge_result is None:
        judge_result = assess_query_risk(question)
    judge_decision = judge_result.get("decision") if judge_result else None
    judge_reason = judge_result.get("reason") if judge_result else None
    judge_model_used = judge_result.get("model_used") if judge_result else None
    rag_mode = (judge_result.get("rag_mode") if judge_result else None) or "vector"

    if judge_result.get("error"):
        logger.warning("Pre-judge evaluation failed for question.")
        judge_decision = "unknown"

    if judge_decision and judge_decision not in {"pass", "unknown"}:
        violation_code = "guardrail_violation_judge"
        warnings: List[str] = []
        if judge_reason:
            warnings.append(f"{violation_code}:{judge_reason}")
        else:
            warnings.append(violation_code)
        payload: Dict[str, Any] = {
            "answer": JUDGE_BLOCK_MESSAGE,
            "original_answer": None,
            "model_used": None,
            "context": [],
            "citations": {"page": [], "table": [], "footnote": []},
            "warnings": warnings,
            "highlights": [],
            "error": violation_code,
            "judge_decision": judge_decision,
        }
        if judge_reason:
            payload["judge_reason"] = judge_reason
        if judge_model_used:
            payload["judge_model_used"] = judge_model_used
        payload["rag_mode"] = rag_mode
        if prompt_metadata:
            payload["meta"] = {"prompt": prompt_metadata}
        yield {"type": "final", "payload": payload}
        return

    builder = _pick_prompt_builder(context_chunks)
    prompt_mode = "flex" if judge_decision == "pass" else "strict"
    messages = builder.get_prompt(
        question,
        context_chunks,
        conversation_memory=conversation_memory,
        mode=prompt_mode,
        meta=prompt_metadata,
    )
    try:
        stream = litellm.completion(model=RAG_MODEL, messages=messages, stream=True)
    except Exception as exc:
        logger.error("Streaming LLM call failed: %s", exc, exc_info=True)
        raise

    accumulated_tokens: List[str] = []
    model_used: Optional[str] = None

    for chunk in stream:
        chunk_dict = chunk if isinstance(chunk, dict) else getattr(chunk, "dict", lambda: None)()
        if chunk_dict is None:
            chunk_dict = getattr(chunk, "__dict__", {})
        if model_used is None:
            model_used = chunk_dict.get("model") or RAG_MODEL
        choices = chunk_dict.get("choices") or []
        if not choices:
            continue
        choice_obj = choices[0]
        token = ""
        if isinstance(choice_obj, dict):
            delta = choice_obj.get("delta") or {}
            if isinstance(delta, dict):
                token = delta.get("content") or ""
            if not token:
                token = choice_obj.get("text") or ""
        else:
            delta = getattr(choice_obj, "delta", None)
            if isinstance(delta, dict):
                token = delta.get("content") or ""
            if not token:
                token = getattr(choice_obj, "text", "") or getattr(choice_obj, "content", "") or ""
        if not token:
            continue
        accumulated_tokens.append(token)
        yield {"type": "token", "text": token}

    answer = "".join(accumulated_tokens)
    payload = _build_rag_payload(context_chunks, answer, model_used)
    payload["rag_mode"] = rag_mode
    if prompt_metadata:
        meta_payload = dict(payload.get("meta") or {})
        meta_payload.setdefault("prompt", prompt_metadata)
        payload["meta"] = meta_payload

    if judge_result.get("error"):
        payload["warnings"].append("judge_evaluation_failed")
        payload["judge_decision"] = judge_decision
    else:
        if judge_decision:
            payload["judge_decision"] = judge_decision
        if judge_reason:
            payload["judge_reason"] = judge_reason
        if judge_model_used:
            payload["judge_model_used"] = judge_model_used

    yield {"type": "final", "payload": payload}


def summarize_chat_transcript(transcript: List[Dict[str, str]]) -> str:
    if not transcript:
        return ""
    formatted = _format_transcript_for_summary(transcript)
    if not formatted:
        return ""
    messages = chat_summary.get_prompt(formatted)
    response, _ = _safe_completion(SUMMARY_MODEL, messages)
    if response is None:
        raise RuntimeError("chat_summary_failed")
    summary_text = _choice_content(response) or ""
    return summary_text.strip()


def _format_watchlist_digest_context(summary: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> str:
    lines: List[str] = []
    lines.append(
        f"- 경보 {summary.get('totalDeliveries', 0)}건, 이벤트 {summary.get('totalEvents', 0)}건, 감시 종목 {summary.get('uniqueTickers', 0)}개"
    )
    top_tickers = summary.get("topTickers") or []
    if top_tickers:
        lines.append(f"- Top 종목: {', '.join(map(str, top_tickers[:5]))}")
    for idx, item in enumerate(items[:5], start=1):
        ticker = item.get("ticker") or "N/A"
        rule_name = item.get("ruleName") or ""
        headline = item.get("headline") or item.get("summary") or item.get("message") or ""
        sentiment = item.get("sentiment")
        sentiment_text = (
            f"(sentiment={sentiment:.2f})" if isinstance(sentiment, (int, float)) else ""
        )
        lines.append(f"{idx}. {ticker} {rule_name} - {headline} {sentiment_text}".strip())
    return "\n".join(lines)


def generate_watchlist_digest_overview(
    summary: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> str:
    """LLM으로 Watchlist Digest 상단 요약문을 생성한다."""

    context_block = _format_watchlist_digest_context(summary, items)
    messages = [
        {
            "role": "system",
            "content": (
                "당신은 K-Finance Watchlist Digest를 작성하는 시니어 애널리스트입니다.\n"
                "- 최근 모멘텀, 수급, 감성 신호를 3~5문장으로 정리하고, 각 문장은 25~60자 사이로 유지합니다.\n"
                "- 첫 문장은 시장의 긍정적 흐름이나 주요 모멘텀, 두 번째는 핵심 종목/섹터 디테일, 세 번째는 리스크·주의 신호를 언급합니다.\n"
                "- 필요하면 네 번째 문장으로 향후 관찰 포인트를 제시할 수 있습니다.\n"
                "- 감탄사나 과도한 조언 없이 사실 기반·전문가 톤을 유지합니다."
            ),
        },
        {
            "role": "user",
            "content": (
                "다음 워치리스트 알림 데이터를 읽고 요구사항에 맞는 디테일한 요약을 작성하십시오.\n"
                "### 데이터\n"
                f"{context_block}\n\n"
                "### 출력 지침\n"
                "1. 문장 수 3~5개, 각 문장은 25~60자.\n"
                "2. 첫 문장은 모멘텀/수급, 두 번째는 종목·섹터 디테일, 세 번째는 리스크·주의 신호를 다룹니다.\n"
                "3. 네 번째 문장이 있다면 다음 관찰 포인트를 제시합니다.\n"
                "4. 불필요한 접두어(예: '요청하신', '다음은')는 제거하고 바로 내용으로 시작합니다."
            ),
        },
    ]
    response, _ = _safe_completion(SUMMARY_MODEL, messages, fallback_model=QUALITY_FALLBACK_MODEL)
    if response is None:
        raise RuntimeError("watchlist_overview_failed")
    overview = _choice_content(response) or ""
    return overview.strip()


def generate_watchlist_personal_note(prompt_text: str) -> Tuple[str, Dict[str, Any]]:
    """사용자 맞춤 워치리스트 코멘트를 생성한다."""

    messages = [
        {
            "role": "system",
            "content": (
                "당신은 사용자의 워치리스트 히스토리를 이해하는 K-Finance Copilot입니다.\n"
                "- 개인 메모는 3~5문장으로 구성하며, 각 문장은 25~65자 사이입니다.\n"
                "- 첫 문장은 관찰된 패턴·이벤트, 두 번째는 해당 종목/섹터의 의미, 세 번째는 리스크·주의 포인트를 설명합니다.\n"
                "- 네 번째 문장이 있다면 사용자에게 다음 액션(체크포인트, 비교 대상 등)을 제안합니다.\n"
                "- '투자하세요' 같은 직접 조언이나 감탄사는 금지하고, 중립적이지만 친절한 톤을 유지합니다.\n"
                "- 이미 prompt에 포함된 문장을 반복하지 말고 새롭게 정리합니다."
            ),
        },
        {
            "role": "user",
            "content": (
                "다음 맥락을 참고해 개인화된 워치리스트 메모를 작성해 주세요.\n"
                "### 사용자 맥락\n"
                f"{prompt_text}\n\n"
                "### 출력 지침\n"
                "1. 문장 수 3~5개, 각 문장은 25~65자.\n"
                "2. 첫 문장=관찰, 두 번째=의미/맥락, 세 번째=리스크, 네 번째=다음 액션.\n"
                "3. 존댓말(예: '~하셨습니다', '~확인해보세요')로 작성합니다.\n"
                "4. 동일한 단어 반복은 피하고, 각 문장은 고유한 정보를 담습니다."
            ),
        },
    ]
    response, model_used = _safe_completion(SUMMARY_MODEL, messages, fallback_model=QUALITY_FALLBACK_MODEL)
    if response is None:
        raise RuntimeError("watchlist_personal_note_failed")
    note = _choice_content(response) or ""
    metadata: Dict[str, Any] = {}
    if model_used:
        metadata["model"] = model_used
    usage_payload = _extract_usage_payload(response)
    if usage_payload:
        metadata["usage"] = usage_payload
    return note.strip(), metadata


__all__ = [
    "classify_filing_content",
    "route_chat_query",
    "extract_structured_info",
    "summarize_filing_content",
    "generate_daily_brief_trend",
    "self_check_extracted_info",
    "analyze_news_article",
    "validate_news_analysis_result",
    "generate_rag_answer",
    "stream_rag_answer",
    "summarize_chat_transcript",
    "generate_watchlist_digest_overview",
    "generate_watchlist_personal_note",
    "set_guardrail_copy",
    "assess_query_risk",
    "extract_value_chain_relations",
    "JUDGE_BLOCK_MESSAGE",
]


