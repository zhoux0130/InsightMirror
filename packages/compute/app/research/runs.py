"""One model run over one document: artifacts, ledger entries and quality metrics."""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from app.research.entities import EntityMaster
from app.research.ledger import Ledger, MeteredClient, ModelConfig, load_models
from app.research.llm import AnthropicProvider, OpenAICompatibleProvider, Provider
from app.research.pipeline import ArtifactStore, run_extraction
from app.research.prompts import PROMPT_VERSION
from app.research.schemas import Block, ExtractionResult
from app.research.traps import TRAPS, run_traps

LEDGER_NAME = "ledger.sqlite"


def research_root(raw_data_dir: str) -> Path:
    return Path(raw_data_dir) / "research"


def ledger_at(root: Path) -> Ledger:
    return Ledger(root / LEDGER_NAME)


def build_provider(config: ModelConfig, api_key: str) -> Provider:
    if config.kind == "anthropic":
        return AnthropicProvider(config.model, api_key)
    return OpenAICompatibleProvider(config.model, api_key, config.base_url, stage_options=config.stage_options)


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def run_metrics(result: ExtractionResult) -> dict[str, Any]:
    claims = result.claims
    total = len(claims)
    trap_results = run_traps(claims)
    failed = {name: detail for name, detail in trap_results.items() if detail is not None}
    quote_failures = sum("quote_not_found_in_segment" in c.reasons for c in claims)
    disagreements = sum(any(r.startswith("independent_review_disagrees") for r in c.reasons) for c in claims)
    return {
        "claims": total,
        "auto": sum(c.route == "auto" for c in claims),
        "review": sum(c.route == "review" for c in claims),
        "reject": sum(c.route == "reject" for c in claims),
        "theses": len(result.theses),
        "entities": len({c.entity_canonical for c in claims if c.route != "reject"}),
        "quote_failure_rate": _rate(quote_failures, total),
        "review_disagreement_rate": _rate(disagreements, total),
        "traps_passed": len(TRAPS) - len(failed),
        "traps_total": len(TRAPS),
        "traps_failed": failed,
    }


def execute_run(
    *,
    model_id: str,
    api_key: str,
    doc_id: str,
    doc_date: str,
    blocks: list[Block],
    root: Path,
    workers: int = 4,
    max_segments: int | None = None,
    provider: Provider | None = None,
) -> tuple[ExtractionResult, dict[str, Any]]:
    config = load_models()[model_id]
    ledger = ledger_at(root)
    run_id = f"{int(time.time())}-{model_id}-{uuid.uuid4().hex[:6]}"
    partial = max_segments is not None
    ledger.start_run(run_id=run_id, doc_id=doc_id, config=config, prompt_version=PROMPT_VERSION, partial=partial)

    store_dir = root / doc_id / PROMPT_VERSION / model_id
    client = MeteredClient(provider or build_provider(config, api_key), config, ledger, run_id)
    try:
        result = run_extraction(
            doc_id=doc_id, doc_date=doc_date, blocks=blocks, client=client, master=EntityMaster.load(),
            store=ArtifactStore(store_dir), workers=workers, max_segments=max_segments,
        )
    except Exception as error:
        ledger.finish_run(run_id, status="error", error=f"{type(error).__name__}: {error}")
        raise
    metrics = run_metrics(result)
    ledger.finish_run(run_id, status="ok", result_path=str((store_dir / "result.json").relative_to(root)), metrics=metrics)
    return result, metrics


def claims_for_document(ledger: Ledger, doc_id: str) -> dict[str, Any]:
    """Every claim with its verbatim quote, for the local console only (contains course text)."""
    rows = []
    feedback = ledger.feedback(doc_id)
    for model_id, path in sorted(ledger.latest_results(doc_id).items()):
        result = ExtractionResult.model_validate_json(Path(path).read_text(encoding="utf-8"))
        for claim in result.claims:
            d = claim.draft
            mine = feedback.get((model_id, claim.claim_id))
            if mine and mine["quote"] != d.quote:  # a rerun reused the id for a different claim
                mine = None
            rows.append({
                "model_id": model_id,
                "claim_id": claim.claim_id,
                "entity": claim.entity_canonical,
                "markets": claim.listing_markets,
                "target": d.target,
                "direction": d.direction,
                "strength": d.strength,
                "attribution": d.attribution,
                "speech_act": d.speech_act,
                "window": f"{d.window_start}~{d.window_end}" if (d.window_start or d.window_end) else "",
                "time_phrase": d.time_phrase,
                "conclusion": d.conclusion,
                "mechanism": d.mechanism,
                "condition": d.condition,
                "signal": "；".join(x for x in (d.signal_metric, d.signal_threshold, d.signal_due) if x),
                "quote": d.quote,
                "page": claim.page,
                "block_id": d.block_id,
                "counts_for_stance": claim.counts_for_stance,
                "route": claim.route,
                "reasons": claim.reasons,
                "feedback": mine,
            })
    return {"doc_id": doc_id, "claims": rows}


def compare_models(ledger: Ledger, doc_id: str) -> dict[str, Any]:
    """Each model's direction per entity and judgment target, without exposing course text."""
    paths = ledger.latest_results(doc_id)
    models = sorted(paths)
    table: dict[str, dict[str, set[str]]] = {}
    for model_id, path in paths.items():
        result = ExtractionResult.model_validate_json(Path(path).read_text(encoding="utf-8"))
        for thesis in result.theses:
            key = f"{thesis.entity}｜{thesis.target}"
            table.setdefault(key, {}).setdefault(model_id, set()).update(thesis.directions)
    rows = []
    for key in sorted(table):
        cells = {m: sorted(table[key].get(m, set())) for m in models}
        present = [tuple(v) for v in cells.values() if v]
        rows.append({
            "key": key,
            "cells": cells,
            "status": "仅部分模型提到" if len(present) < len(models) else ("一致" if len(set(present)) == 1 else "有分歧"),
        })
    return {"doc_id": doc_id, "models": models, "rows": rows}
