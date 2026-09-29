"""Generic OOXML manuscript builder shared by the English and Chinese versions.

``write_docx`` takes a language-neutral list of blocks and an ordered list of
figures, and emits a .docx that re-uses the styles, header, footer and section
geometry of the course template (``templates/docx_template``).
"""

from __future__ import annotations

import html
import os
import struct
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

W_TWIPS = 9972
EMU_PER_TWIP = 635
MAX_EMU = W_TWIPS * EMU_PER_TWIP - 16000

FONT = "Calibri"
FONT_CJK = "SimSun"
# relative width of each figure inside the text column
FIG_SCALE = {
    "fig1_workflow": 0.86, "fig2_model_and_data": 0.92, "fig3_mlp_architecture": 0.80,
    "fig4_loss_curve": 0.62, "fig5_prediction_test_samples": 1.00, "fig6_training_size": 0.88,
    "fig7_design": 0.88, "fig8_failure_case": 0.96,
}


def esc(t: str) -> str:
    return html.escape(t, quote=False)


def _fonts() -> str:
    return (f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:eastAsia="{FONT_CJK}"/>')


def add_runs(text: str, bold=False, italic=False, size=None, color=None,
             mono=False, sup=False, sub=False) -> str:
    """Turn a small subset of HTML (<b>, <i>, <sub>, <super>, <br/>, <font>) into runs."""
    import re

    rpr = []
    if bold:
        rpr.append("<w:b/>")
    if italic:
        rpr.append("<w:i/>")
    if color:
        rpr.append(f'<w:color w:val="{color}"/>')
    if size:
        rpr.append(f'<w:sz w:val="{int(round(size*2))}"/>')
    rpr.append(_fonts())
    if sup:
        rpr.append('<w:vertAlign w:val="superscript"/>')
    if sub:
        rpr.append('<w:vertAlign w:val="subscript"/>')
    rpr = "".join(rpr)

    def run(t, extra=""):
        return f'<w:r><w:rPr>{rpr}{extra}</w:rPr><w:t xml:space="preserve">{esc(t)}</w:t></w:r>'

    out = []
    pos = 0
    pattern = re.compile(r"</?(b|i|sub|super|br\s*/|font[^>]*)>", re.I)
    state = {"b": bold, "i": italic, "sub": sub, "sup": sup}
    stack = []
    for m in pattern.finditer(text):
        chunk = text[pos:m.start()]
        if chunk:
            out.append(run(chunk))
        tag = m.group(1).lower()
        closing = text[m.start() + 1] == "/"
        name = tag.split()[0].rstrip("/")
        if name == "br":
            out.append(f'<w:r><w:rPr>{rpr}</w:rPr><w:br/></w:r>')
        else:
            if closing:
                if stack:
                    k = stack.pop()
                    state[k] = False
            else:
                state[name] = True
                stack.append(name)
        pos = m.end()
    if pos < len(text):
        out.append(run(text[pos:]))
    if not out:
        out.append(run(text))
    return "".join(out)


def para(runs, align=None, space_before=None, space_after=None, style=None,
         indent=None, size=None, keep_next=False) -> str:
    ppr = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    ppr.append('<w:ind w:firstLine="%d"/>' % (0 if indent is None else indent))
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    spacing = []
    if space_before is not None:
        spacing.append(f'w:before="{space_before}"')
    if space_after is not None:
        spacing.append(f'w:after="{space_after}"')
    if spacing:
        ppr.append("<w:spacing " + " ".join(spacing) + "/>")
    if keep_next:
        ppr.append("<w:keepNext/>")
    body = runs if isinstance(runs, str) else "".join(runs)
    return "<w:p><w:pPr>" + "".join(ppr) + "</w:pPr>" + body + "</w:p>"


def heading(text: str, level: int = 1) -> str:
    return para(add_runs(text), style={1: "1", 2: "21", 3: "31"}[level], keep_next=True)


def body(text: str, size=9.5) -> str:
    return para(add_runs(text, size=size), align="both", space_after=110, indent=200)


def caption(text: str, size=9) -> str:
    return para(add_runs(text, size=size, bold=False), align="center",
                space_before=50, space_after=170)


def png_size(path: str):
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", head[16:24])


def figure(path: str, rel_id: str, docpr_id: int) -> str:
    w, h = png_size(path)
    key = os.path.basename(path).replace("_zh", "").replace(".png", "")
    scale = FIG_SCALE.get(key, 0.9)
    cx = int(min(MAX_EMU, w * 9525) * scale)
    cy = int(cx * h / w)
    name = os.path.basename(path)
    return (
        '<w:p><w:pPr><w:ind w:firstLine="0"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr>'
        "<w:noProof/>" + _fonts() + "</w:rPr><w:drawing>"
        '<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{docpr_id}" name="Picture {docpr_id}"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>'
        "</wp:cNvGraphicFramePr>"
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="{docpr_id}" name="{esc(name)}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
    )


def table(header, rows, widths=None) -> str:
    n = len(header)
    widths = widths or [W_TWIPS // n] * n
    borders = ("<w:tblBorders>" + "".join(
        f'<w:{e} w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>'
        for e in ("top", "left", "bottom", "right", "insideH", "insideV")) + "</w:tblBorders>")
    out = ["<w:tbl><w:tblPr>",
           f'<w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:jc w:val="center"/>', borders,
           '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" '
           'w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr><w:tblGrid>']
    out += [f'<w:gridCol w:w="{w}"/>' for w in widths]
    out.append("</w:tblGrid>")

    def cell(text, w, bold=False, shade=None):
        tc = [f'<w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>']
        if shade:
            tc.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
        tc.append("</w:tcPr>")
        return ("<w:tc>" + "".join(tc)
                + para(add_runs(str(text), bold=bold, size=8.5), align="center") + "</w:tc>")

    out.append("<w:tr><w:trPr><w:tblHeader/></w:trPr>")
    out += [cell(h, widths[i], bold=True, shade="F2F2F2") for i, h in enumerate(header)]
    out.append("</w:tr>")
    for row in rows:
        out.append("<w:tr>")
        out += [cell(c, widths[i]) for i, c in enumerate(row)]
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


SECT_PR = (
    "<w:sectPr>"
    '<w:headerReference w:type="default" r:id="rIdHdr"/>'
    '<w:footerReference w:type="default" r:id="rIdFtr"/>'
    '<w:pgSz w:w="12240" w:h="15840"/>'
    '<w:pgMar w:top="1020" w:right="1134" w:bottom="1020" w:left="1134" '
    'w:header="720" w:footer="720" w:gutter="0"/>'
    '<w:cols w:space="720"/><w:docGrid w:linePitch="360"/></w:sectPr>'
)

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Default Extension="png" ContentType="image/png"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
    '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
    '<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>'
    '<Override PartName="/word/webSettings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml"/>'
    '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
    '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
    '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>'
    '<Override PartName="/word/endnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"/>'
    '<Override PartName="/word/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
    '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
    "</Types>"
)

ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
    "</Relationships>"
)

DOCUMENT_OPEN = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:o="urn:schemas-microsoft-com:office:office" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:w10="urn:schemas-microsoft-com:office:word" '
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
    'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml" '
    'xmlns:w16="http://schemas.microsoft.com/office/word/2018/wordml" '
    'xmlns:w16du="http://schemas.microsoft.com/office/word/2023/wordml/word16du" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
    'mc:Ignorable="w14 w15 w16 w16du wp14"><w:body>'
)


def build_paragraphs(blocks, figures: list[str]) -> str:
    """Render language-neutral blocks; returns the paragraph XML plus sectPr."""
    rel_of = {os.path.basename(f): f"rIdFig{i+1}" for i, f in enumerate(figures)}
    parts = []
    docpr = 1
    for block in blocks:
        kind = block[0]
        if kind == "h":
            parts.append(heading(block[1], block[2] if len(block) > 2 else 1))
        elif kind == "p":
            parts.append(body(block[1]))
        elif kind == "cap":
            parts.append(caption(block[1]))
        elif kind == "fig":
            name = block[1]
            docpr += 1
            parts.append(figure(os.path.join(ROOT, "figures", name), rel_of[name], docpr))
        elif kind == "table":
            parts.append(table(block[1], block[2], block[3] if len(block) > 3 else None))
        elif kind == "refs":
            from texts_zh import REFS as REFS_ZH

            refs = block[1] if len(block) > 1 and block[1] else REFS_ZH
            for i, r in enumerate(refs, start=1):
                parts.append(para(add_runs(f"[{i}] {r}", size=9), space_after=50, indent=0))
        else:
            raise ValueError(f"unknown block {kind!r}")
    return "".join(parts) + SECT_PR


def write_docx(out_path: str, blocks, figures: list[str], template_dir: str,
               core_title: str, author: str, preface_xml: str = "") -> None:
    document_xml = (DOCUMENT_OPEN + preface_xml + build_paragraphs(blocks, figures)
                    + "</w:body></w:document>")

    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
        '<Relationship Id="rIdNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
        '<Relationship Id="rIdFontTable" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>'
        '<Relationship Id="rIdWebSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/webSettings" Target="webSettings.xml"/>'
        '<Relationship Id="rIdHdr" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>'
        '<Relationship Id="rIdFtr" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
        '<Relationship Id="rIdFootnotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>'
        '<Relationship Id="rIdEndnotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes" Target="endnotes.xml"/>'
        '<Relationship Id="rIdTheme" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
        + "".join(
            f'<Relationship Id="rIdFig{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{f}"/>'
            for i, f in enumerate(figures)
        ) + "</Relationships>"
    )

    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{esc(core_title)}</dc:title><dc:creator>{esc(author)}</dc:creator>"
        "<cp:lastModifiedBy>AI4S thin-film pipeline</cp:lastModifiedBy></cp:coreProperties>"
    )
    app = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>Microsoft Office Word</Application></Properties>"
    )

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    src_word = os.path.join(template_dir, "word")
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/_rels/document.xml.rels", rels)
        for part in ("styles.xml", "settings.xml", "numbering.xml", "fontTable.xml",
                     "webSettings.xml", "header1.xml", "footer1.xml",
                     "footnotes.xml", "endnotes.xml"):
            with open(os.path.join(src_word, part), "rb") as fh:
                z.writestr(f"word/{part}", fh.read())
        with open(os.path.join(src_word, "theme", "theme1.xml"), "rb") as fh:
            z.writestr("word/theme/theme1.xml", fh.read())
        for f in figures:
            with open(os.path.join(ROOT, "figures", f), "rb") as fh:
                z.writestr(f"word/media/{f}", fh.read())
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)
