"""Typst CLI wrapper used to generate PDF reports."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_TYPST_BIN = os.getenv("TYPST_BIN", "typst")
_TEMPLATE_ROOT = Path(os.getenv("TYPST_TEMPLATE_DIR", "templates/typst"))


class TypstRenderError(RuntimeError):
    """Raised when Typst rendering fails."""


def _resolve_template(template: Path | str) -> Path:
    """Resolve a Typst template path relative to the project template directory."""

    path = Path(template)
    if path.suffix != ".typ":
        path = path.with_suffix(".typ")

    if not path.is_absolute():
        candidate = _TEMPLATE_ROOT / path.name
        if candidate.exists():
            path = candidate
        else:
            candidate = _TEMPLATE_ROOT / path
            if candidate.exists():
                path = candidate

    if not path.exists():
        raise FileNotFoundError(f"Typst template not found: {path}")
    return path


def render_typst_pdf(
    template: Path | str,
    context: Mapping[str, Any],
    *,
    output_path: Optional[Path | str] = None,
    typst_bin: Optional[str] = None,
    timeout_seconds: int = 120,
) -> Path:
    """
    Render a Typst template into a PDF.

    Parameters
    ----------
    template:
        Path or filename of the Typst template (`.typ`).
    context:
        JSON-serialisable mapping passed to the template as ``context`` input.
    output_path:
        Optional explicit output path. When omitted a temporary file is created.
    typst_bin:
        Override for Typst executable (defaults to ``TYPST_BIN`` env or ``typst``).
    timeout_seconds:
        Maximum seconds to wait for Typst CLI.
    """

    template_path = _resolve_template(template)
    typst_exec = typst_bin or _DEFAULT_TYPST_BIN

    if shutil.which(typst_exec) is None:
        raise TypstRenderError(f"Typst binary '{typst_exec}' is not available on PATH.")

    if output_path is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="typst-report-"))
        output_path = temp_dir / f"{template_path.stem}.pdf"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="typst-context-") as tmpdir:
        context_path = Path(tmpdir) / "context.json"
        context_json = json.dumps(context, ensure_ascii=False, indent=2)
        context_path.write_text(context_json, encoding="utf-8")

        command = [
            typst_exec,
            "compile",
            str(template_path),
            str(output_path),
            "--input",
            f"context={context_path}",
        ]

        logger.info("Rendering Typst template %s → %s", template_path, output_path)

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise TypstRenderError(f"Typst rendering timed out after {timeout_seconds}s.") from exc
        except FileNotFoundError as exc:
            raise TypstRenderError(f"Typst binary '{typst_exec}' is not accessible.") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            logger.error(
                "Typst rendering failed (code=%s). stdout=%s stderr=%s",
                result.returncode,
                stdout,
                stderr,
            )
            raise TypstRenderError(f"Typst rendering failed: {stderr or stdout or 'unknown error'}")

    if not output_path.is_file():
        raise TypstRenderError(f"Typst did not produce the expected PDF at {output_path}.")

    return output_path


def render_event_brief(
    context: Mapping[str, Any],
    *,
    output_path: Optional[Path | str] = None,
    typst_bin: Optional[str] = None,
    timeout_seconds: int = 120,
) -> Path:
    """Convenience wrapper to render the default event brief template."""

    return render_typst_pdf(
        "event_brief.typ",
        context,
        output_path=output_path,
        typst_bin=typst_bin,
        timeout_seconds=timeout_seconds,
    )


__all__ = ["TypstRenderError", "render_typst_pdf", "render_event_brief"]
