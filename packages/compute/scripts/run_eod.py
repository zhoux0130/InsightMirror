"""Run EOD pipeline from command line.

Usage:
    python -m scripts.run_eod                    # CN market, today
    python -m scripts.run_eod 2026-03-15         # CN market, specific date
    python -m scripts.run_eod 2026-03-15 --market US  # US market
"""

import argparse
from datetime import date
from app.core.pipeline.orchestrator import PipelineOrchestrator
from app.db.connection import get_db


def main():
    parser = argparse.ArgumentParser(description="Run EOD pipeline")
    parser.add_argument("run_date", nargs="?", default=None, help="Date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--market", choices=["CN", "US"], default="CN", help="Market to run pipeline for")
    args = parser.parse_args()

    run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
    print(f"Running EOD pipeline for {run_date} (market={args.market})...")

    with get_db() as db:
        orchestrator = PipelineOrchestrator(db)
        results = orchestrator.run_eod(run_date, market=args.market)

    for step, result in results.items():
        status = result["status"]
        records = result.get("records", "N/A")
        error = result.get("error", "")
        print(f"  {step}: {status} (records: {records}) {error}")


if __name__ == "__main__":
    main()
