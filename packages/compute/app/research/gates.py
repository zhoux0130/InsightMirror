"""Deterministic checks that decide whether a model-drafted claim can be trusted."""
from __future__ import annotations

import re
from collections import defaultdict

from app.research.entities import EntityMaster, squash
from app.research.schemas import Block, ClaimDraft, ClaimRecord, ClaimVerdict, Thesis

MAX_QUOTE_CHARS = 200
WINDOW = re.compile(r"^(\d{4})(?:-Q([1-4])|-(0[1-9]|1[0-2]))?$")
PRICE_LANGUAGE = re.compile(r"股价|股票|炒股|涨|跌|买|卖|抛|抄底|入场|进场|投资|持仓|回报|估值|市值|归零|上车|追顶")
CONDITION_LANGUAGE = re.compile(r"如果|假如|要是|只要|一旦|倘若")
STANCE_ATTRIBUTIONS = {"老师本人", "转述并认同"}
STANCE_ACTS = {"判断", "行动建议", "自我修正"}


def window_order(value: str) -> tuple[int, int] | None:
    match = WINDOW.match(value)
    if not match:
        return None
    year, quarter, month = match.groups()
    if quarter:
        return int(year), (int(quarter) - 1) * 3 + 1
    return int(year), int(month) if month else 1


def _window_reasons(draft: ClaimDraft) -> list[str]:
    reasons: list[str] = []
    orders = {}
    for name, value in (("start", draft.window_start), ("end", draft.window_end)):
        if value:
            orders[name] = window_order(value)
            if orders[name] is None:
                reasons.append(f"window_{name}_format")
    if orders.get("start") and orders.get("end") and orders["start"] > orders["end"]:
        reasons.append("window_reversed")
    if (draft.window_start or draft.window_end) and not draft.time_phrase:
        reasons.append("window_without_time_phrase")
    return reasons


def _locate_block(draft: ClaimDraft, segment: list[Block]) -> tuple[Block | None, bool]:
    wanted = squash(draft.quote)
    if not wanted:
        return None, False
    for block in segment:
        if block.id == draft.block_id and wanted in squash(block.text):
            return block, False
    matches = [b for b in segment if wanted in squash(b.text)]
    return (matches[0], True) if len(matches) == 1 else (None, False)


def evaluate_claim(
    claim_id: str,
    segment_index: int,
    draft: ClaimDraft,
    segment: list[Block],
    master: EntityMaster,
    verdict: ClaimVerdict | None,
) -> ClaimRecord:
    review: list[str] = []
    reject: list[str] = []

    block, moved = _locate_block(draft, segment)
    if block is None:
        reject.append("quote_not_found_in_segment")
    elif moved:
        draft = draft.model_copy(update={"block_id": block.id})
        review.append("block_id_corrected")
    if len(draft.quote) > MAX_QUOTE_CHARS:
        reject.append("quote_too_long")

    segment_text = "".join(b.text for b in segment)
    entity = master.resolve(draft.entity)
    if entity is None:
        review.append("entity_unresolved")
    forms = entity.surface_forms if entity else tuple(p.strip() for p in draft.entity.split("/"))
    if not EntityMaster.named_in(forms, segment_text):
        review.append("entity_not_named_in_segment")

    if draft.explicitness == "推断":
        review.append("explicitness_inferred")
    if draft.target in ("股价", "估值") and not PRICE_LANGUAGE.search(draft.quote):
        review.append("price_target_without_price_language")
    if CONDITION_LANGUAGE.search(draft.quote) and not draft.condition:
        review.append("conditional_quote_without_condition")
    if draft.speech_act == "检验标准" and not draft.signal_metric:
        review.append("check_without_metric")
    if draft.change_type not in ("", "首次提出") and not draft.prior_view:
        review.append("change_without_prior_view")
    if draft.time_phrase and squash(draft.time_phrase) not in squash(segment_text):
        review.append("time_phrase_not_in_text")
    review.extend(_window_reasons(draft))

    role = block.role if block else ""
    if role == "提问人" and draft.attribution in STANCE_ATTRIBUTIONS:
        review.append("question_block_attributed_to_teacher")
    if role == "助手摘要" and draft.attribution != "助手摘要":
        review.append("summary_block_misattributed")

    if verdict is None:
        review.append("independent_review_missing")
    elif not verdict.supported:
        review.append("independent_review_disagrees:" + ",".join(verdict.wrong_fields or ["unspecified"]))

    counts = (
        draft.attribution in STANCE_ATTRIBUTIONS
        and draft.speech_act in STANCE_ACTS
        and draft.direction != "不适用"
        and role != "助手摘要"
        and not reject
    )
    canonical = entity.name if entity else draft.entity
    return ClaimRecord(
        claim_id=claim_id,
        segment_index=segment_index,
        draft=draft,
        page=block.page if block else "",
        block_role=role,
        entity_canonical=canonical,
        entity_type=entity.type if entity else "",
        listing_markets=list(entity.markets) if entity else [],
        counts_for_stance=counts,
        thesis_key=f"{canonical}|{draft.target}|{draft.window_start}~{draft.window_end}",
        route="reject" if reject else ("review" if review else "auto"),
        reasons=reject + review,
    )


def build_theses(claims: list[ClaimRecord]) -> list[Thesis]:
    grouped: dict[str, list[ClaimRecord]] = defaultdict(list)
    for claim in claims:
        if claim.counts_for_stance:
            grouped[claim.thesis_key].append(claim)

    theses: list[Thesis] = []
    for key, members in grouped.items():
        members.sort(key=lambda c: c.draft.block_id)
        corrections = [c for c in members if c.draft.speech_act == "自我修正"]
        current = (corrections or members)[-1]
        directions = sorted({c.draft.direction for c in members})
        first = members[0]
        theses.append(
            Thesis(
                key=key,
                entity=first.entity_canonical,
                target=first.draft.target,
                window=f"{first.draft.window_start}~{first.draft.window_end}",
                claim_ids=[c.claim_id for c in members],
                directions=directions,
                current_direction=current.draft.direction,
                current_conclusion=current.draft.conclusion,
                needs_review=len(directions) > 1 or any(c.route == "review" for c in members),
            )
        )
    return sorted(theses, key=lambda t: t.key)
