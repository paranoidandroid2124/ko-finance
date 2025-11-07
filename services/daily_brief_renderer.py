"""Utilities for rendering the LaTeX daily brief template."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from core.logging import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates" / "latex"
TEMPLATE_NAME = "main.tex.jinja"
DEFAULT_PAYLOAD = TEMPLATE_DIR / "sample_payload.json"

SIGNAL_COLORS = {
    "primary": "Accent",
    "info": "AccentB",
    "accent": "AccentC",
    "warn": "AccentWarn",
    "neutral": "Stroke",
}

ALERT_COLORS = {
    "warn": "AccentWarn",
    "info": "AccentInfo",
    "accent": "AccentC",
}

ACTION_COLORS = {
    "primary": "AccentB",
    "info": "AccentInfo",
    "warn": "AccentWarn",
    "neutral": "AccentInfo",
}


def latex_escape(value: Any) -> str:
    """Escape basic LaTeX special characters while allowing macro usage."""
    if value is None:
        return ""
    text = str(value)
    replacements = [
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for target, replacement in replacements:
        text = text.replace(target, replacement)
    text = text.replace("\n", r"\\")
    return text.strip()


def map_color(mapping: Dict[str, str], severity: str | None, default: str) -> str:
    if severity:
        severity = severity.lower()
    return mapping.get(severity, default)


def validate_payload(payload: Dict[str, Any]) -> None:
    errors: List[str] = []
    report = payload.get("report")
    if not isinstance(report, dict):
        errors.append("report section is missing or invalid")
    else:
        if not report.get("title"):
            errors.append("report.title is required")
        if not report.get("date"):
            errors.append("report.date is required")
    signals = payload.get("signals", [])
    if not signals:
        errors.append("signals array must contain at least one item")
    else:
        for idx, item in enumerate(signals):
            if not item.get("label"):
                errors.append(f"signals[{idx}] is missing label")
            if item.get("value") in (None, ""):
                errors.append(f"signals[{idx}] is missing value")
    evidence = payload.get("evidence", [])
    if not evidence:
        errors.append("evidence array must contain at least one item")
    if errors:
        formatted = "\n".join(f"- {msg}" for msg in errors)
        raise ValueError(f"Daily brief payload validation failed:\n{formatted}")


def split_main_appendix(items: List[Dict[str, Any]], limit: int | None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if limit is None or limit <= 0 or limit >= len(items):
        return items, []
    return items[:limit], items[limit:]


def prepare_signals(payload: Dict[str, Any], top_n: Dict[str, int]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    raw = payload.get("signals", [])
    signals: List[Dict[str, str]] = []
    for item in raw:
        severity = item.get("severity")
        signals.append(
            {
                "frame_color": map_color(SIGNAL_COLORS, severity, "Accent"),
                "label": latex_escape(item.get("label", "")),
                "value": latex_escape(item.get("value", "")),
                "delta": latex_escape(item.get("delta", "")),
                "note": latex_escape(item.get("note", "")),
            }
        )
    return split_main_appendix(signals, top_n.get("signals"))


def prepare_alerts(payload: Dict[str, Any], top_n: Dict[str, int]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    raw = payload.get("alerts", [])
    alerts: List[Dict[str, str]] = []
    for item in raw:
        severity = item.get("severity")
        alerts.append(
            {
                "frame_color": map_color(ALERT_COLORS, severity, "AccentWarn"),
                "title": latex_escape(item.get("title", "")),
                "body": latex_escape(item.get("body", "")),
            }
        )
    return split_main_appendix(alerts, top_n.get("alerts"))


def prepare_actions(payload: Dict[str, Any], top_n: Dict[str, int]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    raw = payload.get("actions", [])
    actions: List[Dict[str, Any]] = []
    for item in raw:
        severity = item.get("severity")
        actions.append(
            {
                "frame_color": map_color(ACTION_COLORS, severity, "AccentB"),
                "title": latex_escape(item.get("title", "")),
                "ordered": bool(item.get("ordered")),
                "entries": [latex_escape(value) for value in item.get("items", []) if value],
            }
        )
    return split_main_appendix(actions, top_n.get("actions"))


def prepare_evidence(payload: Dict[str, Any], top_n: Dict[str, int]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    raw = payload.get("evidence", [])
    evidence: List[Dict[str, Any]] = []
    for item in raw:
        source = latex_escape(item.get("source", ""))
        date_text = latex_escape(item.get("date", ""))
        badge_parts = [part for part in (source, date_text) if part]
        badge = " · ".join(badge_parts) if badge_parts else "Evidence"
        evidence.append(
            {
                "badge": badge,
                "source": source,
                "date": date_text,
                "title": latex_escape(item.get("title", "")),
                "body": latex_escape(item.get("body", "")),
                "trace_id": latex_escape(item.get("trace_id", "")),
                "url": latex_escape(item.get("url", "")),
            }
        )
    return split_main_appendix(evidence, top_n.get("evidence"))


def prepare_metrics(payload: Dict[str, Any], top_n: Dict[str, int]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    raw = payload.get("metrics", [])
    metrics: List[Dict[str, str]] = []
    for item in raw:
        metrics.append(
            {
                "label": latex_escape(item.get("label", "")),
                "current": latex_escape(item.get("current", "")),
                "delta": latex_escape(item.get("delta", "")),
            }
        )
    return split_main_appendix(metrics, top_n.get("metrics"))


def prepare_notes(payload: Dict[str, Any], top_n: Dict[str, int]) -> Tuple[List[str], List[str]]:
    raw = payload.get("notes", [])
    notes = [latex_escape(item) for item in raw if item]
    return split_main_appendix(notes, top_n.get("notes"))


def build_appendix_sections(payload: Dict[str, Any], overflow: Dict[str, Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    appendix = payload.get("appendix", {}) or {}
    sections = appendix.get("sections", []) if isinstance(appendix, dict) else []
    result: List[Dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        processed: Dict[str, Any] = {
            "title": latex_escape(section.get("title", "")),
            "type": section.get("type", "list"),
        }
        section_type = processed["type"]
        if section_type == "list":
            processed["list_items"] = [latex_escape(item) for item in section.get("items", [])]
        elif section_type == "cards":
            processed["card_items"] = [
                {
                    "title": latex_escape(item.get("title", "")),
                    "body": latex_escape(item.get("body", "")),
                    "note": latex_escape(item.get("note", "")),
                }
                for item in section.get("items", [])
            ]
        elif section_type == "table":
            processed["table_rows"] = [
                {
                    "label": latex_escape(row.get("label", "")),
                    "value": latex_escape(row.get("value", "")),
                }
                for row in section.get("rows", [])
            ]
        else:
            continue
        if processed.get("list_items") or processed.get("card_items") or processed.get("table_rows"):
            result.append(processed)

    for key, items in overflow.items():
        overflow_items = list(items)
        if not overflow_items:
            continue
        if key == "signals":
            section = {
                "title": "추가 시그널",
                "type": "list",
                "list_items": [
                    f"{entry['label']} \\textemdash{{}} {entry['value']} ({entry['delta']}) :: {entry['note']}"
                    for entry in overflow_items
                ],
            }
        elif key == "alerts":
            section = {
                "title": "추가 알림",
                "type": "list",
                "list_items": [f"{entry['title']}: {entry['body']}" for entry in overflow_items],
            }
        elif key == "actions":
            section = {
                "title": "추가 액션",
                "type": "list",
                "list_items": [
                    entry["title"] + " \\textemdash{} " + "; ".join(entry["entries"])
                    for entry in overflow_items
                ],
            }
        elif key == "evidence":
            section = {
                "title": "추가 근거",
                "type": "cards",
                "card_items": overflow_items,
            }
        elif key == "metrics":
            section = {
                "title": "추가 지표",
                "type": "table",
                "table_rows": [
                    {
                        "label": entry["label"],
                        "value": f"{entry['current']} ({entry['delta']})",
                    }
                    for entry in overflow_items
                ],
            }
        elif key == "notes":
            section = {
                "title": "추가 메모",
                "type": "list",
                "list_items": overflow_items,
            }
        else:
            continue
        result.append(section)

    return result


def generate_charts(charts_payload: Dict[str, Any], output_dir: Path) -> Dict[str, str]:
    generated: Dict[str, str] = {}
    for key, config in charts_payload.items():
        if isinstance(config, str):
            generated[key] = latex_escape(config)
            continue
        if not isinstance(config, dict):
            continue
        path_str = config.get("path", f"assets/{key}.pdf")
        output_path = output_dir / path_str
        output_path.parent.mkdir(parents=True, exist_ok=True)
        series = config.get("series") or []
        if series:
            try:
                import matplotlib.pyplot as plt  # type: ignore
            except ImportError:
                logger.info("matplotlib not available; skipping chart '%s'.", key)
            else:
                x_labels = config.get("x")
                fig, ax = plt.subplots(figsize=(5, 2.4))
                for serie in series:
                    values = serie.get("values") or []
                    if not values:
                        continue
                    label = serie.get("label")
                    if x_labels and len(x_labels) == len(values):
                        ax.plot(x_labels, values, marker="o", label=label)
                    else:
                        ax.plot(range(len(values)), values, marker="o", label=label)
                ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.6)
                if any(serie.get("label") for serie in series):
                    ax.legend(loc="best", fontsize=8)
                ax.set_xlabel(config.get("x_label", "Window"), fontsize=8)
                ax.set_ylabel(config.get("y_label", "Minutes"), fontsize=8)
                ax.tick_params(axis="both", labelsize=8)
                plt.tight_layout()
                plt.savefig(output_path, format="pdf")
                plt.close(fig)
        generated[key] = latex_escape(path_str)
    return generated


def prepare_context(payload: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    report = payload.get("report", {})
    top_n = report.get("top_n", {})

    signals_main, signals_appendix = prepare_signals(payload, top_n)
    alerts_main, alerts_appendix = prepare_alerts(payload, top_n)
    actions_main, actions_appendix = prepare_actions(payload, top_n)
    evidence_main, evidence_appendix = prepare_evidence(payload, top_n)
    metrics_main, metrics_appendix = prepare_metrics(payload, top_n)
    notes_main, notes_appendix = prepare_notes(payload, top_n)

    overflow = {
        "signals": signals_appendix,
        "alerts": alerts_appendix,
        "actions": actions_appendix,
        "evidence": evidence_appendix,
        "metrics": metrics_appendix,
        "notes": notes_appendix,
    }

    appendix_sections = build_appendix_sections(payload, overflow)
    charts = generate_charts(payload.get("charts", {}), output_dir)
    charts.setdefault("sla_trend", "")

    context = {
        "report": {
            "title": latex_escape(report.get("title", "AI Market Signals")),
            "date": latex_escape(report.get("date", "")),
            "headline": latex_escape(report.get("headline", "")),
        },
        "signals_main": signals_main,
        "alerts_main": alerts_main,
        "actions_main": actions_main,
        "evidence_main": evidence_main,
        "metrics_main": metrics_main,
        "notes_main": notes_main,
        "appendix": {"sections": appendix_sections},
        "charts": charts,
    }

    links = payload.get("links", {})
    if links:
        context["links"] = {key: latex_escape(value) for key, value in links.items()}
    return context


def _copy_support_assets(workdir: Path) -> None:
    for subdir in ("assets", "fonts"):
        src = TEMPLATE_DIR / subdir
        if src.exists():
            dst = workdir / subdir
            shutil.copytree(src, dst, dirs_exist_ok=True)


def render_latex(context: Dict[str, Any], output_tex: Path) -> None:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(TEMPLATE_NAME)
    rendered = template.render(**context)
    output_tex.write_text(rendered, encoding="utf-8")


def compile_pdf(tex_path: Path) -> Path:
    workdir = tex_path.parent
    _copy_support_assets(workdir)
    latexmk_path = shutil.which("latexmk")
    if latexmk_path:
        cmd = [latexmk_path, "-lualatex", "-interaction=nonstopmode", tex_path.name]
        result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode == 0:
            return workdir / (tex_path.stem + ".pdf")
        logger.warning("latexmk failed for %s; falling back to lualatex. stderr=%s", tex_path, result.stderr)
    for _ in range(2):
        result = subprocess.run(
            ["lualatex", "-interaction=nonstopmode", tex_path.name],
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(f"lualatex failed:\n{result.stdout}\n{result.stderr}")
    return workdir / (tex_path.stem + ".pdf")


def render_daily_brief(
    payload: Dict[str, Any],
    output_dir: Path,
    *,
    tex_name: str = "daily_brief.tex",
    compile_pdf_output: bool = False,
) -> Dict[str, Path]:
    """Render the payload into LaTeX (and optionally PDF)."""

    validate_payload(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    context = prepare_context(payload, output_dir)

    output_tex = output_dir / tex_name
    render_latex(context, output_tex)
    result: Dict[str, Path] = {"tex": output_tex}

    if compile_pdf_output:
        pdf_path = compile_pdf(output_tex)
        result["pdf"] = pdf_path
    return result


__all__ = [
    "DEFAULT_PAYLOAD",
    "TEMPLATE_DIR",
    "TEMPLATE_NAME",
    "compile_pdf",
    "generate_charts",
    "prepare_context",
    "render_daily_brief",
    "render_latex",
    "validate_payload",
]
