from __future__ import annotations

import pytest

from app.research import parser
from app.research.parser import TextIntegrityError, parse_transcript

FOOTER = "【课程入口】公众号“创新地图”进入特训营        {}"
RAW = "\n".join(
    [
        "        【标题】不进入正文",
        "第一部分：课程要点提炼",
        "  摘要一句话。",
        "第二部分：课程文字稿",
        "  【讲者】这句话跨",
        FOOTER.format(3),
        "\f页继续了，Scaling",
        "Law 还有效，好长时 间。",
        "",
        "",
        "",
        "",
        "  配图之后的新段落。",
        "  互动问答",
        "  小明问：王老师，1）第一问？2）第二问？",
        "  王老师答：1）第一答。2）第二答。",
        "  好，不好意思，今天到这儿。",
    ]
)


@pytest.fixture
def blocks():
    return parse_transcript(RAW)


def test_title_and_footer_are_excluded(blocks):
    joined = "".join(b.text for b in blocks)
    assert "标题" not in joined and "课程入口" not in joined


def test_sentence_is_joined_across_pages_and_keeps_start_and_end_page(blocks):
    block = next(b for b in blocks if "这句话跨页继续了" in b.text)
    assert block.page == "1-2"


def test_ascii_words_keep_a_space_and_cjk_justification_is_removed(blocks):
    block = next(b for b in blocks if "Scaling" in b.text)
    assert "Scaling Law" in block.text and "好长时间" in block.text


def test_image_gap_starts_a_flagged_paragraph(blocks):
    assert next(b for b in blocks if b.text.startswith("配图之后")).image_before


def test_questions_and_answers_share_numbered_ids(blocks):
    pairs = [(b.role, b.qa_id) for b in blocks if b.qa_id]
    assert ("提问人", "Q01-2") in pairs and ("老师回答", "Q01-1") in pairs and ("老师回答", "Q01-2") in pairs


def test_closing_remark_is_lecture_not_answer(blocks):
    assert blocks[-1].role == "讲者口述" and blocks[-1].qa_id == ""


def test_lost_text_raises(monkeypatch):
    original = parser._chunks
    monkeypatch.setattr(parser, "_chunks", lambda text, base: original(text, base)[:0] or [(base, text[:-1])])
    with pytest.raises(TextIntegrityError):
        parse_transcript(RAW)
