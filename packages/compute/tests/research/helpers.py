"""Small synthetic inputs; tests must not depend on the paid course PDF."""
from __future__ import annotations

from app.research.schemas import Block, ClaimDraft, ClaimVerdict


def block(block_id="B001", text="这家公司股价会大跌。", page="1", role="讲者口述", section="课程文字稿") -> Block:
    return Block(id=block_id, page=page, section=section, role=role, qa_id="", image_before=False, text=text)


def draft(**overrides) -> ClaimDraft:
    values = dict(
        block_id="B001", entity="英伟达", attribution="老师本人", speech_act="判断", target="股价", direction="负面(看跌)",
        strength="肯定", time_phrase="", window_start="", window_end="", time_precision="未说明", conclusion="结论",
        premise="", mechanism="", result="", condition="", signal_metric="", signal_threshold="", signal_due="",
        signal_means="", action="", explicitness="明说", quote="这家公司股价会大跌", prior_view="", change_type="",
    )
    values.update(overrides)
    return ClaimDraft(**values)


def agree(index=0) -> ClaimVerdict:
    return ClaimVerdict(index=index, supported=True, wrong_fields=[], note="")
