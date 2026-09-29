"""Build the Chinese Word manuscript from the same result JSON files.

    python src/make_paper_zh.py      # -> paper/AI4S_研究论文_中文稿_<id>.docx
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docxlib as D  # noqa: E402
from texts_zh import FIG, REFS, build_zh  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TITLE_ZH = "基于多层感知机的多层介质薄膜光谱预测与辅助设计"
TITLE_EN = ("MLP-Based Spectral Prediction and Data-Driven Design of Multilayer "
            "Dielectric Thin Films")


def load(name):
    with open(os.path.join(ROOT, "results", name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    main_j = load("mlp_main_metrics.json")
    sizes_j = load("training_size_study.json")
    screen_j = load("screening_results.json")
    fp = load("dataset_fingerprint.json")
    c = main_j["config"]
    lam_t = screen_j["target_wavelength_nm"]

    blocks = build_zh(main_j, sizes_j, screen_j, fp)
    blocks = [("refs", REFS) if b[0] == "refs" else b for b in blocks]
    figures = [FIG[i] for i in range(1, 9)]

    R = D.add_runs
    preface = (
        D.para(R("研究论文 · RESEARCH ARTICLE", bold=True, size=9, color="1F4E79"))
        + D.para(R(TITLE_ZH, bold=True, size=18), align="center")
        + D.para(R(TITLE_EN, size=11), align="center")
        + D.para(R(f"姓名：{c.get('student_name', '__________')}    学号：{c['student_id']}", size=10),
                 align="center")
        + D.para(R(f"λ_target = {lam_t:.0f} nm    seed = {c['seed']}    "
                   f"design_seed = {c['design_seed']}", italic=True, size=9.5, color="666666"),
                 align="center")
    )

    out = os.path.join(ROOT, "paper", f"AI4S_研究论文_中文稿_{c['student_id']}.docx")
    D.write_docx(
        out, blocks, figures,
        template_dir=os.path.join(ROOT, "templates", "docx_template"),
        core_title=TITLE_ZH, author=c["student_id"], preface_xml=preface,
    )
    print("wrote", os.path.relpath(out, ROOT), f"({os.path.getsize(out)/1024:.0f} kB)")


if __name__ == "__main__":
    main()
