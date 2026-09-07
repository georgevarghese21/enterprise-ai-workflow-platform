"""Splits a policy markdown document into retrievable chunks.

Chunk boundaries follow `##` section headings first (since NovaTech policy
docs are consistently structured that way), then fall back to splitting an
overlong section by paragraph so no single chunk is too large to embed or
retrieve usefully.
"""

import re
from dataclasses import dataclass

MAX_CHUNK_CHARS = 900
OVERLAP_CHARS = 150

_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    title: str | None
    content: str


def chunk_markdown(text: str) -> list[Chunk]:
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return _split_long_section(None, text.strip())

    chunks: list[Chunk] = []
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_body = text[start:end].strip()
        if section_body:
            chunks.extend(_split_long_section(title, section_body))
    return chunks


def _split_long_section(title: str | None, body: str) -> list[Chunk]:
    if len(body) <= MAX_CHUNK_CHARS:
        return [Chunk(title=title, content=body)]

    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) > MAX_CHUNK_CHARS and current:
            chunks.append(Chunk(title=title, content=current))
            current = current[-OVERLAP_CHARS:] + "\n\n" + paragraph
        else:
            current = candidate
    if current:
        chunks.append(Chunk(title=title, content=current.strip()))
    return chunks
