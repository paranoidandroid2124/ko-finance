"""Render the LaTeX daily brief template with JSON data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.env_utils import load_dotenv_if_available

load_dotenv_if_available()

from services.daily_brief_renderer import (
    DEFAULT_PAYLOAD,
    compile_pdf,
    prepare_context,
    render_latex,
    validate_payload,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = REPO_ROOT / "build" / "daily_brief"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the LaTeX daily brief template.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_PAYLOAD,
        help="Path to JSON payload (default: sample payload).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_ROOT,
        help="Directory where rendered files will be written.",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Compile the rendered TeX to PDF using latexmk.",
    )
    parser.add_argument(
        "--tex-name",
        default="daily_brief.tex",
        help="Filename for the rendered TeX output (default: daily_brief.tex).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    validate_payload(payload)
    context = prepare_context(payload, output_dir)

    output_tex = output_dir / args.tex_name
    render_latex(context, output_tex)
    print(f"Rendered LaTeX written to {output_tex}")

    if args.compile:
        pdf_path = compile_pdf(output_tex)
        print(f"PDF generated at {pdf_path}")


if __name__ == "__main__":
    main()
