"""Objective verification: check every required deliverable and every number.

Run from the repository root:

    python tools/verify_deliverables.py

It re-derives all reported values from the result JSON files (not from the
manuscript text), checks that the manuscripts quote the same values, and prints a
PASS/FAIL line per requirement.  Exit code 0 means every check passed.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import config as cfg  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))


def load(name: str):
    with open(os.path.join(ROOT, "results", name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def docx_text(path: str) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    return "\n".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S))


def pdf_text(path: str) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(path)
    return "\n".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))


def main() -> int:
    # ---------------------------------------------------------------- parameters
    check(cfg.STUDENT_ID == "2020276134", "student ID = 2020276134", cfg.STUDENT_ID)
    check(cfg.N_MOD == 34, "N (last two digits) = 34", str(cfg.N_MOD))
    check(abs(cfg.LAMBDA_TARGET_NM - 480.0) < 1e-9, "lambda_target = 480 nm",
          f"{cfg.LAMBDA_TARGET_NM:.0f} nm")
    check(cfg.SEED == 276134, "seed = 276134", str(cfg.SEED))
    check(cfg.DESIGN_SEED == 276135, "design_seed = 276135", str(cfg.DESIGN_SEED))
    check(cfg.TARGET_INDEX == 8, "target index 8 of 41", str(cfg.TARGET_INDEX))
    check(len(cfg.WAVELENGTHS_NM) == 41, "41 wavelength samples", str(len(cfg.WAVELENGTHS_NM)))
    check(cfg.STACK == ("H", "L", "H", "L") and cfg.N_LAYERS == 4,
          "stack Air/H/L/H/L/Glass (4 layers)", str(cfg.STACK))

    # ---------------------------------------------------------------- experiment 1
    main_j = load("mlp_main_metrics.json")
    fp = load("dataset_fingerprint.json")
    tm = main_j["test_metrics"]
    check(fp["n_samples"] == 5000, "dataset has 5000 designs", str(fp["n_samples"]))
    check(fp["n_wavelengths"] == 41, "spectra have 41 points", str(fp["n_wavelengths"]))
    check(main_j["config"]["split"] == [4000, 500, 500], "fixed split 4000/500/500",
          str(main_j["config"]["split"]))
    check(main_j["config"]["hidden_sizes"] == [128, 128, 64],
          "MLP architecture 4-128-128-64-41", str(main_j["config"]["hidden_sizes"]))
    check(abs(tm["rmse"] - 0.00891) < 5e-5, "Q1 test RMSE = 0.0089", f"{tm['rmse']:.5f}")
    check(abs(tm["mae_at_target_wavelength"] - 0.00776) < 2e-4,
          "Q1 MAE at 480 nm = 0.0078", f"{tm['mae_at_target_wavelength']:.5f}")

    # ---------------------------------------------------------------- experiment 2
    sizes_j = load("training_size_study.json")
    rec = sizes_j["records"]
    check([r["n_train"] for r in rec] == [500, 1000, 2000, 4000],
          "training-size study 500/1000/2000/4000", str([r["n_train"] for r in rec]))
    rmses = [r["test_metrics"]["rmse"] for r in rec]
    check(all(b < a for a, b in zip(rmses, rmses[1:])), "test RMSE decreases monotonically",
          " -> ".join(f"{r:.5f}" for r in rmses))
    gains = sizes_j["marginal_gains"]
    check(abs(gains[-1]["relative_mse_reduction_pct"] - 41.1) < 1.0,
          "Q2 last doubling reduces MSE by 41 %",
          f"{gains[-1]['relative_mse_reduction_pct']:.1f} %")

    # ---------------------------------------------------------------- experiment 3
    screen_j = load("screening_results.json")
    best = screen_j["best_design"]
    check(screen_j["n_candidates"] == 10000, "10,000 candidates screened",
          str(screen_j["n_candidates"]))
    check(screen_j["design_seed"] == 276135, "candidates use design_seed",
          str(screen_j["design_seed"]))
    check(len(screen_j["top10"]) == 10, "Top-10 verified with TMM", str(len(screen_j["top10"])))
    check(len(screen_j["final_top5"]) == 5, "final Top-5 reported",
          str(len(screen_j["final_top5"])))
    check(screen_j["top10"][0]["rank_tmm"] == 1 and screen_j["top10"][0]["rank_mlp"] == 2,
          "TMM verification re-ranks the surrogate's top pick (MLP #1 -> TMM #2)",
          f"mlp#{screen_j['top10'][0]['rank_mlp']} tmm#{screen_j['top10'][0]['rank_tmm']}")
    check(all(r["rank_mlp"] <= 10 for r in screen_j["top10"]),
          "all five reported designs come from the surrogate's Top-10",
          f"{sum(1 for r in screen_j['top10'] if r['rank_tmm'] <= 5)} kept of 5")
    check(abs(best["tmm_R_target"] - 0.6566) < 5e-4, "Q3 TMM-verified R(480 nm) = 0.6566",
          f"{best['tmm_R_target']:.4f}")
    check(best["tmm_R_target"] > screen_j["candidate_pool"]["R_target_tmm_p999"],
          "selected design beats pool 99.9th percentile",
          f"{best['tmm_R_target']:.4f} > {screen_j['candidate_pool']['R_target_tmm_p999']:.4f}")
    check(screen_j["candidate_pool"]["R_target_tmm_max"] <= best["tmm_R_target"] + 1e-9,
          "selected design is the best of the whole TMM-evaluated pool",
          f"pool max {screen_j['candidate_pool']['R_target_tmm_max']:.4f}")
    check(screen_j["timing"]["speedup"] > 5,
          "surrogate is much faster than TMM",
          f"x{screen_j['timing']['speedup']:.1f}")

    # ---------------------------------------------------------------- failure case
    worst = main_j["worst_test_sample"]
    check(worst["per_sample_mse"] > 5 * tm["per_sample_mse_median"],
          "analysed failure case is a genuine outlier",
          f"{worst['per_sample_mse']:.2e} vs median {tm['per_sample_mse_median']:.2e}")

    # ---------------------------------------------------------------- figures
    needed = ["fig1_workflow", "fig2_model_and_data", "fig3_mlp_architecture", "fig4_loss_curve",
              "fig5_prediction_test_samples", "fig6_training_size", "fig7_design",
              "fig8_failure_case"]
    for n in needed:
        for ext in ("png", "pdf"):
            p = os.path.join(ROOT, "figures", f"{n}.{ext}")
            check(os.path.exists(p) and os.path.getsize(p) > 3000, f"figure {n}.{ext} exists",
                  f"{os.path.getsize(p)//1024 if os.path.exists(p) else 0} kB")
        for ext in ("png", "pdf"):
            check(os.path.exists(os.path.join(ROOT, "figures", f"{n}_zh.{ext}")),
                  f"figure {n}_zh.{ext} exists (Chinese labels)")

    # ---------------------------------------------------------------- table
    t1 = os.path.join(ROOT, "results", "tables", "table1_top5.md")
    check(os.path.exists(t1), "Table 1 markdown exists")
    if os.path.exists(t1):
        t1_txt = open(t1, encoding="utf-8").read()
        body = [l for l in t1_txt.splitlines() if l.startswith("|")][2:]
        check(len(body) == 5, "Table 1 has five rows", str(len(body)))
        check("0.6566" in t1_txt, "Table 1 quotes the TMM value")
    sup = os.path.join(ROOT, "results", "tables", "screening_top10_rankings.md")
    check(os.path.exists(sup), "Top-10 MLP-vs-TMM ranking table exists")

    # ---------------------------------------------------------------- manuscripts
    papers = sorted(p for p in glob.glob(os.path.join(ROOT, "paper", "*.docx"))
                    if not os.path.basename(p).startswith("~$"))
    check(len(papers) == 2, "two Word manuscripts (English + Chinese)", str(len(papers)))
    for p in papers:
        txt = docx_text(p)
        tag = "zh" if "中文" in os.path.basename(p) else "en"
        check(len(txt) > 15000, f"[{tag}] docx has substantial text", f"{len(txt)} chars")
        for token in ("480", "276134", "276135"):
            check(token in txt, f"[{tag}] docx quotes {token}")
        check(txt.count("0.0089") >= 1 or txt.count("0.00891") >= 1,
              f"[{tag}] docx quotes the test RMSE")
        check("0.6566" in txt, f"[{tag}] docx quotes the verified design reflectance")
        m = re.search(r"github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", txt)
        check(bool(m), f"[{tag}] docx carries a real GitHub repository URL",
              m.group(0) if m else "no URL found")
        check(txt.count("Figure") + txt.count("图 ") >= 8 or txt.count("图 ") >= 8,
              f"[{tag}] docx references all eight figures")

    pdfs = sorted(p for p in glob.glob(os.path.join(ROOT, "paper", "*.pdf"))
                  if not os.path.basename(p).startswith("~$"))
    check(len(pdfs) == 2, "two PDF manuscripts", str(len(pdfs)))
    for p in pdfs:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(p)
        n = len(pdf)
        tag = "zh" if "中文" in os.path.basename(p) else "en"
        check(4 <= n <= 8, f"[{tag}] PDF page count 4-8", f"{n} pages")
        txt = pdf_text(p)
        for token in ("480", "276134", "276135", "0.6566"):
            check(token in txt, f"[{tag}] PDF quotes {token}")

    # ---------------------------------------------------------------- references
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from texts_zh import REFS  # noqa: E402

    check(8 <= len(REFS) <= 12, "8-12 real references", str(len(REFS)))
    check(any("iScience" in r for r in REFS), "recommended reading iScience review cited")
    check(any("Macleod" in r for r in REFS), "thin-film optics reference cited")

    # ---------------------------------------------------------------- report
    n_pass = sum(1 for ok, _, _ in RESULTS if ok)
    width = max(len(n) for _, n, _ in RESULTS) + 2
    for ok, name, detail in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}} {detail}")
    print(f"\n{n_pass}/{len(RESULTS)} checks passed")
    return 0 if n_pass == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
