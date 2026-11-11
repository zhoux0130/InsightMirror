"""Prefill a copy of the annotation workbook; review-routed claims come first."""
from __future__ import annotations

from pathlib import Path

import openpyxl

from app.research.schemas import ExtractionResult

CLAIM_SHEET = "观点标注"
BLOCK_SHEET = "段落标注"
FIRST_ROW = 2
CLAIM_CAPACITY = 400
REJECT_SHEET = "未通过校验"

CLAIM_COLUMNS = {
    2: "block_id", 4: "attribution", 5: "speech_act", 6: "target", 7: "direction", 8: "strength", 9: "time_phrase",
    10: "window_start", 11: "window_end", 12: "time_precision", 13: "conclusion", 14: "premise", 15: "mechanism",
    16: "result", 17: "condition", 18: "signal_metric", 19: "signal_threshold", 20: "signal_due", 21: "signal_means",
    22: "action", 23: "explicitness", 24: "quote", 28: "prior_view", 29: "change_type",
}
ENTITY_COLUMN, NOTE_COLUMN = 3, 30
SEGMENT_START_COLUMN, SEGMENT_TOPIC_COLUMN, HAS_VIEW_COLUMN = 8, 9, 10


class CapacityError(ValueError):
    """More claims than the template has rows for."""


def prefill_workbook(result: ExtractionResult, template: Path, output: Path) -> dict[str, int]:
    workbook = openpyxl.load_workbook(template)
    claims_sheet, blocks_sheet = workbook[CLAIM_SHEET], workbook[BLOCK_SHEET]

    kept = [c for c in result.claims if c.route != "reject"]
    if len(kept) > CLAIM_CAPACITY:
        raise CapacityError(f"{len(kept)} claims exceed {CLAIM_CAPACITY} rows")
    kept.sort(key=lambda c: (c.route != "review", c.draft.block_id, c.claim_id))

    for row, claim in enumerate(kept, FIRST_ROW):
        for column, name in CLAIM_COLUMNS.items():
            value = getattr(claim.draft, name)
            claims_sheet.cell(row, column, value if value != "" else None)
        claims_sheet.cell(row, ENTITY_COLUMN, claim.entity_canonical)
        prefix = "[待确认] " + "；".join(claim.reasons) if claim.route == "review" else "[自动通过]"
        claims_sheet.cell(row, NOTE_COLUMN, f"{prefix} ({claim.claim_id})")

    rows_by_block = {
        blocks_sheet.cell(r, 1).value: r for r in range(FIRST_ROW, blocks_sheet.max_row + 1)
    }
    for span in result.segments:
        row = rows_by_block[span.start_block]
        blocks_sheet.cell(row, SEGMENT_START_COLUMN, "是")
        blocks_sheet.cell(row, SEGMENT_TOPIC_COLUMN, span.topic)
        blocks_sheet.cell(row, HAS_VIEW_COLUMN, "是" if span.has_investment_view else "否")

    rejected = [c for c in result.claims if c.route == "reject"]
    sheet = workbook.create_sheet(REJECT_SHEET)
    sheet.append(["claim_id", "block_id", "entity", "conclusion", "quote", "reasons"])
    for claim in rejected:
        sheet.append(
            [claim.claim_id, claim.draft.block_id, claim.draft.entity, claim.draft.conclusion, claim.draft.quote,
             "；".join(claim.reasons)]
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    return {
        "review": sum(c.route == "review" for c in kept),
        "auto": sum(c.route == "auto" for c in kept),
        "reject": len(rejected),
    }
