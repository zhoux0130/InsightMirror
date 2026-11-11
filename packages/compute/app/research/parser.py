"""Convert transcript PDF text into page-anchored blocks without rewriting the source."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.research.schemas import Block

CJK_RANGE = r"㐀-鿿"
CJK_ADJACENT = rf"[{CJK_RANGE}，。？！、：；”“（）]"
FOOTER = re.compile(r"【课程入口】公众号.创新地图.进入特训营\s*\d+\s*$")
QUESTION_OPENING = re.compile(r"^[^：。，]{1,14}?\s*问：")
SUB_ITEM = re.compile(r"[1-9]）")
TARGET_CHUNK_CHARS = 450
MAX_CHUNK_CHARS = 620

SECTION_SUMMARY = "课程要点(助手整理)"
SECTION_LECTURE = "课程文字稿"
SECTION_QA = "互动问答"
ROLE_SUMMARY = "助手摘要"
ROLE_LECTURE = "讲者口述"
ROLE_QUESTION = "提问人"
ROLE_ANSWER = "老师回答"
ROLE_HEADING = "分节标题"


class TextIntegrityError(ValueError):
    """Blocks no longer contain exactly the source characters."""


@dataclass
class _Paragraph:
    text: str = ""
    line_pages: list[tuple[int, int]] = field(default_factory=list)
    image_before: bool = False

    def page_at(self, offset: int) -> int:
        page = self.line_pages[0][1]
        for start, line_page in self.line_pages:
            if start <= offset:
                page = line_page
        return page


def extract_text(pdf_path: Path) -> str:
    return subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"], check=True, capture_output=True, text=True
    ).stdout


def _clean_line(line: str) -> str:
    collapsed = re.sub(r"\s+", " ", line.strip())
    return re.sub(rf"(?<={CJK_ADJACENT}) (?={CJK_ADJACENT})", "", collapsed)


def _join(left: str, right: str) -> str:
    if left and right and left[-1].isascii() and left[-1].isalnum() and right[0].isascii() and right[0].isalnum():
        return f"{left} {right}"
    return left + right


def _is_part_heading(text: str) -> bool:
    return text.startswith("第") and "部分" in text[:6]


def _read_paragraphs(raw: str) -> tuple[list[_Paragraph], str]:
    paragraphs: list[_Paragraph] = []
    current: _Paragraph | None = None
    source_chars: list[str] = []
    blank_run, page, started, pending_image = 0, 1, False, False

    for line in raw.split("\n"):
        if "\f" in line:
            page += line.count("\f")
            line = line.replace("\f", "")
        if FOOTER.search(line.strip()):
            continue
        if not line.strip():
            blank_run += 1
            continue
        if not started:
            if not line.strip().startswith("第一部分"):
                blank_run = 0
                continue
            started = True
        text = _clean_line(line)
        source_chars.append(text)
        image_gap = blank_run >= 3
        pending_image = pending_image or image_gap
        if current is None or image_gap or re.match(r"\s{2,}\S", line) or _is_part_heading(text):
            if current and current.text:
                paragraphs.append(current)
            current = _Paragraph(image_before=pending_image)
            pending_image = False
        blank_run = 0
        current.line_pages.append((len(current.text), page))
        current.text = _join(current.text, text)
    if current and current.text:
        paragraphs.append(current)
    return paragraphs, "".join(source_chars)


def _chunks(text: str, base: int) -> list[tuple[int, str]]:
    chunks: list[tuple[int, str]] = []
    buffer, buffer_start, offset = "", base, base
    for sentence in filter(None, re.split(r"(?<=[。！？])", text)):
        if buffer and (len(buffer) >= TARGET_CHUNK_CHARS or len(buffer) + len(sentence) > MAX_CHUNK_CHARS):
            chunks.append((buffer_start, buffer))
            buffer, buffer_start = "", offset
        buffer += sentence
        offset += len(sentence)
    if buffer:
        chunks.append((buffer_start, buffer))
    return chunks


def _qa_pieces(text: str) -> list[tuple[int, str]]:
    cuts = [0] + [m.start() for m in SUB_ITEM.finditer(text) if m.start() > 0] + [len(text)]
    return [(a, text[a:b]) for a, b in zip(cuts, cuts[1:]) if text[a:b]]


def parse_transcript(raw: str) -> list[Block]:
    paragraphs, source = _read_paragraphs(raw)
    blocks: list[Block] = []
    section, role, question_number = SECTION_SUMMARY, ROLE_SUMMARY, 0

    for paragraph in paragraphs:
        text = paragraph.text
        if text.startswith("第一部分"):
            section, role = SECTION_SUMMARY, ROLE_SUMMARY
        elif text.startswith("第二部分"):
            section, role = SECTION_LECTURE, ROLE_LECTURE
        elif text.strip() == SECTION_QA:
            section, role = SECTION_QA, ROLE_HEADING
        elif section == SECTION_QA:
            if text.startswith("王老师答："):
                role = ROLE_ANSWER
            elif QUESTION_OPENING.match(text):
                question_number += 1
                role = ROLE_QUESTION
            elif text.startswith("好，不好意思"):
                role = ROLE_LECTURE

        in_exchange = section == SECTION_QA and role in (ROLE_QUESTION, ROLE_ANSWER)
        for piece_start, piece in _qa_pieces(text) if in_exchange else [(0, text)]:
            sub_item = re.match(r"([1-9])）", piece)
            for start, chunk in _chunks(piece, piece_start):
                qa_id = ""
                if in_exchange:
                    qa_id = f"Q{question_number:02d}" + (f"-{sub_item.group(1)}" if sub_item else "")
                first, last = paragraph.page_at(start), paragraph.page_at(start + len(chunk) - 1)
                blocks.append(
                    Block(
                        id=f"B{len(blocks) + 1:03d}",
                        page=str(first) if first == last else f"{first}-{last}",
                        section=section,
                        role=role,
                        qa_id=qa_id,
                        image_before=paragraph.image_before and start == 0,
                        text=chunk,
                    )
                )

    if _squash("".join(b.text for b in blocks)) != _squash(source):
        raise TextIntegrityError("parsed blocks do not match the source text")
    return blocks


def _squash(text: str) -> str:
    return re.sub(r"\s", "", text)


def render_blocks(blocks: list[Block]) -> str:
    return "\n".join(
        f'<block id="{b.id}" page="{b.page}" role="{b.role}" qa="{b.qa_id}">{b.text}</block>' for b in blocks
    )
