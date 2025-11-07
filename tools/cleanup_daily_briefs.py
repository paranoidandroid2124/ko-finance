"""Script to clean up daily brief artifacts using the Celery task."""

from __future__ import annotations

import argparse

from parse.tasks import cleanup_daily_briefs


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke cleanup for daily brief artifacts.")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=7,
        help="Number of days to retain daily brief outputs before deletion (default: 7).",
    )
    args = parser.parse_args()
    result = cleanup_daily_briefs(retention_days=args.retention_days)
    print("Cleanup result:", result)


if __name__ == "__main__":
    main()
