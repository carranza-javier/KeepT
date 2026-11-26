"""Render the Musterwil sample letter (docs/Musterwil_Kehrichtabfuhr.docx) to a PNG the way a
word processor shows it: python tools/render_letter.py out.png [zoom]

The text, fonts, sizes, colours and spacing are taken from the .docx, so OCR and translation
can be tested on the same page without Word."""
from __future__ import annotations

import html
import re
import sys
import zipfile
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QTextDocument

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "docs" / "Musterwil_Kehrichtabfuhr.docx"


def paragraphs(path: Path = DOCX) -> list[dict]:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    out = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)))
        size = re.findall(r'w:sz w:val="(\d+)"', p)
        color = re.findall(r'w:color w:val="(\w+)"', p)
        align = re.findall(r'w:jc w:val="(\w+)"', p)
        before = re.findall(r'w:before="(\d+)"', p)
        after = re.findall(r'w:after="(\d+)"', p)
        out.append({
            "text": text,
            "pt": int(size[0]) / 2 if size else 11,
            "color": "#" + color[0] if color else "#000000",
            "align": {"right": "right", "center": "center"}.get(align[0] if align else "", "left"),
            "bold": "<w:b/>" in p,
            "before": int(before[0]) / 20 if before else 0,  # twips -> pt
            "after": int(after[0]) / 20 if after else 0,
            "border": "<w:pBdr>" in p,
        })
    return out


def render(zoom: float = 1.0) -> QImage:
    px = 96 / 72 * zoom  # px per pt
    width = round(11906 / 1440 * 96 * zoom)
    margin = round(1300 / 1440 * 96 * zoom)
    top = round(1134 / 1440 * 96 * zoom)
    parts = []
    for p in paragraphs():
        style = (f"font-family:Arial; font-size:{p['pt'] * px:.1f}px; color:{p['color']};"
                 f"margin-top:{p['before'] * px:.0f}px; margin-bottom:{p['after'] * px:.0f}px;"
                 f"font-weight:{700 if p['bold'] else 400};")
        parts.append(f'<p align="{p["align"]}" style="{style}">{html.escape(p["text"])}</p>')
        if p["border"]:
            parts.append(f'<hr style="height:{max(1, round(1.33 * zoom))}px; background:#1F3A5F; border:0"/>')
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setTextWidth(width - 2 * margin)
    doc.setHtml("".join(parts))
    height = max(round(width * 0.9), int(doc.size().height()) + 2 * top)
    img = QImage(width, height, QImage.Format_RGB32)
    img.fill(QColor("#ffffff"))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.TextAntialiasing)
    painter.translate(margin, top)
    doc.drawContents(painter, QRectF(0, 0, width, height))
    painter.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    zoom = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    render(zoom).save(sys.argv[1])
