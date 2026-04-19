from __future__ import annotations

import argparse
import logging

from app.crawlers.state_grid.blob_store import BlobStore
from app.crawlers.state_grid.client import StateGridClient
from app.crawlers.state_grid.orchestrator import StateGridOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch State Grid raw notices into DB and OSS")
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    parser.add_argument("--limit-pages", type=int)
    parser.add_argument("--notice-id")
    parser.add_argument("--with-files", action="store_true")
    parser.add_argument("--replay-dead", action="store_true")
    parser.add_argument("--task-type")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with StateGridClient() as client:
        orchestrator = StateGridOrchestrator(client=client, blob_store=BlobStore())
        if args.replay_dead:
            orchestrator.replay_dead_tasks(task_type=args.task_type)
            return
        if args.notice_id:
            orchestrator.fetch_details_for_raws(limit=1, notice_ids=[args.notice_id])
            if args.with_files:
                orchestrator.fetch_files_for_raws(limit=1, notice_ids=[args.notice_id])
            return
        if args.mode == "full":
            orchestrator.run_full_pipeline(limit_pages=args.limit_pages)
            return
        orchestrator.fetch_notices_incremental()
        orchestrator.fetch_details_for_raws()
        orchestrator.fetch_files_for_raws()


if __name__ == "__main__":
    main()
