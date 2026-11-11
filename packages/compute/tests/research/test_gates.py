from __future__ import annotations

import pytest

from app.research.entities import EntityMaster
from app.research.gates import build_theses, evaluate_claim
from app.research.schemas import ClaimVerdict
from tests.research.helpers import agree, block, draft

MASTER = EntityMaster.load()
NAMED = block(text="英伟达这家公司股价会大跌。")


def run(claim, segment=None, verdict=agree()):
    return evaluate_claim("C1", 0, claim, segment or [NAMED], MASTER, verdict)


def test_clean_claim_is_auto_and_counts():
    record = run(draft())
    assert (record.route, record.counts_for_stance, record.reasons) == ("auto", True, [])
    assert record.listing_markets == ["美股"]


def test_quote_matching_ignores_whitespace():
    assert run(draft(quote="这家公司 股价\n会大跌")).route == "auto"


def test_paraphrased_quote_is_rejected_and_never_counts():
    record = run(draft(quote="公司股价要暴跌"))
    assert record.route == "reject" and not record.counts_for_stance


def test_overlong_quote_is_rejected():
    long_text = "英伟达" + "股" * 300
    assert run(draft(quote=long_text), [block(text=long_text)]).route == "reject"


def test_wrong_block_id_is_repaired_and_flagged():
    other = block("B002", "英伟达完全不同的一句。")
    record = run(draft(block_id="B002"), [NAMED, other])
    assert record.draft.block_id == "B001" and "block_id_corrected" in record.reasons


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"explicitness": "推断"}, "explicitness_inferred"),
        ({"speech_act": "检验标准"}, "check_without_metric"),
        ({"change_type": "反转"}, "change_without_prior_view"),
        ({"window_start": "明年", "time_phrase": "股价"}, "window_start_format"),
        ({"window_start": "2029"}, "window_without_time_phrase"),
        ({"window_start": "2030", "window_end": "2029", "time_phrase": "股价"}, "window_reversed"),
        ({"time_phrase": "后年"}, "time_phrase_not_in_text"),
    ],
)
def test_review_routes(overrides, reason):
    record = run(draft(**overrides))
    assert record.route == "review" and reason in record.reasons


def test_stock_target_needs_price_language():
    segment = [block(text="英伟达的市场需求不行。")]
    record = run(draft(quote="市场需求不行"), segment)
    assert "price_target_without_price_language" in record.reasons


def test_condition_in_quote_must_be_captured():
    segment = [block(text="英伟达如果做到，股价会涨。")]
    assert "conditional_quote_without_condition" in run(draft(quote="如果做到，股价会涨"), segment).reasons


def test_unknown_entity_goes_to_review():
    assert "entity_unresolved" in run(draft(entity="某未知公司")).reasons


def test_unnamed_entity_goes_to_review():
    segment = [block(text="这些韩国公司股价会大跌。")]
    record = run(draft(entity="美光", quote="股价会大跌"), segment)
    assert "entity_not_named_in_segment" in record.reasons


def test_alias_resolves_to_canonical_name():
    segment = [block(text="脸书股价会大跌。")]
    assert run(draft(entity="脸书", quote="股价会大跌"), segment).entity_canonical == "Meta"


def test_question_block_cannot_be_teacher_view():
    segment = [block(text="英伟达股价会大跌吗？", role="提问人")]
    assert "question_block_attributed_to_teacher" in run(draft(quote="股价会大跌"), segment).reasons


@pytest.mark.parametrize(
    "overrides",
    [
        {"attribution": "提问人假设"},
        {"attribution": "转述并反驳"},
        {"speech_act": "事实证据"},
        {"speech_act": "类比"},
        {"direction": "不适用"},
    ],
)
def test_non_stance_claims_do_not_count(overrides):
    assert not run(draft(**overrides)).counts_for_stance


def test_summary_block_never_counts():
    segment = [block(text="英伟达这家公司股价会大跌。", role="助手摘要")]
    assert not run(draft(), segment).counts_for_stance


def test_independent_disagreement_and_missing_review_go_to_review():
    disagree = ClaimVerdict(index=0, supported=False, wrong_fields=["target"], note="偷换对象")
    assert "independent_review_disagrees:target" in run(draft(), verdict=disagree).reasons
    assert "independent_review_missing" in run(draft(), verdict=None).reasons


def _thesis_claim(claim_id, block_id="B001", **overrides):
    segment = [block(block_id, "英伟达这家公司股价会大跌。2029")]
    params = dict(block_id=block_id, window_start="2029", window_end="2029", time_phrase="2029")
    params.update(overrides)
    return evaluate_claim(claim_id, 0, draft(**params), segment, MASTER, agree())


def test_different_windows_are_separate_theses():
    theses = build_theses([_thesis_claim("A"), _thesis_claim("B", window_start="", window_end="", time_phrase="")])
    assert len(theses) == 2 and not any(t.needs_review for t in theses)


def test_conflict_in_one_thesis_needs_review():
    theses = build_theses([_thesis_claim("A"), _thesis_claim("B", "B002", direction="正面(看涨)")])
    assert len(theses) == 1 and theses[0].needs_review


def test_self_correction_is_current_even_if_not_last():
    theses = build_theses(
        [
            _thesis_claim("A", "B001", speech_act="自我修正", conclusion="修正后"),
            _thesis_claim("B", "B002", conclusion="后续重复"),
        ]
    )
    assert theses[0].current_conclusion == "修正后"


def test_unresolved_compound_name_matches_any_part():
    segment = [block(text="算力股价会大跌。")]
    record = run(draft(entity="算力 / AI 基建", quote="股价会大跌"), segment)
    assert "entity_not_named_in_segment" not in record.reasons
