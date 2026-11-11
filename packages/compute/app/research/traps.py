"""Regression traps found by reading the 2026-10-29 transcript.

They only catch known failure modes; passing them does not prove full accuracy.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.research.entities import squash
from app.research.schemas import ClaimRecord

Check = Callable[[list[ClaimRecord]], str | None]
NEGATIVE = "负面(看跌)"
PRICE_TARGETS = ("股价", "估值")


def _active(claims: list[ClaimRecord]) -> list[ClaimRecord]:
    return [c for c in claims if c.route != "reject"]


def _stance(claims: list[ClaimRecord]) -> list[ClaimRecord]:
    return [c for c in claims if c.counts_for_stance]


def _first_page(claim: ClaimRecord) -> int:
    return int(claim.page.split("-")[0]) if claim.page else 0


def nvda_has_time_legs(claims: list[ClaimRecord]) -> str | None:
    legs = [c for c in _stance(claims) if c.entity_canonical == "英伟达" and c.draft.target == "股价"]
    windows = {(c.draft.window_start, c.draft.window_end) for c in legs}
    directions = {c.draft.direction for c in legs}
    if len(windows) < 2 or len(directions) < 2:
        return f"expected multiple time legs, got windows={sorted(windows)} directions={sorted(directions)}"
    return None


def humanoid_market_is_not_stock(claims: list[ClaimRecord]) -> str | None:
    bad = [
        c.claim_id
        for c in _stance(claims)
        if c.entity_canonical == "人形机器人" and c.draft.target in PRICE_TARGETS and c.draft.direction == NEGATIVE
    ]
    return f"market view recorded as bearish stock view: {bad}" if bad else None


def rejected_premise_is_not_bearish(claims: list[ClaimRecord]) -> str | None:
    bad = [
        c.claim_id
        for c in _stance(claims)
        if c.entity_canonical in ("ServiceNow", "Palantir")
        and c.draft.target in PRICE_TARGETS
        and c.draft.direction == NEGATIVE
    ]
    return f"rejected question premise recorded as bearish: {bad}" if bad else None


def microsoft_mention_is_not_view(claims: list[ClaimRecord]) -> str | None:
    bad = [c.claim_id for c in _stance(claims) if c.entity_canonical == "微软" and 29 <= _first_page(c) <= 30]
    return f"explanatory mention recorded as view: {bad}" if bad else None


def spacex_keeps_condition(claims: list[ClaimRecord]) -> str | None:
    ok = any(
        c.entity_canonical == "SpaceX" and c.draft.condition and c.draft.signal_metric and c.draft.signal_due
        for c in _active(claims)
    )
    return None if ok else "no SpaceX claim with condition, metric and due date"


def veiled_a_share_passage_names_no_stock(claims: list[ClaimRecord]) -> str | None:
    bad = [
        c.claim_id
        for c in _stance(claims)
        if "A股" in c.listing_markets and c.entity_type == "上市公司" and 14 <= _first_page(c) <= 15
    ]
    return f"individual A-share stance invented from veiled passage: {bad}" if bad else None


def group_is_not_expanded(claims: list[ClaimRecord]) -> str | None:
    forbidden = ("三星", "海力士", "美光", "Samsung", "Hynix", "Micron")
    bad = [c.claim_id for c in _active(claims) if any(name.lower() in c.draft.entity.lower() for name in forbidden)]
    return f"unnamed group members invented: {bad}" if bad else None


def author_confirmation_is_tracked(claims: list[ClaimRecord]) -> str | None:
    ok = any(
        c.entity_canonical == "谷歌" and c.draft.change_type == "作者确认无需修正" and "7月30" in squash(c.draft.prior_view)
        for c in _active(claims)
    )
    return None if ok else "author's confirmation of the 7/30 view was not captured"


def summary_is_not_evidence(claims: list[ClaimRecord]) -> str | None:
    bad = [c.claim_id for c in _stance(claims) if c.block_role == "助手摘要"]
    return f"assistant summary counted as stance: {bad}" if bad else None


@dataclass(frozen=True)
class Trap:
    id: str
    description: str
    check: Check


TRAPS = [
    Trap("nvda_time_legs", "同一股票不同时间段不能压成一个结论", nvda_has_time_legs),
    Trap("humanoid_market_vs_stock", "“市场不行”不等于“股价不行”", humanoid_market_is_not_stock),
    Trap("rejected_premise", "否定提问前提不等于看空", rejected_premise_is_not_bearish),
    Trap("microsoft_mention", "用公司解释数据不等于对公司有观点", microsoft_mention_is_not_view),
    Trap("spacex_condition", "条件和检验指标不能丢", spacex_keeps_condition),
    Trap("veiled_a_share", "含蓄的 A 股段落不能编出个股观点", veiled_a_share_passage_names_no_stock),
    Trap("group_expansion", "分组观点不能扩展到未点名公司", group_is_not_expanded),
    Trap("author_confirmation", "作者确认历史判断要记录沿革", author_confirmation_is_tracked),
    Trap("summary_not_evidence", "助手摘要不算老师观点", summary_is_not_evidence),
]


def run_traps(claims: list[ClaimRecord]) -> dict[str, str | None]:
    return {trap.id: trap.check(claims) for trap in TRAPS}
