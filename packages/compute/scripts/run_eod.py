"""Run EOD pipeline from command line."""

import sys
from datetime import date
from app.core.pipeline.orchestrator import PipelineOrchestrator
from app.db.connection import get_db


def main():
    run_date = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    print(f"Running EOD pipeline for {run_date}...")

    with get_db() as db:
        orchestrator = PipelineOrchestrator(db)
        results = orchestrator.run_eod(run_date)

    for step, result in results.items():
        status = result["status"]
        records = result.get("records", "N/A")
        error = result.get("error", "")
        print(f"  {step}: {status} (records: {records}) {error}")


if __name__ == "__main__":
    main()
