"""Build the Chinese manuscript PDF with reportlab.

Uses the same result JSON files as the Word version, so both manuscripts and both
languages show identical numbers.  Chinese text is rendered with SimSun/SimHei
(registering a system CJK font is required because the built-in Type-1 fonts
contain no CJK glyphs).

    python src/make_pdf_zh.py     # -> paper/AI4S_研究论文_中文稿_<id>.pdf
"""

from __future__ import annotations

import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime  # noqa: E402  (matplotlib/temp env only)

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate, Frame, Image, KeepTogether, PageTemplate, Paragraph, Spacer,
    Table, TableStyle,
)

from texts_zh import FIG, REFS, build_zh  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CJK = None
for _n, _paths in (
    ("SimSun", [r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\simsunb.ttf"]),
    ("SimHei", [r"C:\Windows\Fonts\simhei.ttf"]),
    ("MSYaHei", [r"C:\Windows\Fonts\msyh.ttc"]),
):
    for _p in _paths:
        if os.path.exists(_p):
            try:
                pdfmetrics.registerFont(TTFont(_n, _p, subfontIndex=0))
                CJK = _n
                break
            except Exception:
                continue
    if CJK:
        break

BODY = ParagraphStyle("body", fontName=CJK or "Helvetica", fontSize=9.0, leading=12.4,
                      alignment=TA_JUSTIFY, firstLineIndent=18, spaceAfter=3.5)
NOIND = ParagraphStyle("noind", parent=BODY, firstLineIndent=0)
H1 = ParagraphStyle("h1", fontName=CJK or "Helvetica-Bold", fontSize=11.5, leading=14,
                    spaceBefore=7, spaceAfter=3)
H2 = ParagraphStyle("h2", fontName=CJK or "Helvetica-Bold", fontSize=10, leading=12,
                    spaceBefore=5.5, spaceAfter=2.5)
TITLE_S = ParagraphStyle("title", fontName=CJK or "Helvetica-Bold", fontSize=15, leading=19,
                         alignment=TA_CENTER, spaceAfter=4)
SUB = ParagraphStyle("sub", fontName="Times-Roman", fontSize=10.5, leading=13,
                     alignment=TA_CENTER, spaceAfter=5)
META = ParagraphStyle("meta", fontName=CJK or "Helvetica", fontSize=9, leading=12,
                      alignment=TA_CENTER)
CAP = ParagraphStyle("cap", fontName=CJK or "Helvetica-Bold", fontSize=7.9, leading=10,
                     alignment=TA_CENTER, spaceBefore=1.5, spaceAfter=5)
SMALL = ParagraphStyle("small", fontName=CJK or "Helvetica", fontSize=7.9, leading=10.4,
                       alignment=TA_LEFT, firstLineIndent=0, spaceAfter=2)

FIG_SCALE = {
    "fig1_workflow": 0.80, "fig2_model_and_data": 0.90, "fig3_mlp_architecture": 0.72,
    "fig4_loss_curve": 0.52, "fig5_prediction_test_samples": 1.00, "fig6_training_size": 0.82,
    "fig7_design": 0.82, "fig8_failure_case": 0.94,
}


def load(name):
    with open(os.path.join(ROOT, "results", name), "r", encoding="utf-8") as fh:
        return json.load(fh)


_SUB = {"<sub>": "<sub>", "</sub>": "</sub>", "<super>": "<super>", "</super>": "</super>"}


def rl(text: str) -> str:
    """Convert the block-markup subset (<b> <i> <sub> <super> <br/>) into reportlab markup."""
    t = html.escape(text, quote=False)
    for tag in ("b", "i", "sub", "super"):
        t = t.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    t = t.replace("&lt;br/&gt;", "<br/>").replace("&lt;br&gt;", "<br/>")
    return t


def image(name: str):
    path = os.path.join(ROOT, "figures", name)
    from PIL import Image as PILImage

    with PILImage.open(path) as im:
        w, h = im.size
    usable = 7.08 * FIG_SCALE.get(name.replace("_zh", "").replace(".png", ""), 0.9)
    return Image(path, width=usable * inch, height=usable * inch * h / w)


def kv_table(header, rows, widths):
    data = [[Paragraph(f"<b>{html.escape(str(h))}</b>", SMALL) for h in header]]
    for r in rows:
        data.append([Paragraph(html.escape(str(x)), SMALL) for x in r])
    t = Table(data, colWidths=[w / 1000.0 * inch for w in widths], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


def main() -> None:
    main_j = load("mlp_main_metrics.json")
    sizes_j = load("training_size_study.json")
    screen_j = load("screening_results.json")
    fp = load("dataset_fingerprint.json")
    c = main_j["config"]
    lam_t = screen_j["target_wavelength_nm"]

    blocks = build_zh(main_j, sizes_j, screen_j, fp)
    blocks = [("refs", REFS) if b[0] == "refs" else b for b in blocks]

    flow = [
        Paragraph("基于多层感知机的多层介质薄膜光谱预测与辅助设计", TITLE_S),
        Paragraph("MLP-Based Spectral Prediction and Data-Driven Design of Multilayer "
                  "Dielectric Thin Films", SUB),
        Paragraph(f"姓名：{c.get('student_name', '__________')}　　学号：{c['student_id']}", META),
        Paragraph(f"λ_target = {lam_t:.0f} nm　　seed = {c['seed']}　　"
                  f"design_seed = {c['design_seed']}", META),
        Spacer(1, 4),
    ]
    for b in blocks:
        kind = b[0]
        if kind == "h":
            flow.append(Paragraph(rl(b[1]), H1 if (len(b) < 3 or b[2] == 1) else H2))
        elif kind == "p":
            flow.append(Paragraph(rl(b[1]), BODY))
        elif kind == "cap":
            flow.append(Paragraph(rl(b[1]), CAP))
        elif kind == "fig":
            flow.append(KeepTogether([image(b[1]), Paragraph(rl(b[2]), CAP)]))
        elif kind == "table":
            flow.append(kv_table(b[1], b[2], b[3]))
        elif kind == "refs":
            for i, r in enumerate(b[1], start=1):
                flow.append(Paragraph(f"[{i}] {html.escape(r)}", SMALL))

    out = os.path.join(ROOT, "paper", f"AI4S_研究论文_中文稿_{c['student_id']}.pdf")

    def on_page(canv, doc):
        canv.saveState()
        canv.setFont(CJK or "Helvetica", 7.5)
        canv.setFillColor(colors.HexColor("#888888"))
        canv.drawRightString(letter[0] - 0.71 * inch, letter[1] - 0.5 * inch,
                             "薄膜技术 · AI4S 课程大作业")
        canv.setFont("Helvetica", 7.5)
        canv.drawCentredString(letter[0] / 2, 0.5 * inch, "Course Research Article Template")
        canv.drawRightString(letter[0] - 0.71 * inch, 0.5 * inch, str(canv.getPageNumber()))
        canv.restoreState()

    os.makedirs(os.path.dirname(out), exist_ok=True)
    doc = BaseDocTemplate(out, pagesize=letter, leftMargin=0.71 * inch, rightMargin=0.71 * inch,
                          topMargin=0.72 * inch, bottomMargin=0.68 * inch,
                          title="基于多层感知机的多层介质薄膜光谱预测与辅助设计",
                          author=c["student_id"])
    doc.addPageTemplates([PageTemplate(id="all",
                                       frames=[Frame(doc.leftMargin, doc.bottomMargin,
                                                     doc.width, doc.height)], onPage=on_page)])
    doc.build(flow)
    n_pages = len(re.findall(rb"/Type\s*/Page[^s]", open(out, "rb").read()))
    print("wrote", os.path.relpath(out, ROOT), f"({os.path.getsize(out)/1024:.0f} kB, "
                                               f"{n_pages} pages)")


if __name__ == "__main__":
    main()
