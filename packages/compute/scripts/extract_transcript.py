#!/usr/bin/env python3
"""Extract investment claims from a course transcript PDF.

    python scripts/extract_transcript.py parse <pdf>
    python scripts/extract_transcript.py run <pdf> --model claude|glm|kimi [--max-segments N]
    python scripts/extract_transcript.py export <pdf> --model claude --template T.xlsx --out O.xlsx
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.research.export import prefill_workbook  # noqa: E402
from app.research.ledger import load_models  # noqa: E402
from app.research.parser import extract_text, parse_transcript  # noqa: E402
from app.research.prompts import PROMPT_VERSION  # noqa: E402
from app.research.runs import execute_run, research_root  # noqa: E402
from app.research.schemas import ExtractionResult  # noqa: E402


def doc_date_from(pdf: Path) -> str:
    match = re.search(r"(\d{4})(\d{2})(\d{2})", pdf.name)
    if not match:
        raise SystemExit(f"cannot read a date from {pdf.name}; rename the file or add the date to its name")
    return "-".join(match.groups())


def artifact_dir(doc_date: str, model_id: str) -> Path:
    return research_root(settings.raw_data_dir) / doc_date / PROMPT_VERSION / model_id


def load_api_key(env_name: str) -> str:
    """Worktrees have no .env of their own, so also look in the main checkout."""
    if os.environ.get(env_name):
        return os.environ[env_name]
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"], capture_output=True, text=True
    ).stdout.strip()
    candidates = [Path.cwd() / ".env", *[p / ".env" for p in Path.cwd().parents]]
    if common:
        candidates.append((Path.cwd() / common).resolve().parent / ".env")
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{env_name}=") and line.split("=", 1)[1].strip():
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit(f"{env_name} not found in the environment or .env")


def cmd_parse(pdf: Path) -> None:
    blocks = parse_transcript(extract_text(pdf))
    print(json.dumps({"blocks": len(blocks), "chars": sum(len(b.text) for b in blocks)}, ensure_ascii=False))


def cmd_run(pdf: Path, model_id: str, max_segments: int | None, workers: int) -> None:
    config = load_models()[model_id]
    doc_date = doc_date_from(pdf)
    result, metrics = execute_run(
        model_id=model_id,
        api_key=load_api_key(config.key_env),
        doc_id=doc_date,
        doc_date=doc_date,
        blocks=parse_transcript(extract_text(pdf)),
        root=research_root(settings.raw_data_dir),
        workers=workers,
        max_segments=max_segments,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"result: {artifact_dir(result.doc_id, model_id) / 'result.json'}")


def cmd_export(pdf: Path, model_id: str, template: Path, out: Path) -> None:
    path = artifact_dir(doc_date_from(pdf), model_id) / "result.json"
    result = ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
    print(json.dumps(prefill_workbook(result, template, out), ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("parse").add_argument("pdf", type=Path)
    run = sub.add_parser("run")
    run.add_argument("pdf", type=Path)
    run.add_argument("--model", choices=sorted(load_models()), required=True)
    run.add_argument("--max-segments", type=int)
    run.add_argument("--workers", type=int, default=4)
    export = sub.add_parser("export")
    export.add_argument("pdf", type=Path)
    export.add_argument("--model", choices=sorted(load_models()), required=True)
    export.add_argument("--template", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "parse":
        cmd_parse(args.pdf)
    elif args.command == "run":
        cmd_run(args.pdf, args.model, args.max_segments, args.workers)
    else:
        cmd_export(args.pdf, args.model, args.template, args.out)


if __name__ == "__main__":
    main()
