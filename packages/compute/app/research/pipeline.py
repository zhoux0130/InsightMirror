"""Map → extract → independent review → deterministic gates, resumable per stage."""
from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.research.entities import EntityMaster
from app.research.gates import build_theses, evaluate_claim
from app.research.llm import StructuredClient
from app.research.parser import render_blocks
from app.research.prompts import (
    DOCUMENT_PREAMBLE,
    EXTRACT_INSTRUCTIONS,
    MAP_INSTRUCTIONS,
    PROMPT_VERSION,
    REVIEW_SYSTEM,
)
from app.research.schemas import (
    Block,
    ClaimDraft,
    ClaimRecord,
    ClaimsOutput,
    ClaimVerdict,
    DocumentMap,
    ExtractionResult,
    ReviewOutput,
)

M = TypeVar("M", bound=BaseModel)
CACHED = {"type": "ephemeral"}
SUMMARY_ROLE = "助手摘要"


class SegmentationError(ValueError):
    """Model segments do not cover every block exactly once, in order."""


class ArtifactStore:
    """Stage results on disk, so a rerun only pays for calls that have not finished."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def get_or_run(self, name: str, model: type[M], produce: Callable[[], M]) -> M:
        path = self.root / f"{name}.json"
        if path.exists():
            return model.model_validate_json(path.read_text(encoding="utf-8"))
        result = produce()
        self.save(name, result)
        return result

    def save(self, name: str, value: BaseModel) -> None:
        path = self.root / f"{name}.json"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.root, delete=False) as tmp:
            tmp.write(value.model_dump_json(indent=2))
        os.replace(tmp.name, path)


def resolve_segments(document_map: DocumentMap, blocks: list[Block]) -> list[list[Block]]:
    index = {b.id: i for i, b in enumerate(blocks)}
    resolved: list[list[Block]] = []
    expected = 0
    for span in document_map.segments:
        if span.start_block not in index or span.end_block not in index:
            raise SegmentationError(f"unknown block in span {span.start_block}-{span.end_block}")
        start, end = index[span.start_block], index[span.end_block]
        if start != expected or end < start:
            raise SegmentationError(f"span {span.start_block}-{span.end_block} breaks continuity at {expected}")
        resolved.append(blocks[start : end + 1])
        expected = end + 1
    if expected != len(blocks):
        raise SegmentationError(f"segments stop at block {expected} of {len(blocks)}")
    return resolved


def _doc_block(document: str) -> dict:
    return {"type": "text", "text": DOCUMENT_PREAMBLE.format(document=document), "cache_control": CACHED}


def _extract_user(segment: list[Block], topic: str) -> str:
    return f"目标语义段（话题：{topic}）：\n{render_blocks(segment)}\n\n请抽取这一段的观点。"


def _review_user(segment: list[Block], claims: list[ClaimDraft]) -> str:
    fields = (
        "block_id", "entity", "attribution", "speech_act", "target", "direction", "time_phrase", "window_start",
        "window_end", "conclusion", "condition", "explicitness", "quote",
    )
    candidates = [{"index": i, **claim.model_dump(include=set(fields))} for i, claim in enumerate(claims)]
    return (
        f"原文：\n{render_blocks(segment)}\n\n候选观点：\n"
        f"{json.dumps(candidates, ensure_ascii=False, indent=1)}"
    )


def run_extraction(
    *,
    doc_id: str,
    doc_date: str,
    blocks: list[Block],
    client: StructuredClient,
    master: EntityMaster,
    store: ArtifactStore,
    workers: int = 4,
    max_segments: int | None = None,
) -> ExtractionResult:
    doc_block = _doc_block(render_blocks(blocks))

    document_map = store.get_or_run(
        "map",
        DocumentMap,
        lambda: client.complete(
            system=[doc_block, {"type": "text", "text": f"开课日期：{doc_date}\n\n{MAP_INSTRUCTIONS}"}],
            user="请按要求输出备忘录和语义分段。",
            output=DocumentMap,
        ),
    )
    segments = resolve_segments(document_map, blocks)

    memo = document_map.model_dump(exclude={"segments"})
    extract_system = [
        doc_block,
        {
            "type": "text",
            "text": (
                f"开课日期：{doc_date}\n\n全文备忘录：\n{json.dumps(memo, ensure_ascii=False)}\n\n"
                f"{EXTRACT_INSTRUCTIONS}"
            ),
            "cache_control": CACHED,
        },
    ]

    def process(index: int) -> list[ClaimRecord]:
        span, segment = document_map.segments[index], segments[index]
        summary_only = all(block.role == SUMMARY_ROLE for block in segment)
        if not span.has_investment_view or summary_only:
            return []
        drafts = store.get_or_run(
            f"extract_{index:03d}",
            ClaimsOutput,
            lambda: client.complete(system=extract_system, user=_extract_user(segment, span.topic), output=ClaimsOutput),
        ).claims
        if not drafts:
            return []
        verdicts = store.get_or_run(
            f"review_{index:03d}",
            ReviewOutput,
            lambda: client.complete(
                system=[{"type": "text", "text": REVIEW_SYSTEM}],
                user=_review_user(segment, drafts),
                output=ReviewOutput,
            ),
        ).verdicts
        by_index: dict[int, ClaimVerdict] = {v.index: v for v in verdicts}
        return [
            evaluate_claim(f"S{index:03d}-C{n:02d}", index, draft, segment, master, by_index.get(n))
            for n, draft in enumerate(drafts)
        ]

    indices = list(range(len(segments)))[: max_segments if max_segments is not None else None]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = [record for group in pool.map(process, indices) for record in group]

    result = ExtractionResult(
        doc_id=doc_id,
        doc_date=doc_date,
        model=client.model,
        prompt_version=PROMPT_VERSION,
        segments=document_map.segments,
        claims=records,
        theses=build_theses(records),
    )
    store.save("result", result)
    return result
