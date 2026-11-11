"""Data contracts. Literal values must stay identical to the annotation workbook's 字典 sheet."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

Attribution = Literal["老师本人", "转述并认同", "转述并反驳", "提问人假设", "助手摘要"]
SpeechAct = Literal["判断", "事实证据", "行动建议", "检验标准", "自我修正", "类比"]
Target = Literal["股价", "估值", "公司经营", "信用偿债", "产业需求", "竞争地位", "其他"]
Direction = Literal["正面(看涨)", "负面(看跌)", "震荡上行", "震荡", "中性", "不适用"]
Strength = Literal["肯定", "较确定", "可能", "存疑", ""]
TimePrecision = Literal["季度或月", "年", "年份区间", "模糊(如未来几年)", "未说明"]
SignalMeans = Literal["验证", "证伪", "需结合判断", ""]
Explicitness = Literal["明说", "强暗示", "推断"]
ChangeType = Literal[
    "首次提出", "重申", "强化", "削弱", "时间推移", "条件变化", "反转", "作者确认无需修正", "已验证", "已证伪", ""
]
Route = Literal["auto", "review", "reject"]
ReviewField = Literal["attribution", "speech_act", "target", "direction", "window", "condition", "entity", "conclusion"]
OPTIONAL_CLAIM_TEXT = (
    "strength", "time_phrase", "window_start", "window_end", "premise", "mechanism", "result", "condition",
    "signal_metric", "signal_threshold", "signal_due", "signal_means", "action", "prior_view", "change_type",
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Block(Strict):
    id: str
    page: str
    section: str
    role: str
    qa_id: str
    image_before: bool
    text: str


class GlossaryEntry(Strict):
    term: str
    meaning: str


class EntityGroup(Strict):
    group: str
    members_named_in_text: list[str]


class SegmentSpan(Strict):
    start_block: str
    end_block: str
    topic: str
    has_investment_view: bool


class DocumentMap(Strict):
    main_theses: list[str]
    glossary: list[GlossaryEntry]
    groups: list[EntityGroup]
    likely_transcription_errors: list[GlossaryEntry]
    segments: list[SegmentSpan]


class ClaimDraft(Strict):
    block_id: str
    entity: str
    attribution: Attribution
    speech_act: SpeechAct
    target: Target
    direction: Direction
    strength: Strength
    time_phrase: str
    window_start: str
    window_end: str
    time_precision: TimePrecision
    conclusion: str
    premise: str
    mechanism: str
    result: str
    condition: str
    signal_metric: str
    signal_threshold: str
    signal_due: str
    signal_means: SignalMeans
    action: str
    explicitness: Explicitness
    quote: str
    prior_view: str
    change_type: ChangeType


class ClaimsOutput(Strict):
    claims: list[ClaimDraft]

    @model_validator(mode="before")
    @classmethod
    def fill_absent_optional_text(cls, data: Any) -> Any:
        """Providers without strict schemas may omit a field that simply was not discussed."""
        if isinstance(data, dict) and isinstance(data.get("claims"), list):
            data["claims"] = [
                {**dict.fromkeys(OPTIONAL_CLAIM_TEXT, ""), **claim} if isinstance(claim, dict) else claim
                for claim in data["claims"]
            ]
        return data


class ClaimVerdict(Strict):
    index: int
    supported: bool
    wrong_fields: list[ReviewField]
    note: str


class ReviewOutput(Strict):
    verdicts: list[ClaimVerdict]


class ClaimRecord(Strict):
    claim_id: str
    segment_index: int
    draft: ClaimDraft
    page: str
    block_role: str
    entity_canonical: str
    entity_type: str
    listing_markets: list[str]
    counts_for_stance: bool
    thesis_key: str
    route: Route
    reasons: list[str]


class Thesis(Strict):
    key: str
    entity: str
    target: str
    window: str
    claim_ids: list[str]
    directions: list[str]
    current_direction: str
    current_conclusion: str
    needs_review: bool


class ExtractionResult(Strict):
    doc_id: str
    doc_date: str
    model: str
    prompt_version: str
    segments: list[SegmentSpan]
    claims: list[ClaimRecord]
    theses: list[Thesis]
