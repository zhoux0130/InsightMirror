from __future__ import annotations

import pytest

from app.research.schemas import ClaimRecord
from app.research.traps import TRAPS, run_traps
from tests.research.helpers import draft


def record(entity, *, page="10", role="讲者口述", counts=True, route="auto", markets=(), etype="上市公司", **overrides):
    return ClaimRecord(
        claim_id=f"{entity}-{page}", segment_index=0, draft=draft(entity=entity, **overrides), page=page, block_role=role,
        entity_canonical=entity, entity_type=etype, listing_markets=list(markets), counts_for_stance=counts,
        thesis_key="k", route=route, reasons=[],
    )


GOOD = [
    record("英伟达", window_start="2027", window_end="2028", direction="震荡上行"),
    record("英伟达", window_start="2029", window_end="2029", direction="负面(看跌)"),
    record("人形机器人", target="产业需求", direction="负面(看跌)", etype="行业"),
    record("SpaceX", condition="如期建成", signal_metric="GW", signal_due="2027-12", direction="正面(看涨)"),
    record("谷歌", target="公司经营", direction="正面(看涨)", change_type="作者确认无需修正", prior_view="7 月 30 日课程"),
]


def test_expected_output_passes_every_trap():
    assert all(v is None for v in run_traps(GOOD).values())


def test_each_trap_has_a_unique_id():
    assert len({t.id for t in TRAPS}) == len(TRAPS)


@pytest.mark.parametrize(
    ("trap_id", "bad"),
    [
        ("humanoid_market_vs_stock", record("人形机器人", etype="行业")),
        ("rejected_premise", record("ServiceNow")),
        ("rejected_premise", record("Palantir")),
        ("microsoft_mention", record("微软", page="29", target="竞争地位", direction="中性")),
        ("veiled_a_share", record("工业富联", page="14-15", markets=("A股",))),
        ("group_expansion", record("三星", counts=False)),
        ("summary_not_evidence", record("英伟达", role="助手摘要")),
    ],
)
def test_forbidden_claim_trips_the_trap(trap_id, bad):
    assert run_traps(GOOD + [bad])[trap_id] is not None


@pytest.mark.parametrize(
    ("trap_id", "remaining"),
    [
        ("nvda_time_legs", GOOD[1:]),
        ("spacex_condition", GOOD[:3] + GOOD[4:]),
        ("author_confirmation", GOOD[:4]),
    ],
)
def test_missing_required_claim_trips_the_trap(trap_id, remaining):
    assert run_traps(remaining)[trap_id] is not None


def test_rejected_claims_do_not_satisfy_required_traps():
    rejected = [c.model_copy(update={"route": "reject"}) for c in GOOD if c.entity_canonical == "SpaceX"]
    others = [c for c in GOOD if c.entity_canonical != "SpaceX"]
    assert run_traps(others + rejected)["spacex_condition"] is not None
