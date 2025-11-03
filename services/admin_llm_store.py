"""Persistence helpers for administrator-managed LLM configuration."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.logging import get_logger
from services.admin_audit import append_audit_log
from services.admin_shared import (
    ADMIN_BASE_DIR,
    ensure_parent_dir,
    now_iso,
)

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

_ADMIN_DIR = ADMIN_BASE_DIR
_PROMPTS_PATH = _ADMIN_DIR / "system_prompts.json"
_GUARDRAIL_PATH = _ADMIN_DIR / "guardrails_policy.json"

_DEFAULT_PROMPTS = {
    "chat": {
        "prompt": "You are K-Finance Copilot. Respond with warm, social-enterprise tone.",
        "updatedBy": "system",
    },
    "rag": {
        "prompt": "Summarize retrieved evidence in Korean with polite, concise tone.",
        "updatedBy": "system",
    },
    "self_check": {
        "prompt": "Evaluate factual consistency and guardrail adherence before replying.",
        "updatedBy": "system",
    },
}

_DEFAULT_GUARDRAIL_POLICY = {
    "intentRules": [{"name": "finance_only", "threshold": 0.7}],
    "blocklist": ["pump and dump", "매수 추천", "확실한 수익"],
    "userFacingCopy": {
        "fallback": "투자 자문이나 매수·매도 권고는 제공되지 않습니다. 정보 제공 목적의 분석 질문만 부탁드립니다.",
        "blocked": "죄송해요, 이 주제는 내부 정책상 안내가 어려워요.",
    },
    "updatedAt": None,
    "updatedBy": None,
}

def load_litellm_config(path: Optional[Path] = None) -> Tuple[Path, Dict[str, object]]:
    """
    Load the LiteLLM configuration YAML file.

    Returns the resolved path and parsed config dictionary.
    """
    resolved = path or _resolve_litellm_config_path()
    if resolved is None:
        raise RuntimeError("LiteLLM configuration file could not be located.")
    if not resolved.exists():
        return resolved, {}
    if yaml is None:
        raise RuntimeError("PyYAML is required to manage LiteLLM profiles.")
    try:
        content = resolved.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content) or {}
        if not isinstance(parsed, dict):
            raise ValueError("Parsed LiteLLM config is not a mapping.")
        return resolved, parsed
    except Exception as exc:
        raise RuntimeError(f"Failed to read LiteLLM config: {exc}") from exc


def save_litellm_config(path: Path, config: Dict[str, object]) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML is required to manage LiteLLM profiles.")
    try:
        path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to write LiteLLM config: {exc}") from exc


def _resolve_litellm_config_path() -> Optional[Path]:
    env_path = os.getenv("LITELLM_CONFIG_PATH")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.is_file():
            return candidate
    default_path = Path(__file__).resolve().parents[2] / "litellm_config.yaml"
    if default_path.is_file():
        return default_path
    return None


def list_litellm_profiles(config: Dict[str, object]) -> List[Dict[str, object]]:
    model_list = config.get("model_list")
    if not isinstance(model_list, list):
        return []

    profiles: List[Dict[str, object]] = []
    for entry in model_list:
        if not isinstance(entry, dict):
            continue
        name = entry.get("model_name")
        params = entry.get("litellm_params")
        if not isinstance(name, str) or not isinstance(params, dict):
            continue
        profiles.append(
            {
                "name": name,
                "model": params.get("model"),
                "settings": {k: v for k, v in params.items() if k != "model"},
            }
        )
    return profiles


def upsert_litellm_profile(
    config: Dict[str, object],
    *,
    name: str,
    model: str,
    settings: Dict[str, object],
) -> Dict[str, object]:
    model_list = config.setdefault("model_list", [])
    if not isinstance(model_list, list):
        raise RuntimeError("Invalid LiteLLM configuration: model_list must be a list.")

    target_entry: Optional[Dict[str, object]] = None
    for entry in model_list:
        if isinstance(entry, dict) and entry.get("model_name") == name:
            target_entry = entry
            break

    params = {"model": model}
    params.update(settings)

    if target_entry is None:
        model_list.append({"model_name": name, "litellm_params": params})
    else:
        target_entry["litellm_params"] = params

    return {
        "name": name,
        "model": model,
        "settings": settings,
    }


def load_system_prompts() -> Dict[str, Dict[str, object]]:
    if _PROMPTS_PATH.exists():
        try:
            payload = json.loads(_PROMPTS_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError as exc:  # pragma: no cover
            logger.warning("Failed to parse system prompts store: %s", exc)
    return dict(_DEFAULT_PROMPTS)


def save_system_prompts(prompts: Dict[str, Dict[str, object]]) -> None:
    ensure_parent_dir(_PROMPTS_PATH, logger)
    try:
        _PROMPTS_PATH.write_text(json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to write system prompts: {exc}") from exc


def update_system_prompt(
    *,
    channel: str,
    prompt: str,
    actor: str,
    note: Optional[str] = None,
) -> Dict[str, object]:
    prompts = load_system_prompts()
    prompts[channel] = {
        "prompt": prompt,
        "updatedAt": now_iso(),
        "updatedBy": actor,
        "note": note,
    }
    save_system_prompts(prompts)
    append_audit_log(
        filename="llm_audit.jsonl",
        actor=actor,
        action=f"prompt_update:{channel}",
        payload={"note": note},
    )
    return prompts[channel]


def load_guardrail_policy() -> Dict[str, object]:
    if _GUARDRAIL_PATH.exists():
        try:
            payload = json.loads(_GUARDRAIL_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError as exc:  # pragma: no cover
            logger.warning("Failed to parse guardrail policy store: %s", exc)
    return dict(_DEFAULT_GUARDRAIL_POLICY)


def save_guardrail_policy(policy: Dict[str, object]) -> None:
    ensure_parent_dir(_GUARDRAIL_PATH, logger)
    try:
        _GUARDRAIL_PATH.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to write guardrail policy: {exc}") from exc


def update_guardrail_policy(
    *,
    intent_rules: List[Dict[str, object]],
    blocklist: List[str],
    user_facing_copy: Dict[str, str],
    actor: str,
    note: Optional[str],
) -> Dict[str, object]:
    payload = {
        "intentRules": intent_rules,
        "blocklist": blocklist,
        "userFacingCopy": user_facing_copy,
        "updatedAt": now_iso(),
        "updatedBy": actor,
        "note": note,
    }
    save_guardrail_policy(payload)
    append_audit_log(
        filename="llm_audit.jsonl",
        actor=actor,
        action="guardrail_update",
        payload={"note": note, "blocklist_size": len(blocklist)},
    )
    return payload


__all__ = [
    "list_litellm_profiles",
    "load_guardrail_policy",
    "load_litellm_config",
    "load_system_prompts",
    "save_litellm_config",
    "update_guardrail_policy",
    "update_system_prompt",
    "upsert_litellm_profile",
]
