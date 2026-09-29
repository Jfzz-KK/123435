"""Shared matplotlib style and the result figures of the paper.

Every figure function takes ``lang`` ("en" or "zh").  For Chinese the labels come
from :mod:`texts`, the CJK font is configured automatically and the figure is
written next to its English twin with a ``_zh`` suffix.

Every figure is written as both PNG (for the Word manuscript) and PDF (vector).
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime  # noqa: E402  (must come before pyplot)
import config as cfg  # noqa: E402
from texts import t  # noqa: E402

import matplotlib  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

plt.rcParams.update(
    {
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 10,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "lines.linewidth": 1.4,
        "figure.autolayout": False,
        "axes.unicode_minus": False,
    }
)

CJK_FONT = None
for _cand in ("Microsoft YaHei", "SimHei", "SimSun", "DengXian"):
    try:
        matplotlib.font_manager.findfont(_cand, fallback_to_default=False)
        CJK_FONT = _cand
        break
    except Exception:
        continue
if CJK_FONT:
    plt.rcParams["font.sans-serif"] = [CJK_FONT, "DejaVu Sans"]
    plt.rcParams["font.family"] = ["sans-serif"]

C_TMM = "#1f4e79"
C_MLP = "#c0392b"
C_ACC = "#e67e22"
C_GREY = "#7f8c8d"


def save(fig, name: str, lang: str = "en", paths=None) -> str:
    paths = paths or cfg.paths()
    if lang != "en":
        name = f"{name}_{lang}"
    png = os.path.join(paths.figures, name + ".png")
    pdf = os.path.join(paths.figures, name + ".pdf")
    fig.savefig(png, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    print("figure:", os.path.relpath(png, paths.root), "+ pdf")
    return png


# --------------------------------------------------------------------------
# Figure 1 -- overall workflow
# --------------------------------------------------------------------------
def fig1_workflow(lang: str = "en", paths=None) -> str:
    fig, ax = plt.subplots(figsize=(7.1, 2.5))
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3.2)

    boxes = [
        (0.05, t("fig1_physics", lang), C_TMM),
        (2.55, t("fig1_data", lang), "#2e86c1"),
        (5.05, t("fig1_mlp", lang), C_MLP),
        (7.55, t("fig1_screen", lang), C_ACC),
    ]
    for x0, label, colour in boxes:
        ax.add_patch(
            FancyBboxPatch(
                (x0, 1.05), 2.0, 1.15,
                boxstyle="round,pad=0.06,rounding_size=0.12",
                linewidth=1.3, edgecolor=colour, facecolor=colour, alpha=0.14,
            )
        )
        ax.text(x0 + 1.0, 1.62, label, ha="center", va="center", fontsize=8, color="#1b2631")
    for x0, _, colour in boxes[:-1]:
        ax.add_patch(
            FancyArrowPatch(
                (x0 + 2.06, 1.62), (x0 + 2.49, 1.62), arrowstyle="-|>",
                mutation_scale=11, linewidth=1.3, color=colour,
            )
        )
    ax.add_patch(
        FancyArrowPatch(
            (8.55, 1.0), (8.55, 0.35), arrowstyle="-|>", mutation_scale=11,
            linewidth=1.3, color=C_GREY,
        )
    )
    ax.text(8.55, 0.25, t("fig1_final", lang), ha="center", va="top", fontsize=8, color="#1b2631")
    ax.add_patch(
        FancyArrowPatch(
            (8.55, 0.35), (6.05, 2.45), arrowstyle="-|>", mutation_scale=11,
            linewidth=1.1, color=C_GREY, linestyle=(0, (4, 3)),
            connectionstyle="arc3,rad=-0.35",
        )
    )
    ax.text(1.05, 2.85, "seed = %d" % cfg.SEED, ha="center", fontsize=7.5, color=C_GREY)
    ax.text(6.05, 2.85, "design_seed = %d" % cfg.DESIGN_SEED, ha="center", fontsize=7.5, color=C_GREY)
    ax.text(3.55, 0.55, t("fig1_split", lang), ha="center", fontsize=7, color=C_GREY)
    return save(fig, "fig1_workflow", lang, paths)


# --------------------------------------------------------------------------
# Figure 2 -- physical model + TMM data generation
# --------------------------------------------------------------------------
def fig2_model(data: dict, lang: str = "en", paths=None) -> str:
    lam = data["wavelengths_nm"]
    spec = data["spectra"]
    thick = data["thickness"]
    rng = np.random.default_rng(7)
    show = rng.choice(len(thick), size=4, replace=False)

    fig, axes = plt.subplots(1, 3, figsize=(7.1, 2.4),
                             gridspec_kw={"width_ratios": [1.05, 1.25, 1.25]})

    ax = axes[0]
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.4, 4.9)
    labels = ["H  $n_H=2.30$", "L  $n_L=1.45$", "H  $n_H=2.30$", "L  $n_L=1.45$"]
    colours = ["#f6c6a8", "#aed6f1", "#f6c6a8", "#aed6f1"]
    for i, (lab, colour) in enumerate(zip(labels, colours)):
        y = 4.0 - i * 1.0
        ax.add_patch(Rectangle((0.08, y), 0.84, 0.95, facecolor=colour,
                               edgecolor="#34495e", linewidth=0.8))
        ax.text(0.5, y + 0.48, lab, ha="center", va="center", fontsize=7)
        ax.text(0.94, y + 0.48, f"$d_{i+1}$", ha="left", va="center", fontsize=7, color="#34495e")
    ax.add_patch(Rectangle((0.08, -0.35), 0.84, 0.5, facecolor="#d5d8dc",
                           edgecolor="#34495e", linewidth=0.8))
    ax.text(0.5, -0.1, "Glass  $n_s=1.52$", ha="center", va="center", fontsize=7)
    ax.text(0.5, 5.25, t("fig2_title", lang), ha="center", fontsize=7.5, color="#1b2631")

    ax = axes[1]
    ax.hist(thick.ravel(), bins=40, color=C_TMM, alpha=0.75, edgecolor="white", linewidth=0.4)
    ax.set_xlabel(t("fig2_x", lang))
    ax.set_ylabel(t("fig2_y", lang))
    ax.set_title(t("fig2_B", lang), fontsize=8.5)

    ax = axes[2]
    for s in show:
        ax.plot(lam, spec[s], lw=1.0, alpha=0.9, label=f"{t('fig2_sample', lang)} {s}")
    ax.set_xlabel(t("fig2_spec_x", lang))
    ax.set_ylabel(t("fig2_spec_y", lang))
    ax.set_ylim(-0.02, 1.02)
    ax.set_title(t("fig2_C", lang), fontsize=8.5)
    ax.legend(frameon=False, fontsize=6.5, loc="lower right")
    fig.tight_layout()
    return save(fig, "fig2_model_and_data", lang, paths)


# --------------------------------------------------------------------------
# Figure 3 -- MLP architecture
# --------------------------------------------------------------------------
def fig3_architecture(n_parameters: int | None = None, lang: str = "en", paths=None) -> str:
    fig, ax = plt.subplots(figsize=(7.1, 2.3))
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.0)
    sizes = [cfg.N_LAYERS] + list(cfg.HIDDEN_SIZES) + [cfg.N_WAVELENGTHS]
    names = [
        t("fig3_input", lang),
        t("fig3_fc", lang, n=cfg.HIDDEN_SIZES[0]),
        t("fig3_fc", lang, n=cfg.HIDDEN_SIZES[1]),
        t("fig3_fc", lang, n=cfg.HIDDEN_SIZES[2]),
        t("fig3_output", lang),
    ]
    xs = np.linspace(0.9, 9.1, len(sizes))
    for x, n, name in zip(xs, sizes, names):
        r = 0.16 + 0.5 * np.sqrt(n / max(sizes))
        ax.add_patch(plt.Circle((x, 2.25), r, facecolor="#d6eaf8", edgecolor=C_TMM, linewidth=1.1))
        ax.text(x, 2.25, str(n), ha="center", va="center", fontsize=7.5, color="#1b2631")
        ax.text(x, 2.25 - r - 0.32, name, ha="center", va="top", fontsize=7)
    for xa, xb in zip(xs[:-1], xs[1:]):
        ax.add_patch(
            FancyArrowPatch((xa + 0.18, 2.25), (xb - 0.18, 2.25), arrowstyle="-|>",
                            mutation_scale=9, linewidth=0.9, color=C_GREY)
        )
    extra = t("fig3_params", lang, n=n_parameters) if n_parameters else ""
    ax.text(5.0, 3.75, t("fig3_title", lang) + extra, ha="center", fontsize=8, color="#1b2631")
    ax.text(5.0, 0.35, t("fig3_footer", lang, lr=cfg.LEARNING_RATE, bs=cfg.BATCH_SIZE,
                         ep=cfg.N_EPOCHS), ha="center", fontsize=7, color=C_GREY)
    return save(fig, "fig3_mlp_architecture", lang, paths)


# --------------------------------------------------------------------------
# Figure 4 -- training / validation loss
# --------------------------------------------------------------------------
def fig4_loss(train_loss, val_loss, best_epoch=None, lang: str = "en", paths=None) -> str:
    fig, ax = plt.subplots(figsize=(3.5, 2.7))
    ep = np.arange(1, len(train_loss) + 1)
    ax.semilogy(ep, train_loss, color=C_TMM, label=t("fig4_train", lang))
    ax.semilogy(ep, val_loss, color=C_MLP, label=t("fig4_val", lang))
    if best_epoch:
        ax.axvline(best_epoch, color=C_GREY, lw=0.8, ls="--")
        ax.annotate(
            t("fig4_best", lang, n=best_epoch),
            xy=(best_epoch, min(val_loss)), xytext=(0.12, 0.12), textcoords="axes fraction",
            fontsize=6.5, color=C_GREY, arrowprops=dict(arrowstyle="-", lw=0.6, color=C_GREY),
        )
    ax.set_xlabel(t("fig4_x", lang))
    ax.set_ylabel(t("fig4_y", lang))
    ax.set_title(t("fig4_title", lang), fontsize=9)
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    return save(fig, "fig4_loss_curve", lang, paths)


# --------------------------------------------------------------------------
# Figure 5 -- TMM vs MLP spectra on test samples
# --------------------------------------------------------------------------
def fig5_prediction(y_true, y_pred, lam, thickness, rows, lang: str = "en", paths=None) -> str:
    n = len(rows)
    fig, axes = plt.subplots(1, n, figsize=(2.35 * n, 2.35), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, r in zip(axes, rows):
        ax.plot(lam, y_true[r], color=C_TMM, label=t("fig5_tmm", lang))
        ax.plot(lam, y_pred[r], color=C_MLP, ls="--", label=t("fig5_mlp", lang))
        mse = float(np.mean((y_pred[r] - y_true[r]) ** 2))
        d = thickness[r]
        ax.set_title(f"$d$ = [{d[0]:.0f}, {d[1]:.0f}, {d[2]:.0f}, {d[3]:.0f}] nm\nMSE = {mse:.2e}",
                     fontsize=7)
        ax.set_xlabel(t("fig5_x", lang))
    axes[0].set_ylabel(t("fig5_y", lang))
    axes[0].set_ylim(-0.03, 1.05)
    axes[-1].legend(frameon=False, fontsize=6.5, loc="upper right")
    fig.suptitle(t("fig5_suptitle", lang, what=t("fig5_what", lang)), fontsize=9, y=1.04)
    fig.tight_layout()
    return save(fig, "fig5_prediction_test_samples", lang, paths)


# --------------------------------------------------------------------------
# Figure 6 -- effect of training-set size
# --------------------------------------------------------------------------
def fig6_training_size(sizes, test_mse, test_rmse, val_mse, lang: str = "en", paths=None) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.6))
    x = np.arange(len(sizes))
    axes[0].bar(x - 0.19, val_mse, width=0.38, color=C_ACC, label=t("fig6_val", lang))
    axes[0].bar(x + 0.19, test_mse, width=0.38, color=C_TMM, label=t("fig6_test", lang))
    axes[0].set_xticks(x, [f"{s}" for s in sizes])
    axes[0].set_xlabel(t("fig6_xt", lang))
    axes[0].set_ylabel(t("fig6_y", lang))
    axes[0].set_title(t("fig6_tA", lang), fontsize=9)
    axes[0].legend(frameon=False, fontsize=7)

    axes[1].plot(sizes, test_rmse, "o-", color=C_TMM, label=t("fig6_tr", lang))
    axes[1].plot(sizes, np.sqrt(val_mse), "s--", color=C_ACC, label=t("fig6_vr", lang))
    axes[1].set_xscale("log")
    axes[1].set_xticks(list(sizes))
    axes[1].set_xticklabels([str(s) for s in sizes])
    axes[1].minorticks_off()
    axes[1].set_xlim(min(sizes) * 0.8, max(sizes) * 1.25)
    axes[1].set_xlabel(t("fig6_xtl", lang))
    axes[1].set_ylabel(t("fig6_yr", lang))
    axes[1].set_title(t("fig6_tB", lang), fontsize=9)
    for xi, yi in zip(sizes, test_rmse):
        axes[1].annotate(f"{yi:.3f}", (xi, yi), textcoords="offset points", xytext=(0, 8),
                         ha="center", fontsize=6.5, color=C_TMM,
                         bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
    axes[1].set_ylim(0.0, float(np.max(np.maximum(test_rmse, np.sqrt(val_mse)))) * 1.25)
    axes[1].legend(frameon=False, fontsize=7, loc="upper right")
    fig.tight_layout()
    return save(fig, "fig6_training_size", lang, paths)


# --------------------------------------------------------------------------
# Figure 7 -- MLP-assisted design
# --------------------------------------------------------------------------
def fig7_design(lam, tmm_best, mlp_best, candidates_tmm, candidates_mlp,
                target_nm, target_R_tmm, rows, lang: str = "en", paths=None) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.7), gridspec_kw={"width_ratios": [1.35, 1]})
    ax = axes[0]
    cand_t = np.asarray(candidates_tmm)
    cand_m = np.asarray(candidates_mlp)
    for i in range(cand_t.shape[0]):
        ax.plot(lam, cand_t[i], color=C_GREY, lw=0.6, alpha=0.55,
                label=t("fig7_cand_t", lang) if i == 0 else None)
        ax.plot(lam, cand_m[i], color=C_MLP, lw=0.6, alpha=0.45, ls=":",
                label=t("fig7_cand_m", lang) if i == 0 else None)
    ax.plot(lam, tmm_best, color=C_TMM, lw=1.9, label=t("fig7_sel_t", lang))
    ax.plot(lam, mlp_best, color=C_MLP, lw=1.5, ls="--", label=t("fig7_sel_m", lang))
    ax.axvline(target_nm, color=C_ACC, lw=1.1, ls="-.")
    ax.annotate(
        f"$\\lambda_{{target}}$ = {target_nm:.0f} nm\n$R_{{TMM}}$ = {target_R_tmm:.4f}",
        xy=(target_nm, target_R_tmm), xytext=(target_nm + 45, 0.16),
        fontsize=7, color=C_ACC, arrowprops=dict(arrowstyle="-|>", lw=0.8, color=C_ACC),
    )
    ax.set_xlabel(t("fig7_x", lang))
    ax.set_ylabel(t("fig7_y", lang))
    ax.set_ylim(-0.03, 1.12)
    ax.set_title(t("fig7_tA", lang), fontsize=9)
    ax.legend(frameon=False, fontsize=6.5, loc="upper center", ncol=2)

    ax = axes[1]
    mlp_r = np.asarray(rows["mlp_R"], dtype=float)
    tmm_r = np.asarray(rows["tmm_R"], dtype=float)
    ax.scatter(mlp_r, tmm_r, s=34, color=C_TMM, zorder=3)
    both = np.concatenate([mlp_r, tmm_r])
    lo, hi = float(both.min()) - 0.006, float(both.max()) + 0.006
    ax.plot([lo, hi], [lo, hi], color=C_GREY, lw=0.8, ls="--", label=t("fig7_parity", lang))
    for i, (mx, tx) in enumerate(zip(mlp_r, tmm_r), start=1):
        ax.annotate(str(i), (mx, tx), textcoords="offset points", xytext=(6, -4), fontsize=7)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(t("fig7_xp", lang))
    ax.set_ylabel(t("fig7_yp", lang))
    ax.set_title(t("fig7_tB", lang), fontsize=9)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.tight_layout()
    return save(fig, "fig7_design", lang, paths)


# --------------------------------------------------------------------------
# Figure 8 -- representative failure case (+ error map of the test set)
# --------------------------------------------------------------------------
def fig8_failure(y_true, y_pred, lam, thickness, idx, per_sample_mse,
                 lang: str = "en", paths=None) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(7.1, 2.5),
                             gridspec_kw={"width_ratios": [1, 1, 1.1]})
    ax = axes[0]
    ax.plot(lam, y_true[idx], color=C_TMM, label=t("fig5_tmm", lang))
    ax.plot(lam, y_pred[idx], color=C_MLP, ls="--", label=t("fig5_mlp", lang))
    d = thickness[idx]
    ax.set_title(t("fig8_worst", lang, d0=d[0], d1=d[1], d2=d[2], d3=d[3]), fontsize=8)
    ax.set_xlabel(t("fig5_x", lang))
    ax.set_ylabel(t("fig5_y", lang))
    ax.set_ylim(-0.03, 1.05)
    ax.legend(frameon=False, fontsize=6.5)

    ax = axes[1]
    ax.plot(lam, y_pred[idx] - y_true[idx], color=C_MLP, lw=1.2)
    ax.axhline(0, color=C_GREY, lw=0.7)
    ax.fill_between(lam, 0, y_pred[idx] - y_true[idx], color=C_MLP, alpha=0.18)
    ax.set_title(t("fig8_err", lang, mse=float(np.mean((y_pred[idx] - y_true[idx]) ** 2))),
                 fontsize=8)
    ax.set_xlabel(t("fig5_x", lang))
    ax.set_ylabel(t("fig8_err_y", lang))

    ax = axes[2]
    order = np.argsort(-per_sample_mse)
    ax.plot(np.arange(1, len(order) + 1), per_sample_mse[order], color=C_TMM, lw=1.2)
    ax.set_yscale("log")
    ax.axhline(float(np.median(per_sample_mse)), color=C_ACC, lw=0.9, ls="--",
               label=t("fig8_median", lang, med=float(np.median(per_sample_mse))))
    top1 = int(np.where(order == idx)[0][0]) + 1
    ax.scatter([top1], [per_sample_mse[idx]], color=C_MLP, zorder=4, s=26,
               label=t("fig8_this", lang, rank=top1, total=len(order)))
    ax.set_title(t("fig8_dist", lang), fontsize=8)
    ax.set_xlabel(t("fig8_rank", lang))
    ax.set_ylabel(t("fig8_perms", lang))
    ax.legend(frameon=False, fontsize=6.5)
    fig.tight_layout()
    return save(fig, "fig8_failure_case", lang, paths)
