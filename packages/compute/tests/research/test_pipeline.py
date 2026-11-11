from __future__ import annotations

import threading

import openpyxl
import pytest

from app.research.entities import EntityMaster
from app.research.export import prefill_workbook
from app.research.llm import strict_schema
from app.research.pipeline import ArtifactStore, SegmentationError, resolve_segments, run_extraction
from app.research.schemas import ClaimsOutput, ClaimVerdict, DocumentMap, ReviewOutput, SegmentSpan
from tests.research.helpers import agree, block, draft

BLOCKS = [block("B001", "英伟达这家公司股价会大跌。"), block("B002", "闲谈。"), block("B003", "谷歌股价会涨。")]


def doc_map(spans):
    return DocumentMap(
        main_theses=[], glossary=[], groups=[], likely_transcription_errors=[],
        segments=[SegmentSpan(start_block=a, end_block=b, topic="t", has_investment_view=v) for a, b, v in spans],
    )


GOOD_MAP = doc_map([("B001", "B001", True), ("B002", "B002", False), ("B003", "B003", True)])


class FakeClient:
    model = "fake"

    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def complete(self, *, system, user, output):
        with self.lock:
            self.calls.append((output, system, user))
        if output is DocumentMap:
            return GOOD_MAP
        if output is ClaimsOutput:
            if "B001" in user:
                return ClaimsOutput(claims=[draft(), draft(quote="并不存在的引用")])
            return ClaimsOutput(claims=[draft(block_id="B003", entity="谷歌", quote="谷歌股价会涨", direction="正面(看涨)")])
        verdicts = [agree(0)]
        if "并不存在" in user:
            verdicts.append(ClaimVerdict(index=1, supported=False, wrong_fields=["conclusion"], note=""))
        return ReviewOutput(verdicts=verdicts)


def run(tmp_path, client):
    return run_extraction(
        doc_id="d", doc_date="2026-10-29", blocks=BLOCKS, client=client, master=EntityMaster.load(),
        store=ArtifactStore(tmp_path), workers=2,
    )


def test_segments_without_views_are_skipped(tmp_path):
    client = FakeClient()
    run(tmp_path, client)
    assert sum(1 for output, _, _ in client.calls if output is ClaimsOutput) == 2


def test_routes_and_theses(tmp_path):
    result = run(tmp_path, FakeClient())
    assert sorted(c.route for c in result.claims) == ["auto", "auto", "reject"]
    assert {t.entity for t in result.theses} == {"英伟达", "谷歌"}


def test_rerun_uses_saved_stages(tmp_path):
    run(tmp_path, FakeClient())
    second = FakeClient()
    run(tmp_path, second)
    assert second.calls == []


def test_review_never_sees_the_extraction_system_prompt(tmp_path):
    client = FakeClient()
    run(tmp_path, client)
    reviews = [system for output, system, _ in client.calls if output is ReviewOutput]
    assert reviews and all("<transcript>" not in part["text"] for system in reviews for part in system)


def test_document_is_the_shared_cached_prefix(tmp_path):
    client = FakeClient()
    run(tmp_path, client)
    prefixes = [system[0] for output, system, _ in client.calls if output in (DocumentMap, ClaimsOutput)]
    assert all(p == prefixes[0] for p in prefixes) and prefixes[0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.parametrize(
    "spans",
    [
        [("B001", "B002", True)],
        [("B002", "B003", True)],
        [("B001", "B002", True), ("B002", "B003", True)],
        [("B001", "B999", True)],
    ],
)
def test_bad_segmentation_is_refused(spans):
    with pytest.raises(SegmentationError):
        resolve_segments(doc_map(spans), BLOCKS)


def test_schema_is_closed_and_fully_required():
    schema = strict_schema(ClaimsOutput)
    claim = schema["$defs"]["ClaimDraft"]
    assert claim["additionalProperties"] is False
    assert set(claim["required"]) == set(claim["properties"])
    assert "title" not in claim


def template(path):
    workbook = openpyxl.Workbook()
    claims = workbook.active
    claims.title = "观点标注"
    claims["Y2"] = "=1+1"
    blocks = workbook.create_sheet("段落标注")
    for row, b in enumerate(BLOCKS, 2):
        blocks.cell(row, 1, b.id)
    workbook.save(path)


def test_prefill_puts_review_first_and_keeps_formulas(tmp_path):
    result = run(tmp_path / "store", FakeClient())
    flagged = result.claims[0].model_copy(update={"route": "review", "reasons": ["explicitness_inferred"]})
    result = result.model_copy(update={"claims": [result.claims[-1], flagged, *result.claims[1:-1]]})
    tpl, out = tmp_path / "t.xlsx", tmp_path / "o.xlsx"
    template(tpl)

    counts = prefill_workbook(result, tpl, out)

    assert counts == {"review": 1, "auto": 1, "reject": 1}
    book = openpyxl.load_workbook(out)
    claims, blocks = book["观点标注"], book["段落标注"]
    assert claims["AD2"].value.startswith("[待确认] explicitness_inferred")
    assert claims["C2"].value == "英伟达" and claims["C3"].value == "谷歌"
    assert claims["Y2"].value == "=1+1"
    assert (blocks["H2"].value, blocks["J3"].value) == ("是", "否")
    assert book["未通过校验"].max_row == 2


def _claim_json(**removed):
    data = draft().model_dump()
    for name in removed:
        data.pop(name)
    return data


def test_absent_optional_text_defaults_to_empty():
    parsed = ClaimsOutput.model_validate({"claims": [_claim_json(mechanism=1, prior_view=1)]})
    assert parsed.claims[0].mechanism == "" and parsed.claims[0].prior_view == ""


@pytest.mark.parametrize("field", ["quote", "entity", "direction", "target", "block_id"])
def test_absent_core_field_is_still_an_error(field):
    with pytest.raises(ValueError):
        ClaimsOutput.model_validate({"claims": [_claim_json(**{field: 1})]})


def test_summary_only_segments_are_not_extracted(tmp_path):
    class SummaryClient(FakeClient):
        def complete(self, *, system, user, output):
            if output is DocumentMap:
                self.calls.append((output, system, user))
                return doc_map([("B001", "B001", True)])
            return super().complete(system=system, user=user, output=output)

    client = SummaryClient()
    result = run_extraction(
        doc_id="d", doc_date="2026-10-29", blocks=[block("B001", "摘要。", role="助手摘要")], client=client,
        master=EntityMaster.load(), store=ArtifactStore(tmp_path),
    )
    assert result.claims == [] and [output for output, _, _ in client.calls] == [DocumentMap]
