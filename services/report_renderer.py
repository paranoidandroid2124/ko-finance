"""LaTeX-based renderer for event briefs and research PDFs."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from core.logging import get_logger
from services.daily_brief_renderer import compile_pdf as compile_latex_pdf

logger = get_logger(__name__)

_TEMPLATE_DIR = Path(os.getenv("LATEX_TEMPLATE_DIR", "templates/latex"))
_EVENT_TEMPLATE = os.getenv("EVENT_BRIEF_TEMPLATE", "event_brief.tex.jinja")
_EVENT_STUDY_TEMPLATE = os.getenv("EVENT_STUDY_TEMPLATE", "event_study_report.tex.jinja")


class LatexRenderError(RuntimeError):
    """Raised when LaTeX rendering fails."""


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _prepare_context(payload: Mapping[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    data.setdefault("report", {})
    data.setdefault("company", {})
    summary_block = data.setdefault("summary", {})
    if isinstance(summary_block, Mapping):
        summary_block.setdefault("highlights", [])
        summary_block.setdefault("risks", [])
        summary_block.setdefault("actions", [])
    data.setdefault("evidence", [])
    data.setdefault("diff_summary", {})
    data.setdefault("rag", {})
    return data


def _render_latex_template(template_name: str, context: Mapping[str, Any], output_tex: Path) -> None:
    env = _environment()
    try:
        template = env.get_template(template_name)
    except Exception as exc:  # pragma: no cover - template resolution issues
        raise LatexRenderError(f"LaTeX 템플릿을 찾을 수 없습니다: {template_name}") from exc
    rendered = template.render(**context)
    output_tex.write_text(rendered, encoding="utf-8")


def _render_pdf_from_template(
    template_name: str,
    context: Mapping[str, Any],
    *,
    output_path: Optional[Path | str] = None,
) -> Path:
    workdir = Path(tempfile.mkdtemp(prefix="event-report-"))
    tex_path = workdir / f"{Path(template_name).stem or 'report'}.tex"
    payload = dict(context or {})
    try:
        _render_latex_template(template_name, payload, tex_path)
    except Exception as exc:
        raise LatexRenderError(f"LaTeX 템플릿 렌더링에 실패했습니다: {template_name}: {exc}") from exc

    try:
        pdf_path = compile_latex_pdf(tex_path)
    except Exception as exc:  # pragma: no cover - external latexmk errors
        raise LatexRenderError(f"LaTeX 컴파일에 실패했습니다: {exc}") from exc

    if output_path:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_path, target)
        return target
    return pdf_path


def render_event_brief(
    context: Mapping[str, Any],
    *,
    output_path: Optional[Path | str] = None,
    typst_bin: Optional[str] = None,  # kept for backward compatibility
    timeout_seconds: int = 120,  # kept for backward compatibility
) -> Path:
    """
    Render the event brief payload into a PDF using the LaTeX pipeline.

    Parameters
    ----------
    context:
        Mapping produced by ``services.event_brief_service.make_event_brief``.
    output_path:
        Optional target path for the generated PDF. When omitted a temporary directory is used.
    typst_bin / timeout_seconds:
        Deprecated arguments kept for compatibility. They have no effect in the LaTeX pipeline.
    """

    payload = _prepare_context(context)
    return _render_pdf_from_template(_EVENT_TEMPLATE, payload, output_path=output_path)


def render_event_study_report(
    context: Mapping[str, Any],
    *,
    output_path: Optional[Path | str] = None,
) -> Path:
    """Render the event study report payload into a PDF."""

    payload = dict(context or {})
    return _render_pdf_from_template(_EVENT_STUDY_TEMPLATE, payload, output_path=output_path)


__all__ = ["LatexRenderError", "render_event_brief", "render_event_study_report"]
