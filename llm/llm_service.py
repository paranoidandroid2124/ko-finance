"""LLM interaction helpers for filings, news analysis, and RAG answers."""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import litellm
from langfuse import Langfuse

from core.logging import get_logger
from llm.guardrails import apply_answer_guard
from llm.prompts import (
    analyze_news,
    classify_filing,
    extract_info,
    rag_qa,
    self_check,
    summarize_report,
    table_aware_rag,
)

logger = get_logger(__name__)

LANGFUSE_CLIENT: Optional[Langfuse] = None
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

CLASSIFICATION_MODEL = os.getenv("LLM_CLASSIFICATION_MODEL", "gemini_flash_lite")
SUMMARY_MODEL = os.getenv("LLM_SUMMARY_MODEL", "gemini_flash_lite")
EXTRACTION_MODEL = os.getenv("LLM_EXTRACTION_MODEL", "gemini_flash_lite")
SELF_CHECK_MODEL = os.getenv("LLM_SELF_CHECK_MODEL", "gemini_flash_lite")
NEWS_ANALYSIS_MODEL = os.getenv("LLM_NEWS_MODEL", "gemini_flash_lite")
RAG_MODEL = os.getenv("LLM_RAG_MODEL", "gemini_flash_lite")
QUALITY_FALLBACK_MODEL = os.getenv("LLM_QUALITY_FALLBACK_MODEL", "gpt-4.1")

CITATION_PAGE_RE = re.compile(r"\(p\.\s*\d+\)", re.IGNORECASE)
CITATION_TABLE_RE = re.compile(r"\(table\s*[^\)]+\)", re.IGNORECASE)
CITATION_FOOTNOTE_RE = re.compile(r"\(footnote\s*[^\)]+\)", re.IGNORECASE)


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


def _safe_completion(
    model: str,
    messages: List[Dict[str, Any]],
    *,
    response_format: Optional[Dict[str, Any]] = None,
    fallback_model: Optional[str] = None,
) -> Tuple[Optional[Any], Optional[str]]:
    try:
        response = litellm.completion(model=model, messages=messages, response_format=response_format)
        response_content = getattr(response.choices[0].message, "content", "")
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
                response_content = getattr(response.choices[0].message, "content", "")
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
        payload = json.loads(response.choices[0].message.content)
        payload["model_used"] = model_used
        return payload
    except Exception as exc:
        logger.error("JSON decode failure: %s", exc, exc_info=True)
        return {"error": f"JSON decode failure: {exc}", "model_used": model_used}


def classify_filing_content(raw_md: str) -> Dict[str, Any]:
    snippet = raw_md[:12000]
    messages = classify_filing.get_prompt(snippet)
    result = _json_completion(CLASSIFICATION_MODEL, messages)
    if "error" in result:
        logger.error("Classification failed: %s", result["error"])
    return result


def extract_structured_info(raw_md: str) -> Dict[str, Any]:
    snippet = raw_md[:24000]
    messages = extract_info.get_prompt(snippet)
    result = _json_completion(EXTRACTION_MODEL, messages)
    if "error" in result:
        logger.error("Extraction failed: %s", result["error"])
    return result


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
    result = _json_completion(NEWS_ANALYSIS_MODEL, messages, fallback_model=QUALITY_FALLBACK_MODEL)
    if "error" in result:
        logger.error("News analysis failed: %s", result["error"])
        return result
    validated = validate_news_analysis_result(result)
    if "error" in validated:
        return validated
    logger.info("News analysis sentiment=%s", validated.get("sentiment"))
    return validated


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
    result = _json_completion(SELF_CHECK_MODEL, messages)
    if "error" in result:
        logger.error("Self-check failed: %s", result["error"])
    return result


def summarize_filing_content(raw_md: str) -> Dict[str, Any]:
    snippet = raw_md[:24000]
    messages = summarize_report.get_prompt(snippet)
    result = _json_completion(SUMMARY_MODEL, messages)
    if "error" in result:
        logger.error("Summary generation failed: %s", result["error"])
    return result


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


def _extract_citations(answer: str) -> Dict[str, List[str]]:
    if not answer:
        return {"page": [], "table": [], "footnote": []}
    return {
        "page": CITATION_PAGE_RE.findall(answer),
        "table": CITATION_TABLE_RE.findall(answer),
        "footnote": CITATION_FOOTNOTE_RE.findall(answer),
    }


def _find_missing_citations(required: Dict[str, bool], citations: Dict[str, List[str]]) -> List[str]:
    missing: List[str] = []
    for key, needed in required.items():
        if needed and not citations.get(key):
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
                "metadata": chunk.get("metadata"),
            }
        )
    return highlights


def _select_prompt_builder(context_chunks: List[Dict[str, Any]]):
    if any((chunk.get("type") or "").lower() in {"table", "footnote", "figure"} for chunk in context_chunks):
        return table_aware_rag
    return rag_qa


def answer_with_rag(question: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    builder = _select_prompt_builder(context_chunks)
    messages = builder.get_prompt(question, context_chunks)
    response, model_used = _safe_completion(RAG_MODEL, messages)
    if response is None:
        return {"error": model_used or "rag_failed"}

    answer = getattr(response.choices[0].message, "content", "") or ""
    safe_answer, guardrail_error = apply_answer_guard(answer)

    citations = _extract_citations(safe_answer)
    missing = _find_missing_citations(_categorize_context(context_chunks), citations)

    payload: Dict[str, Any] = {
        "answer": safe_answer,
        "original_answer": answer if guardrail_error else None,
        "model_used": model_used,
        "context": context_chunks,
        "citations": citations,
        "warnings": [],
        "highlights": _collect_highlights(context_chunks),
    }

    if guardrail_error:
        payload["warnings"].append(guardrail_error)
        payload["error"] = guardrail_error

    if missing:
        payload["warnings"].append("missing_citations:" + ",".join(missing))
        payload["error"] = payload.get("error") or "missing_citations"

    return payload


__all__ = [
    "classify_filing_content",
    "extract_structured_info",
    "summarize_filing_content",
    "self_check_extracted_info",
    "analyze_news_article",
    "validate_news_analysis_result",
    "answer_with_rag",
]

