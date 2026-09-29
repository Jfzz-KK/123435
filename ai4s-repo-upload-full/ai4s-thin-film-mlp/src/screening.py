"""Experiment 3.3 -- MLP-assisted screening of thin-film designs.

Pipeline (assignment section 2.6):

1. generate 10,000 *new* candidate thickness vectors with ``design_seed``
   (so that they cannot coincide with the training data);
2. predict every candidate spectrum with the trained MLP and rank the
   candidates by the predicted reflectance at the personal target wavelength;
3. take the Top-10 candidates and recompute their true spectra with TMM;
4. re-rank with TMM, report the final Top-5 in Table 1 of the paper.

The script also measures how much faster the surrogate is than TMM, which is the
whole point of using a surrogate for screening.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg  # noqa: E402
import runtime  # noqa: E402
import viz  # noqa: E402
from data import build_dataset  # noqa: E402
from tmm import ThinFilmStack  # noqa: E402
from train_utils import MLPSurrogate, predict  # noqa: E402

import torch  # noqa: E402

TOP_K_VERIFY = 10
TOP_K_FINAL = 5


def generate_candidates(seed: int, n: int) -> np.ndarray:
    """Candidate thicknesses drawn with ``design_seed`` (independent of training)."""
    rng = np.random.default_rng(seed)
    return rng.uniform(cfg.D_MIN_NM, cfg.D_MAX_NM, size=(n, cfg.N_LAYERS))


def load_model(paths, pool_size: int | None = None) -> MLPSurrogate:
    name = "mlp_main.pt" if pool_size in (None, cfg.N_TRAIN) else f"mlp_n{pool_size}.pt"
    blob = torch.load(os.path.join(paths.models, name), map_location="cpu", weights_only=False)
    model = MLPSurrogate(hidden_sizes=tuple(blob["hidden_sizes"]), seed=int(blob["seed"]))
    model.load_state_dict(blob["state_dict"])
    model.eval()
    return model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", choices=["en", "zh"])
    args = ap.parse_args()
    lang = args.lang

    paths = cfg.paths()
    runtime.seed_everything(cfg.SEED)

    data = build_dataset(verbose=False)
    lam = data["wavelengths_nm"]
    stack = ThinFilmStack(cfg.STACK, cfg.N_H, cfg.N_L, cfg.N_S, cfg.N_INC)
    model = load_model(paths)

    # ---- timing of both forward models for the same 10,000 designs ----------
    cand = generate_candidates(cfg.DESIGN_SEED, cfg.N_CANDIDATES)
    t0 = time.perf_counter()
    R_mlp = predict(model, cand)
    t_mlp = time.perf_counter() - t0
    t0 = time.perf_counter()
    R_tmm_all = stack.reflectance(cand, lam)
    t_tmm = time.perf_counter() - t0
    print(
        f"forward-model timing for {len(cand)} designs: MLP {t_mlp:.3f} s, "
        f"TMM {t_tmm:.3f} s  (speed-up x{t_tmm / t_mlp:.1f})"
    )

    # ---- screening with the surrogate --------------------------------------
    ti = cfg.TARGET_INDEX
    R_mlp_target = R_mlp[:, ti]
    order = np.argsort(-R_mlp_target)[:TOP_K_VERIFY]
    top = cand[order]
    R_tmm_top = stack.reflectance(top, lam)
    R_tmm_target = R_tmm_top[:, ti]
    R_mlp_top = R_mlp[order][:, ti]

    # ---- TMM re-ranking of the Top-10 --------------------------------------
    rank_tmm = np.argsort(-R_tmm_target)          # positions in `top`
    final = rank_tmm[:TOP_K_FINAL]
    rank_mlp = np.argsort(-R_mlp_top)             # positions in `top`

    rows = []
    for pos_in_top in rank_tmm:
        rows.append(
            {
                "rank_mlp": int(np.where(rank_mlp == pos_in_top)[0][0]) + 1,
                "rank_tmm": int(np.where(rank_tmm == pos_in_top)[0][0]) + 1,
                "candidate_index": int(order[pos_in_top]),
                "d_nm": [float(v) for v in top[pos_in_top]],
                "mlp_R_target": float(R_mlp_top[pos_in_top]),
                "tmm_R_target": float(R_tmm_target[pos_in_top]),
                "mlp_target_error": float(R_mlp_top[pos_in_top] - R_tmm_target[pos_in_top]),
                "absorbed": bool(np.where(rank_tmm == pos_in_top)[0][0] < TOP_K_FINAL),
            }
        )

    best = final[0]
    best_d = top[best]
    best_tmm = float(R_tmm_top[best, ti])
    best_tmm_spectrum = R_tmm_top[best]

    # spectral error of the surrogate over the whole candidate pool at lambda_t
    spec_err = R_mlp - R_tmm_all
    metrics = {
        "n_candidates": int(cfg.N_CANDIDATES),
        "target_wavelength_nm": float(cfg.LAMBDA_TARGET_NM),
        "target_index": int(ti),
        "timing": {
            "mlp_seconds": float(t_mlp),
            "tmm_seconds": float(t_tmm),
            "speedup": float(t_tmm / t_mlp),
        },
        "candidate_pool": {
            "R_target_tmm_min": float(R_tmm_all[:, ti].min()),
            "R_target_tmm_max": float(R_tmm_all[:, ti].max()),
            "R_target_tmm_mean": float(R_tmm_all[:, ti].mean()),
            "R_target_tmm_p999": float(np.percentile(R_tmm_all[:, ti], 99.9)),
            "spectrum_mse": float(np.mean(spec_err**2)),
            "spectrum_mae": float(np.mean(np.abs(spec_err))),
            "R_target_mse": float(np.mean(spec_err[:, ti] ** 2)),
            "R_target_mae": float(np.mean(np.abs(spec_err[:, ti]))),
            "R_target_max_abs_error": float(np.max(np.abs(spec_err[:, ti]))),
        },
        "top10": rows,
        "final_top5": [rows[i] for i in range(TOP_K_FINAL)],
        "best_design": {
            "d_nm": [float(v) for v in best_d],
            "mlp_R_target": float(R_mlp_top[best]),
            "tmm_R_target": float(best_tmm),
            "absolute_error": float(abs(R_mlp_top[best] - best_tmm)),
            "mlp_spectrum": [float(v) for v in R_mlp[order][best]],
        },
        "design_seed": int(cfg.DESIGN_SEED),
        "seed": int(cfg.SEED),
    }

    # ---- Figure 7 ----------------------------------------------------------
    final = rank_tmm[:TOP_K_FINAL]
    viz.fig7_design(
        lam,
        best_tmm_spectrum,
        R_mlp[order][best],
        R_tmm_top[final],
        R_mlp[order][final],
        cfg.LAMBDA_TARGET_NM,
        float(best_tmm),
        {"mlp_R": R_mlp_top[final], "tmm_R": R_tmm_target[final]},
        lang,
        paths,
    )

    np.savez_compressed(
        os.path.join(paths.results, "screening.npz"),
        candidates=cand,
        R_mlp=R_mlp,
        R_tmm_target=R_tmm_all[:, ti],
        top_index=order,
        best_d=best_d,
    )

    runtime.dump_json(metrics, os.path.join(paths.results, "screening_results.json"))

    # ---- Table 1 as markdown (the paper table is generated from this) ------
    lines = [
        "| Rank | d1 (nm) | d2 (nm) | d3 (nm) | d4 (nm) | MLP R_target | TMM R_target |",
        "|---|---|---|---|---|---|---|",
    ]
    for i in range(TOP_K_FINAL):
        r = rows[i]
        lines.append(
            "| %d | %.1f | %.1f | %.1f | %.1f | %.4f | %.4f |"
            % (i + 1, *r["d_nm"], r["mlp_R_target"], r["tmm_R_target"])
        )
    table_md = "\n".join(lines) + "\n"
    with open(os.path.join(paths.tables, "table1_top5.md"), "w", encoding="utf-8") as fh:
        fh.write(table_md)
    print(table_md)

    # ---------------- Top-10 with both rankings (supplementary material) ------
    sup = [
        "| MLP rank | TMM rank | d1 (nm) | d2 (nm) | d3 (nm) | d4 (nm) | MLP R_target | TMM R_target |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: x["rank_mlp"]):
        sup.append(
            "| %d | %d | %.1f | %.1f | %.1f | %.1f | %.4f | %.4f |"
            % (r["rank_mlp"], r["rank_tmm"], *r["d_nm"], r["mlp_R_target"], r["tmm_R_target"])
        )
    with open(os.path.join(paths.tables, "screening_top10_rankings.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(sup) + "\n")
    print("wrote results/tables/screening_top10_rankings.md")


if __name__ == "__main__":
    main()
