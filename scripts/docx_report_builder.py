#!/usr/bin/env python3
"""Rebuild a Group 18 report DOCX body from a block list, reusing the
original file's own paragraph, heading, table, figure and reference XML as
templates (styles, fonts, sizes, two-column layout are unchanged).

Block kinds: ("title"|"author"|"course"|"p"|"h1"|"h2"|"caption"|"ref", text),
("break",) for the one-to-two-column section break, ("figure",),
("table", header_list, rows_list_of_lists).
The original DOCX is only read; output must not already exist.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

BLOCK_RE = re.compile(r"<w:p[ >].*?</w:p>|<w:tbl>.*?</w:tbl>|<w:sectPr.*?</w:sectPr>", re.S)
TEXT_RE = re.compile(r"(<w:t(?: [^>]*)?>)(.*?)(</w:t>)", re.S)


def _style(block: str) -> str:
    m = re.search(r'<w:pStyle w:val="([^"]+)"', block)
    return m.group(1) if m else "-"


def _text(block: str) -> str:
    return "".join(m.group(2) for m in TEXT_RE.finditer(block))


def _set_text(template: str, text: str) -> str:
    """Put `text` into the template's single run (first <w:t>), drop other runs' text."""
    first = True

    def repl(m: re.Match) -> str:
        nonlocal first
        if first:
            first = False
            return f'<w:t xml:space="preserve">{escape(text)}</w:t>'
        return ""
    out = TEXT_RE.sub(repl, template)
    if first:
        raise ValueError("template has no <w:t>")
    return out


class Templates:
    def __init__(self, document_xml: str):
        start = document_xml.index("<w:body>") + len("<w:body>")
        end = document_xml.index("</w:body>")
        self.head, self.tail = document_xml[:start], document_xml[end:]
        blocks = BLOCK_RE.findall(document_xml[start:end])
        self.sect = blocks[-1]
        self.title = next(b for b in blocks if _style(b) == "Title")
        self.h1 = next(b for b in blocks if _style(b) == "Heading1")
        self.h2 = next((b for b in blocks if _style(b) == "Heading2"), None)
        self.author = next(b for b in blocks if "Shahriar Ahmed" in _text(b))
        self.course = next(b for b in blocks if "Group 18" in _text(b) and _style(b) == "-")
        self.body = next(b for b in blocks if _text(b).startswith("Abstract"))
        self.brk = next(b for b in blocks if "<w:sectPr>" in b and b.startswith("<w:p"))
        self.figure = next(b for b in blocks if "<w:drawing>" in b)
        self.caption = next(b for b in blocks if _text(b).startswith("Fig. 1."))
        self.ref = next(b for b in blocks if _text(b).startswith("[1]"))
        table = next(b for b in blocks if b.startswith("<w:tbl>"))
        rows = re.findall(r"<w:tr[ >].*?</w:tr>", table, re.S)
        self.tbl_pr = re.search(r"<w:tblPr>.*?</w:tblPr>", table, re.S).group(0)
        self.head_cell = re.search(r"<w:tc>.*?</w:tc>", rows[0], re.S).group(0)
        self.body_cell = re.search(r"<w:tc>.*?</w:tc>", rows[1], re.S).group(0)
        self.table_width = sum(int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"/>', table))

    def table(self, header: list[str], rows: list[list[str]]) -> str:
        width = self.table_width // len(header)
        grid = "<w:tblGrid>" + f'<w:gridCol w:w="{width}"/>' * len(header) + "</w:tblGrid>"

        def cell(template: str, text: str) -> str:
            return _set_text(re.sub(r'<w:tcW w:type="dxa" w:w="\d+"/>',
                                    f'<w:tcW w:type="dxa" w:w="{width}"/>', template), text)
        out = [f"<w:tbl>{self.tbl_pr}{grid}",
               "<w:tr>" + "".join(cell(self.head_cell, h) for h in header) + "</w:tr>"]
        for row in rows:
            if len(row) != len(header):
                raise ValueError(f"row has {len(row)} cells, header has {len(header)}")
            out.append("<w:tr>" + "".join(cell(self.body_cell, c) for c in row) + "</w:tr>")
        return "".join(out) + "</w:tbl>"

    def render(self, blocks: list[tuple]) -> str:
        simple = {"title": self.title, "author": self.author, "course": self.course,
                  "p": self.body, "h1": self.h1, "h2": self.h2,
                  "caption": self.caption, "ref": self.ref}
        out = []
        for block in blocks:
            kind = block[0]
            if kind in simple:
                if simple[kind] is None:
                    raise ValueError(f"template document has no {kind!r} paragraph")
                out.append(_set_text(simple[kind], block[1]))
            elif kind == "break":
                out.append(self.brk)
            elif kind == "figure":
                out.append(self.figure)
            elif kind == "table":
                out.append(self.table(block[1], block[2]))
            else:
                raise ValueError(f"unknown block kind {kind!r}")
        return self.head + "".join(out) + self.sect + self.tail


def build(original: Path, output: Path, blocks: list[tuple], figure_png: Path | None) -> None:
    if output.exists():
        raise SystemExit(f"error: refusing to overwrite {output}")
    with zipfile.ZipFile(original) as src:
        document = src.read("word/document.xml").decode("utf-8")
        new_document = Templates(document).render(blocks)
        media = [n for n in src.namelist() if n.startswith("word/media/")]
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == "word/document.xml":
                    data = new_document.encode("utf-8")
                elif figure_png is not None and info.filename == media[0]:
                    data = figure_png.read_bytes()
                dst.writestr(info, data)


def original_blocks(original: Path) -> list[tuple]:
    """Block list that reproduces the original (round-trip test)."""
    document = zipfile.ZipFile(original).read("word/document.xml").decode("utf-8")
    t = Templates(document)
    start = document.index("<w:body>") + 8
    blocks = []
    for b in BLOCK_RE.findall(document[start:document.index("</w:body>")])[:-1]:
        if b.startswith("<w:tbl>"):
            rows = [[_text(c) for c in re.findall(r"<w:tc>.*?</w:tc>", r, re.S)]
                    for r in re.findall(r"<w:tr[ >].*?</w:tr>", b, re.S)]
            blocks.append(("table", rows[0], rows[1:]))
        elif b == t.brk:
            blocks.append(("break",))
        elif "<w:drawing>" in b:
            blocks.append(("figure",))
        else:
            style, text = _style(b), _text(b)
            kind = {"Title": "title", "Heading1": "h1", "Heading2": "h2"}.get(style)
            if kind is None:
                kind = ("author" if "Shahriar Ahmed" in text else
                        "course" if "Group 18" in text else
                        "caption" if text.startswith("Fig.") else
                        "ref" if text.startswith("[") else "p")
            blocks.append((kind, text))
    return blocks
