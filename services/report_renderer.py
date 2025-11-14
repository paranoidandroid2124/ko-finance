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
    data.setdefault("summary", {})
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

    workdir = Path(tempfile.mkdtemp(prefix="event-brief-"))
    tex_path = workdir / "event_brief.tex"
    payload = _prepare_context(context)

    try:
        _render_latex_template(_EVENT_TEMPLATE, payload, tex_path)
    except Exception as exc:
        raise LatexRenderError(f"LaTeX 템플릿 렌더링에 실패했습니다: {exc}") from exc

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


__all__ = ["LatexRenderError", "render_event_brief"]
