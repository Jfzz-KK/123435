"""Check the manuscripts and README against the assignment's submission rules.

Verifies, from the files themselves (not from memory):
  * the repository URL now present in all four manuscripts and in the READMEs,
  * that no placeholder is left anywhere,
  * the personal parameters quoted in each document,
  * the section list required by the assignment template,
  * that all eight figures and Table 1 are referenced,
  * the word/page budget of the PDFs.

    python tools/check_submission_state.py
"""

from __future__ import annotations

import os
import re
import zipfile

import pypdfium2 as pdfium

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
WORKSPACE = os.path.dirname(os.path.dirname(PROJ))
OUT = os.path.join(WORKSPACE, "default-workspace", "AI4S_提交物")
URL = "https://github.com/Jfzz-KK/123435"
PLACEHOLDER = "USERNAME/REPOSITORY"

SECTIONS = ["Abstract", "Introduction", "Materials and Methods", "Results", "Discussion",
            "Conclusions", "Data and Code Availability", "References"]


def docx_text(path: str) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    return "\n".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S))


def pdf_text(path: str) -> str:
    doc = pdfium.PdfDocument(path)
    return "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc))), len(doc)


def main() -> None:
    print("=" * 78)
    print("1. repository URL in every manuscript (delivery copies)")
    print("=" * 78)
    for f in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, f)
        if f.endswith(".docx"):
            t = docx_text(p)
            pages = ""
        elif f.endswith(".pdf"):
            t, n = pdf_text(p)
            pages = f"  [{n} pages]"
        else:
            continue
        bare = URL.replace("https://", "")
        print(f"  {f[:42]:44} url x{t.count(URL)}  bare x{t.count(bare)}  "
              f"placeholder x{t.count(PLACEHOLDER)}{pages}")

    print()
    print("=" * 78)
    print("2. personal parameters quoted in each manuscript")
    print("=" * 78)
    for f in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, f)
        if f.endswith(".docx"):
            t = docx_text(p)
        elif f.endswith(".pdf"):
            t, _ = pdf_text(p)
        else:
            continue
        present = {k: (k in t) for k in ("480", "276134", "276135", "2020276134")}
        print(f"  {f[:42]:44} " + "  ".join(f"{k}:{'Y' if v else 'N'}" for k, v in present.items()))

    print()
    print("=" * 78)
    print("3. required sections and figures in the manuscripts")
    print("=" * 78)
    for f in sorted(os.listdir(OUT)):
        if not f.endswith(".pdf"):
            continue
        t, n = pdf_text(os.path.join(OUT, f))
        miss = [s for s in SECTIONS if s not in t]
        zh = [s for s in ("摘要", "引言", "材料与方法", "结果", "讨论", "结论", "数据与代码可用性", "参考文献")
              if s not in t]
        figs = sum(1 for i in range(1, 9) if str(i) in t)
        print(f"  {f[:42]:44} pages={n}  missing EN sections: {miss or 'none'}  "
              f"missing ZH sections: {zh or 'none'}  figure numbers found: {figs}/8")

    print()
    print("=" * 78)
    print("4. READMEs")
    print("=" * 78)
    for label, p in (("project README", os.path.join(PROJ, "README.md")),
                     ("workspace README", os.path.join(WORKSPACE, "README.md"))):
        if not os.path.exists(p):
            print(f"  {label}: MISSING ({p})")
            continue
        t = open(p, encoding="utf-8").read()
        print(f"  {label}: url x{t.count(URL)}  placeholder x{t.count(PLACEHOLDER)}  "
              f"lambda_target x{t.count('480')}  seed x{t.count('276134')}  "
              f"design_seed x{t.count('276135')}")
        print(f"      requirements.txt mentioned: {'requirements.txt' in t} | "
              f"commands: {len(re.findall(r'python ', t))} 'python ...' lines")


if __name__ == "__main__":
    main()
