"""Composite evaluation runner for classification and RAG pipelines."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from core.logging import get_logger

logger = get_logger(__name__)


def _run_subprocess(command: List[str], *, cwd: Optional[Path] = None) -> int:
    logger.info("Executing command: %s", " ".join(command))
    try:
        result = subprocess.run(command, cwd=cwd, check=True)
        return result.returncode
    except subprocess.CalledProcessError as exc:
        logger.error("Evaluation command failed (exit=%s): %s", exc.returncode, exc)
        return exc.returncode


def run_promptfoo_eval(config_path: Path, *, use_npx: bool = True) -> int:
    if not config_path.is_file():
        logger.warning("Promptfoo config not found: %s", config_path)
        return 0

    binary = "npx" if use_npx else "promptfoo"
    if shutil.which(binary) is None:
        fallback = "promptfoo" if use_npx else "npx"
        if use_npx and shutil.which("promptfoo"):
            binary = "promptfoo"
        elif not use_npx and shutil.which("npx"):
            binary = "npx"
        else:
            logger.warning(
                "Neither promptfoo nor npx is available on PATH. Skipping prompt evaluation."
            )
            return 0

    command = [binary]
    if binary == "npx":
        command.extend(["promptfoo@latest", "eval", str(config_path)])
    else:
        command.extend(["eval", str(config_path)])

    return _run_subprocess(command)


def run_ragas_eval(script_path: Path, filing_id: Optional[str], question: Optional[str], *, top_k: int) -> int:
    if not script_path.is_file():
        logger.warning("Ragas evaluation script not found: %s", script_path)
        return 0
    if not (filing_id and question):
        logger.info("Skipping Ragas evaluation (filing-id or question missing).")
        return 0

    command = [
        sys.executable,
        str(script_path),
        "--filing-id",
        filing_id,
        "--question",
        question,
        "--top-k",
        str(top_k),
    ]
    return _run_subprocess(command)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run model evaluation suites.")
    parser.add_argument(
        "--promptfoo-config",
        type=Path,
        default=Path("eval/promptfoo/m1_classification.yaml"),
        help="Path to promptfoo configuration file.",
    )
    parser.add_argument(
        "--ragas-script",
        type=Path,
        default=Path("eval/ragas/m1_self_check_template.py"),
        help="Path to the Ragas evaluation script.",
    )
    parser.add_argument("--filing-id", help="Filing UUID for Ragas evaluation.")
    parser.add_argument("--question", help="Question text for the Ragas evaluation.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of context chunks for Ragas.")
    parser.add_argument("--skip-promptfoo", action="store_true", help="Skip promptfoo evaluation.")
    parser.add_argument("--skip-ragas", action="store_true", help="Skip Ragas evaluation.")

    args = parser.parse_args()

    exit_codes: List[int] = []
    if not args.skip_promptfoo:
        exit_codes.append(run_promptfoo_eval(args.promptfoo_config))
    if not args.skip_ragas:
        exit_codes.append(run_ragas_eval(args.ragas_script, args.filing_id, args.question, top_k=args.top_k))

    highest_exit = max(exit_codes) if exit_codes else 0
    if highest_exit == 0:
        logger.info("Evaluation completed successfully.")
    else:
        logger.error("Evaluation finished with failures. See previous logs for details.")
    return highest_exit


if __name__ == "__main__":
    raise SystemExit(main())

