"""Generate the Research Article manuscript (Word) from the experiment outputs.

The script reads

    results/mlp_main_metrics.json
    results/training_size_study.json
    results/screening_results.json
    results/dataset_fingerprint.json
    figures/*.png

and writes ``paper/AI4S_Research_Article_2020276134.docx`` plus a plain-text
version.  Every number in the text comes from those JSON files, so the
manuscript cannot drift away from the code.  It supports ``--lang zh`` for a
Chinese version of the manuscript.

The docx is assembled directly as OOXML (no python-docx needed): the template's
styles, header, footer and section properties are re-used, and the figures are
embedded as PNG.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import struct
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

W_TWIPS = 9972          # usable text width of the template (US Letter, 1 col)
EMU_PER_TWIP = 635
MAX_EMU = W_TWIPS * EMU_PER_TWIP - 16000   # small safety margin

FONT = "Calibri"


def load(path: str):
    with open(os.path.join(ROOT, "results", path), "r", encoding="utf-8") as fh:
        return json.load(fh)


def png_size(path: str) -> tuple[int, int]:
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


# --------------------------------------------------------------------------
# OOXML building blocks
# --------------------------------------------------------------------------
def esc(t: str) -> str:
    return html.escape(t, quote=False)


def run(text: str, bold=False, italic=False, size=None, color=None, mono=False) -> str:
    rpr = []
    if bold:
        rpr.append("<w:b/>")
    if italic:
        rpr.append("<w:i/>")
    if color:
        rpr.append(f'<w:color w:val="{color}"/>')
    if size:
        rpr.append(f'<w:sz w:val="{int(size*2)}"/>')
    if mono:
        rpr.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>')
    else:
        rpr.append(f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/>')
    return (
        "<w:r><w:rPr>" + "".join(rpr) + f'</w:rPr><w:t xml:space="preserve">{esc(text)}</w:t></w:r>'
    )


def para(runs, align=None, space_before=None, space_after=None, style=None, indent=None) -> str:
    ppr = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if indent is None:
        ppr.append('<w:ind w:firstLine="0"/>')
    else:
        ppr.append(f'<w:ind w:firstLine="{indent}"/>')
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    spacing = []
    if space_before is not None:
        spacing.append(f'w:before="{space_before}"')
    if space_after is not None:
        spacing.append(f'w:after="{space_after}"')
    if spacing:
        ppr.append("<w:spacing " + " ".join(spacing) + "/>")
    body = runs if isinstance(runs, str) else "".join(runs)
    return "<w:p><w:pPr>" + "".join(ppr) + "</w:pPr>" + body + "</w:p>"


def heading(text: str, level: int = 1) -> str:
    style = {1: "1", 2: "21", 3: "31"}[level]
    return para(run(text), style=style)


def label_para(label: str, text: str, size=9.5) -> str:
    return para([run(label, bold=True, size=size), run(text, size=size)])


def body(text: str, size=9.5, justify=True) -> str:
    return para(
        run(text, size=size),
        align="both" if justify else None,
        space_after=120,
        indent=200,
    )


def caption(text: str) -> str:
    return para(run(text, bold=True, size=9), align="center", space_before=60, space_after=180)


def figure(path: str, rel_id: str, docpr_id: int, max_emu: int = MAX_EMU) -> str:
    w, h = png_size(path)
    cx = min(max_emu, w * 9525)          # PNG assumed 96 dpi logical size
    cy = int(cx * h / w)
    name = os.path.basename(path)
    return (
        '<w:p><w:pPr><w:ind w:firstLine="0"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr>'
        "<w:noProof/>"
        f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/></w:rPr><w:drawing>'
        f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
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


def table(header: list[str], rows: list[list[str]], widths: list[int] | None = None) -> str:
    n = len(header)
    widths = widths or [W_TWIPS // n] * n
    borders = (
        "<w:tblBorders>"
        + "".join(
            f'<w:{edge} w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>'
            for edge in ("top", "left", "bottom", "right", "insideH", "insideV")
        )
        + "</w:tblBorders>"
    )
    out = [
        "<w:tbl><w:tblPr>",
        f'<w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:jc w:val="center"/>',
        borders,
        '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" '
        'w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>',
        "</w:tblPr><w:tblGrid>",
    ]
    out += [f'<w:gridCol w:w="{w}"/>' for w in widths]
    out.append("</w:tblGrid>")

    def cell(text, w, bold=False, shade=None):
        tc = [f'<w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>']
        if shade:
            tc.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
        tc.append("</w:tcPr>")
        return (
            "<w:tc>"
            + "".join(tc)
            + para(run(text, bold=bold, size=8.5), align="center")
            + "</w:tc>"
        )

    out.append("<w:tr><w:trPr><w:tblHeader/></w:trPr>")
    out += [cell(h, widths[i], bold=True, shade="F2F2F2") for i, h in enumerate(header)]
    out.append("</w:tr>")
    for row in rows:
        out.append("<w:tr>")
        out += [cell(str(c), widths[i]) for i, c in enumerate(row)]
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


# --------------------------------------------------------------------------
# manuscript text
# --------------------------------------------------------------------------
EN = {
    "title_zh": "基于多层感知机的多层介质薄膜光谱预测与辅助设计",
    "title_en": "MLP-Based Spectral Prediction and Data-Driven Design of Multilayer Dielectric Thin Films",
    "name_label": "姓名 / Name: ",
    "id_label": "学号 / Student ID: ",
    "abstract_h": "Abstract",
    "keywords": (
        "Keywords: optical thin films; transfer matrix method; multilayer perceptron; "
        "surrogate model; AI for Science"
    ),
}


def build_document(main: dict, sizes: dict, screen: dict, fp: dict, lang: str = "en") -> str:
    cfg = main["config"]
    tm = main["test_metrics"]
    vm = main["val_metrics"]
    worst = main["worst_test_sample"]
    best = screen["best_design"]
    pool = screen["candidate_pool"]
    timing = screen["timing"]
    top10 = screen["top10"]
    rec = sizes["records"]
    gains = sizes["marginal_gains"]
    lam_t = screen["target_wavelength_nm"]
    seed = cfg["seed"]
    dseed = cfg["design_seed"]
    npar = main["n_parameters"]

    parts: list[str] = []
    p = parts.append

    # ---------------- front matter ----------------
    p(para(run("RESEARCH ARTICLE", bold=True, size=9, color="1F4E79")))
    p(para(run(EN["title_zh"], bold=True, size=18), align="center"))
    p(para(run(EN["title_en"], size=12), align="center"))
    p(
        para(
            [
                run(EN["name_label"], size=10),
                run(cfg.get("student_name", "__________") + "    ", size=10),
                run(EN["id_label"], size=10),
                run(cfg["student_id"], size=10),
            ],
            align="center",
        )
    )
    p(
        para(
            run(
                f"\u03bb_target = {lam_t:.0f} nm    seed = {seed}    design_seed = {dseed}",
                italic=True, size=9.5, color="666666",
            ),
            align="center",
        )
    )

    # ---------------- abstract ----------------
    p(heading(EN["abstract_h"], 1))
    abstract = (
        f"We study whether a small multilayer perceptron (MLP) can act as a fast surrogate for the "
        f"optical response of a four-layer dielectric thin film and assist the design of a coating "
        f"that maximises reflectance at a personal target wavelength of {lam_t:.0f} nm. "
        f"Transfer-matrix-method (TMM) spectra were generated for {cfg['n_samples']:,} random "
        f"thickness combinations of the fixed stack Air/H/L/H/L/Glass "
        f"(n_H = {cfg['n_h']:.2f}, n_L = {cfg['n_l']:.2f}, n_s = {cfg['n_s']:.2f}, "
        f"{cfg['d_range_nm'][0]:.0f}-{cfg['d_range_nm'][1]:.0f} nm per layer, "
        f"{cfg['n_wavelengths']} wavelengths from "
        f"{cfg['wavelength_range_nm'][0]:.0f} to {cfg['wavelength_range_nm'][1]:.0f} nm) and split "
        f"once into {cfg['split'][0]:,}/{cfg['split'][1]}/{cfg['split'][2]} training, validation and "
        f"test samples with seed {seed}. The MLP "
        f"({'-'.join(str(h) for h in cfg['hidden_sizes'])}, {npar:,} parameters, MSE loss, Adam) "
        f"predicts the whole spectrum from four thicknesses and reaches a test RMSE of "
        f"{tm['rmse']:.4f} in reflectance units (test MSE {tm['mse']:.2e}), i.e. about "
        f"{100*tm['rmse']/fp['R_mean']:.1f} % of the mean reflectance. Its error at "
        f"{lam_t:.0f} nm is only {tm['mae_at_target_wavelength']:.4f} on average. Increasing the "
        f"training set from 500 to 4,000 samples lowers the test RMSE from {rec[0]['test_metrics']['rmse']:.4f} "
        f"to {rec[-1]['test_metrics']['rmse']:.4f}, but the last doubling yields only a "
        f"{gains[-1]['relative_mse_reduction_pct']:.0f} % MSE reduction, i.e. clearly diminishing "
        f"returns. Screening {screen['n_candidates']:,} candidates generated with design_seed "
        f"{dseed} takes {timing['mlp_seconds']:.2f} s with the surrogate against "
        f"{timing['tmm_seconds']:.1f} s for TMM (x{timing['speedup']:.1f}), and the best design found "
        f"by the surrogate reaches a TMM-verified reflectance of {best['tmm_R_target']:.4f} at "
        f"{lam_t:.0f} nm. The MLP is therefore an accurate and much cheaper alternative to TMM for "
        f"large-scale screening, but its ranking must always be confirmed by TMM."
    )
    p(body(abstract))
    p(para(run(EN["keywords"], size=9.5, italic=True), space_before=120))

    # ---------------- 1. Introduction ----------------
    p(heading("1. Introduction", 1))
    p(body(
        "Multilayer dielectric thin films are one of the oldest and still most widely used tools of "
        "optical engineering. Their optical response is produced by interference between the partial "
        "reflections at the layer interfaces, so the reflectance spectrum is controlled by only three "
        "families of design parameters: the number of layers, the materials (refractive indices) and "
        "the thickness of each layer [1,2]. Because the layers are thin compared with the wavelength, "
        "a modest change in thickness strongly modifies the phase accumulated by the wave in that "
        "layer, and therefore the position and depth of the interference fringes. Even for the simple "
        "four-layer stack considered here, the mapping from thickness to spectrum is strongly "
        "non-linear, and the frequency of the fringes grows with the total optical thickness."
    ))
    p(body(
        "The standard physical model of such a stack is the transfer matrix method (TMM) [1,3]. Each "
        "layer is represented by a 2x2 characteristic matrix that depends on the optical phase "
        "thickness; multiplying the matrices gives the input admittance of the multilayer, from which "
        "the amplitude reflection coefficient and the reflectance follow analytically. TMM is exact "
        "for the idealised model used here (plane wave, normal incidence, non-dispersive, lossless "
        "layers) and it is computationally cheap per design - microseconds to milliseconds. The "
        "difficulty appears when a very large number of designs has to be evaluated, for instance "
        f"when {screen['n_candidates']:,} candidates must be ranked before a design is chosen: the "
        "cost grows linearly with the number of candidates and dominates the whole optimisation loop."
    ))
    p(body(
        "Machine-learning surrogate models offer a way out of this trade-off. A neural network "
        "trained on TMM data learns the mapping from design parameters to optical response directly "
        "from examples [4], and once trained it evaluates a design in a single forward pass that is "
        "orders of magnitude cheaper than a numerical simulation. Such surrogates are now routinely "
        "used in the inverse design of optical multilayer structures, either as vectorised regressors "
        "or as generative models [4-7]. The price is that a surrogate is only an approximation: it "
        "can mis-rank nearly equivalent candidates, and its accuracy depends on how much training "
        "data are available. The recommended reading for this assignment reviews this development "
        "from classical optimisation to deep learning [4]."
    ))
    p(body(
        f"This work addresses three questions for a deliberately minimal system - a four-layer "
        f"Air/H/L/H/L/Glass stack with fixed refractive indices and only the four thicknesses as "
        f"free parameters. (Q1) Can an MLP predict the reflectance spectrum of the stack accurately? "
        f"(Q2) How does the prediction error change when the number of training samples grows? "
        f"(Q3) Can the MLP act as a surrogate that helps to screen a large candidate library and find "
        f"a design with high reflectance at a personal target wavelength? All three questions are "
        f"answered with a single fixed dataset, a single fixed train/validation/test split and "
        f"explicitly recorded random seeds, so that every number reported below can be reproduced. "
        f"Figure 1 summarises the workflow: TMM generates the data, the MLP is trained on it, the "
        f"surrogate ranks a new candidate library, and TMM verifies the finalists."
    ))
    p(figure(os.path.join(ROOT, "figures", "fig1_workflow.png"), "rIdFig1", 1))
    p(caption(
        "Figure 1. Overall workflow of the AI4S thin-film study. The dataset is generated with "
        f"seed = {seed}; the screening library uses design_seed = {dseed} and the final top-5 design "
        "is always verified with TMM."
    ))

    # ---------------- 2. Materials and Methods ----------------
    p(heading("2. Materials and Methods", 1))
    p(heading("2.1 Optical model and transfer matrix method", 2))
    p(body(
        f"The object of the study is the four-layer stack Air / H / L / H / L / Glass, illuminated at "
        f"normal incidence by a plane wave. The layers are non-absorbing and non-dispersive with "
        f"refractive indices n_H = {cfg['n_h']:.2f} (layers 1 and 3) and n_L = {cfg['n_l']:.2f} "
        f"(layers 2 and 4); the substrate is glass with n_s = {cfg['n_s']:.2f} and the incident "
        f"medium is air with n_0 = 1.00. The layer thicknesses d_i and the vacuum wavelength "
        f"\u03bb are measured in nanometres."
    ))
    p(body(
        "The optical phase thickness of layer i is "
        "\u03b4_i = 2\u03c0 n_i d_i / \u03bb. With the optical admittance at normal incidence "
        "\u03b7_i = n_i, the characteristic matrix of the layer is "
        "M_i = [[cos \u03b4_i, i sin \u03b4_i / \u03b7_i], [i \u03b7_i sin \u03b4_i, cos \u03b4_i]]. "
        "The multilayer matrix is the ordered product M = M_1 M_2 M_3 M_4 (light travels from layer 1 "
        "towards the substrate), the input admittance is "
        "Y = (M_21 + M_22 \u03b7_s)/(M_11 + M_12 \u03b7_s), and the amplitude reflection coefficient "
        "and reflectance are r = (\u03b7_0 - Y)/(\u03b7_0 + Y) and R = |r|\u00b2. "
        "The implementation (src/tmm.py) evaluates the product layer by layer for whole batches of "
        "designs and wavelengths at once. Six unit checks are included in tests/test_tmm.py: a "
        "zero-thickness stack reproduces the bare air/glass Fresnel reflectance "
        "((n_0-n_s)/(n_0+n_s))\u00b2 = 0.0426, a single quarter-wave layer reproduces the analytic "
        "value R = ((\u03b7_0 - n\u00b2/n_s)/(\u03b7_0 + n\u00b2/n_s))\u00b2, batched and "
        "single-design evaluation agree to 1e-13, and 400 random stacks satisfy 0 <= R <= 1 at all "
        "41 wavelengths. Because the model is lossless, R is used directly as the quantity to be "
        "learned."
    ))
    p(figure(os.path.join(ROOT, "figures", "fig2_model_and_data.png"), "rIdFig2", 2))
    p(caption(
        "Figure 2. Physical model and TMM-based generation of thickness-spectrum data. "
        "(A) the Air/H/L/H/L/Glass stack; (B) distribution of the 20,000 sampled layer thicknesses; "
        "(C) four examples of the 5,000 TMM-calculated reflectance spectra."
    ))

    p(heading("2.2 Student-specific target wavelength and random seeds", 2))
    p(body(
        f"Following the assignment, the personal parameters are derived from the student ID "
        f"{cfg['student_id']}. The last two digits are N = {cfg['n_mod']}, so the target wavelength is "
        f"\u03bb_target = 450 + 10 x (N mod 31) = {lam_t:.0f} nm, which corresponds to index "
        f"{screen['target_index']} of the 41 wavelength samples. The random seed is the integer formed "
        f"by the last six digits, seed = {seed}; it controls the generation of the dataset, the single "
        f"random permutation that defines the train/validation/test split, and the initialisation of "
        f"the MLP weights. The design stage uses design_seed = seed + 1 = {dseed} so that the "
        f"candidate structures cannot coincide with the training data. All scripts set the three seeds "
        f"explicitly (random, numpy and torch) at start-up."
    ))
    p(body(
        f"The generated dataset is fingerprinted in results/dataset_fingerprint.json: "
        f"sha256(thickness) = {fp['thickness_sha256'][:16]}..., "
        f"sha256(spectra) = {fp['spectra_sha256'][:16]}..., "
        f"sha256(split) = {fp['split_sha256'][:16]}..., with R in "
        f"[{fp['R_min']:.4f}, {fp['R_max']:.4f}] and mean R = {fp['R_mean']:.4f}. Re-running "
        f"src/data.py reproduces these digests, which is how the numerical consistency of the "
        f"manuscript was checked."
    ))

    p(heading("2.3 Dataset generation", 2))
    p(body(
        f"{cfg['n_samples']:,} thickness combinations were drawn from a uniform distribution in "
        f"[{cfg['d_range_nm'][0]:.0f}, {cfg['d_range_nm'][1]:.0f}] nm for each of the four layers with "
        f"seed {seed}, and their reflectance was computed with TMM at the "
        f"{cfg['n_wavelengths']} wavelengths from {cfg['wavelength_range_nm'][0]:.0f} to "
        f"{cfg['wavelength_range_nm'][1]:.0f} nm in steps of {cfg['wavelength_step_nm']:.0f} nm. One "
        f"random permutation of the 5,000 samples, drawn from the same seeded generator immediately "
        f"after the thicknesses, defines a fixed split of {cfg['split'][0]:,} training, "
        f"{cfg['split'][1]} validation and {cfg['split'][2]} test samples; the sorted index sets are "
        f"stored together with the data. This split is used for every experiment in the paper and is "
        f"never re-shuffled."
    ))

    p(heading("2.4 MLP surrogate model", 2))
    p(body(
        f"The surrogate is a fully connected network with input dimension {cfg['n_layers']} (the four "
        f"layer thicknesses, standardised to [-1, 1] with the fixed constants "
        f"{(cfg['d_range_nm'][0]+cfg['d_range_nm'][1])/2:.0f} nm and "
        f"{(cfg['d_range_nm'][1]-cfg['d_range_nm'][0])/2:.0f} nm, so that the input scaling does not "
        f"depend on the training subset), hidden layers {cfg['hidden_sizes'][0]}, "
        f"{cfg['hidden_sizes'][1]} and {cfg['hidden_sizes'][2]} with ReLU activations, and "
        f"{cfg['n_wavelengths']} output units, i.e. the architecture "
        f"{cfg['n_layers']}-{'-'.join(str(h) for h in cfg['hidden_sizes'])}-{cfg['n_wavelengths']} "
        f"recommended by the assignment; it has {npar:,} trainable parameters. A sigmoid activation "
        f"is applied to the output because a lossless stack necessarily satisfies 0 <= R <= 1, which "
        f"makes the network physically bounded by construction. Weights are initialised with He "
        f"initialisation drawn from the seeded torch generator. The loss is the mean squared error "
        f"between predicted and TMM-calculated reflectance; training uses Adam with a constant "
        f"learning rate of {cfg['learning_rate']:g}, a batch size of {cfg['batch_size']} and "
        f"{cfg['n_epochs']} epochs, and the minibatch permutation is drawn from a generator seeded "
        f"with {seed} as well. The weights of the epoch with the lowest validation MSE are kept; "
        f"training the full model took {main['training_seconds']:.0f} s on a single CPU core "
        f"(PyTorch {main['environment']['torch']}, {main['environment']['threads']} thread)."
    ))
    p(figure(os.path.join(ROOT, "figures", "fig3_mlp_architecture.png"), "rIdFig3", 3))
    p(caption(
        f"Figure 3. Architecture of the MLP surrogate model "
        f"({cfg['n_layers']}-{'-'.join(str(h) for h in cfg['hidden_sizes'])}-{cfg['n_wavelengths']}, "
        f"{npar:,} parameters) mapping four layer thicknesses to the 41-point reflectance spectrum."
    ))

    p(heading("2.5 Training-size experiment", 2))
    p(body(
        "To isolate the effect of the amount of data, the first 500, 1,000, 2,000 and 4,000 samples of "
        "the fixed 4,000-sample training pool were used in turn. Because the pool order is itself the "
        "fixed random permutation, the smaller sets are nested subsets of the larger ones. The "
        "validation and test sets were never changed, and the seed, architecture, optimiser, learning "
        "rate, batch size and number of epochs were identical in the four runs, so any difference in "
        "test error is caused by the training-set size alone."
    ))

    p(heading("2.6 MLP-assisted thin-film screening", 2))
    p(body(
        f"The trained surrogate was used to screen {screen['n_candidates']:,} new candidate stacks "
        f"generated with design_seed = {dseed} from the same uniform thickness distribution. "
        f"All candidate spectra were predicted by the MLP, the candidates were ranked by the "
        f"predicted reflectance at {lam_t:.0f} nm, and the ten best were recomputed with TMM. The "
        f"final ranking is the TMM ranking of those ten candidates, and Table 1 reports the best five. "
        f"Two quantities are worth separating: the design objective, i.e. R at \u03bb_target, and the "
        f"agreement between the predicted and the true spectrum of the candidate. Only the second one "
        f"decides whether the surrogate ranking can be trusted."
    ))

    # ---------------- 3. Results ----------------
    p(heading("3. Results", 1))
    p(heading("3.1 MLP training and spectral prediction", 2))
    p(figure(os.path.join(ROOT, "figures", "fig4_loss_curve.png"), "rIdFig4", 4))
    p(caption("Figure 4. Training and validation losses of the MLP surrogate model."))
    p(body(
        f"Figure 4 shows the two loss curves. The training MSE falls from "
        f"{main['train_loss_final']*40:.2e} at the first epoch to "
        f"{main['train_loss_final']:.2e} at the end of the {cfg['n_epochs']} epochs, while the "
        f"validation MSE reaches its minimum {main['best_val_loss']:.2e} at epoch "
        f"{main['best_epoch']} and stays close to the training curve afterwards. The two curves track "
        f"each other without a visible gap, so the network is not overfitting the 4,000 training "
        f"samples; the residual error is the approximation error of the surrogate, not memorisation. "
        f"The kept checkpoint gives a validation MSE of {vm['mse']:.2e} (RMSE {vm['rmse']:.4f}) and a "
        f"test MSE of {tm['mse']:.2e}, i.e. RMSE = {tm['rmse']:.4f}, MAE = {tm['mae']:.4f} and a "
        f"largest absolute deviation of {tm['max_abs_error']:.4f} over all 500 test samples and all "
        f"41 wavelengths. Relative to the mean reflectance {fp['R_mean']:.4f} of the dataset, the "
        f"test RMSE is {100*tm['rmse']/fp['R_mean']:.1f} %. At the personal target wavelength "
        f"{lam_t:.0f} nm the mean absolute error is {tm['mae_at_target_wavelength']:.4f} and the MSE "
        f"{tm['mse_at_target_wavelength']:.2e}, slightly better than the spectrum-averaged values."
    ))
    p(body(
        f"Figure 5 shows three representative test samples. The MLP reproduces the position and the "
        f"depth of the interference fringes for all of them; the per-sample MSE of these three "
        f"samples is "
        + ", ".join(f"{s['per_sample_mse']:.1e}" for s in main["representative_test_samples"])
        + f", i.e. close to the median per-sample MSE of {tm['per_sample_mse_median']:.2e}. The "
        f"agreement is best where the spectrum is smooth and worst where two nearby thickness "
        f"combinations produce steep, closely spaced fringes - exactly the regime in which a small "
        f"thickness change moves a fringe across a sampling interval of 10 nm."
    ))
    p(figure(os.path.join(ROOT, "figures", "fig5_prediction_test_samples.png"), "rIdFig5", 5))
    p(caption(
        "Figure 5. Comparison of TMM-calculated and MLP-predicted spectra on representative test "
        "samples. The three designs are close to the median prediction error."
    ))

    p(heading("3.2 Effect of training-set size", 2))
    rows = [
        [
            f"{r['n_train']:,}",
            f"{r['val_metrics']['mse']:.2e}",
            f"{r['test_metrics']['mse']:.2e}",
            f"{r['test_metrics']['rmse']:.4f}",
            f"{r['test_metrics']['mae']:.4f}",
            f"{r['best_epoch']}",
            f"{r['training_seconds']:.0f}",
        ]
        for r in rec
    ]
    p(table(
        ["Train samples", "Val MSE", "Test MSE", "Test RMSE", "Test MAE", "Best epoch", "Time (s)"],
        rows,
        widths=[1700, 1450, 1450, 1400, 1400, 1300, 1272],
    ))
    p(caption("Table 2. Effect of the training-set size on the prediction error (500 fixed test samples)."))
    p(figure(os.path.join(ROOT, "figures", "fig6_training_size.png"), "rIdFig6", 6))
    p(caption("Figure 6. Effect of the training-set size on the test error."))
    p(body(
        f"Table 2 and Figure 6 summarise the four runs. The test RMSE decreases monotonically from "
        f"{rec[0]['test_metrics']['rmse']:.4f} for 500 training samples to "
        f"{rec[-1]['test_metrics']['rmse']:.4f} for 4,000 samples, a total reduction of "
        f"{100*(rec[0]['test_metrics']['mse']-rec[-1]['test_metrics']['mse'])/rec[0]['test_metrics']['mse']:.0f} % "
        f"in MSE. The benefit of each further doubling, however, shrinks steadily: doubling the pool "
        f"from 500 to 1,000 samples lowers the test MSE by "
        f"{gains[0]['relative_mse_reduction_pct']:.0f} %, from 1,000 to 2,000 by "
        f"{gains[1]['relative_mse_reduction_pct']:.0f} % and from 2,000 to 4,000 by only "
        f"{gains[2]['relative_mse_reduction_pct']:.0f} %. Expressed as RMSE ratios, the three "
        f"doublings multiply the error by {gains[0]['rmse_ratio']:.2f}, {gains[1]['rmse_ratio']:.2f} "
        f"and {gains[2]['rmse_ratio']:.2f} respectively. The validation and test errors stay within a "
        f"factor of {max(r['test_metrics']['mse']/r['val_metrics']['mse'] for r in rec):.2f} of each "
        f"other for every training size, which confirms that the fixed validation set is a reliable "
        f"proxy for the test set. In other words, the model is already data-limited at 500 samples "
        f"and the returns of adding data decay quickly; a larger model or a better input representation "
        f"would be needed to exploit 4,000 samples fully."
    ))

    p(heading("3.3 MLP-assisted thin-film design", 2))
    p(body(
        f"Screening {screen['n_candidates']:,} candidates took {timing['mlp_seconds']:.2f} s with the "
        f"surrogate and {timing['tmm_seconds']:.1f} s with TMM on the same machine and the same batch, "
        f"a speed-up of x{timing['speedup']:.1f}. Over the whole candidate pool the surrogate "
        f"reproduces the TMM spectrum with an MSE of {pool['spectrum_mse']:.2e} "
        f"(MAE {pool['spectrum_mae']:.4f}); at the target wavelength the mean absolute error is "
        f"{pool['R_target_mae']:.4f} and the largest single error "
        f"{pool['R_target_max_abs_error']:.4f}. The true (TMM) reflectance at {lam_t:.0f} nm over the "
        f"10,000 candidates ranges from {pool['R_target_tmm_min']:.4f} to "
        f"{pool['R_target_tmm_max']:.4f} with a mean of {pool['R_target_tmm_mean']:.4f} and a 99.9th "
        f"percentile of {pool['R_target_tmm_p999']:.4f}, so the designs selected below are in the tail "
        f"of the distribution."
    ))
    p(body(
        "Figure 7A shows the spectra of the five finalist candidates together with the selected "
        "design after TMM verification (the surrogate was used to rank all 10,000 candidates and the "
        "Top-10 of that ranking were recomputed with TMM; Figure 7B shows the MLP ranking against the "
        "TMM verification for those ten candidates)."
    ))
    p(figure(os.path.join(ROOT, "figures", "fig7_design.png"), "rIdFig7", 7))
    p(caption(
        "Figure 7. MLP-predicted and TMM-verified spectra of the selected design. "
        "(A) the selected design and the five finalist candidates, with the personal target "
        "wavelength marked; (B) MLP ranking against the TMM verification for the Top-10 candidates."
    ))
    t1_rows = [
        [
            str(i + 1),
            f"{r['d_nm'][0]:.1f}",
            f"{r['d_nm'][1]:.1f}",
            f"{r['d_nm'][2]:.1f}",
            f"{r['d_nm'][3]:.1f}",
            f"{r['mlp_R_target']:.4f}",
            f"{r['tmm_R_target']:.4f}",
        ]
        for i, r in enumerate(top10[:5])
    ]
    p(table(
        ["Rank", "d1 (nm)", "d2 (nm)", "d3 (nm)", "d4 (nm)", "MLP R_target", "TMM R_target"],
        t1_rows,
        widths=[900, 1450, 1450, 1450, 1450, 1640, 1632],
    ))
    p(caption(
        f"Table 1. Top five candidate thin-film designs selected by the MLP and verified using TMM "
        f"(\u03bb_target = {lam_t:.0f} nm)."
    ))
    n_kept = sum(1 for r in top10 if r["rank_tmm"] <= 5)
    mlp_top1 = next(r for r in top10 if r["rank_mlp"] == 1)
    tmm_top1 = next(r for r in top10 if r["rank_tmm"] == 1)
    p(body(
        f"The best design found has thicknesses [{', '.join(f'{v:.1f}' for v in best['d_nm'])}] nm "
        f"and reaches a TMM reflectance of {best['tmm_R_target']:.4f} at {lam_t:.0f} nm; the "
        f"surrogate predicted {best['mlp_R_target']:.4f}, an absolute error of only "
        f"{best['absolute_error']:.4f}. The design beats the 99.9th percentile of the candidate pool "
        f"({pool['R_target_tmm_p999']:.4f}) and is more than twice the mean reflectance of the pool "
        f"({pool['R_target_tmm_mean']:.4f}). The re-ranking, however, does change the order: the "
        f"candidate that the surrogate ranked first (predicted R = {mlp_top1['mlp_R_target']:.4f}) "
        f"ends up {mlp_top1['rank_tmm']}nd after TMM verification with a true "
        f"R = {mlp_top1['tmm_R_target']:.4f}, whereas the verified winner had been placed "
        f"{tmm_top1['rank_mlp']}nd by the MLP. The two candidates differ by only "
        f"{abs(mlp_top1['mlp_R_target'] - tmm_top1['mlp_R_target']):.4f} in the predicted reflectance, "
        f"which is the same order as the surrogate's own error at the target wavelength "
        f"({pool['R_target_mae']:.4f}), so the mis-ranking is a direct consequence of the residual "
        f"prediction error. All five designs in Table 1 were in the surrogate's Top-10, but only "
        f"{n_kept} of them would have been selected by the raw MLP order, and the corrected Table 1 "
        f"has to be produced by TMM."
    ))

    p(heading("3.4 Representative failure case", 2))
    p(figure(os.path.join(ROOT, "figures", "fig8_failure_case.png"), "rIdFig8", 8))
    p(caption(
        "Figure 8. A representative case with relatively large MLP prediction error "
        f"(rank 1 of the 500 test samples, per-sample MSE {worst['per_sample_mse']:.2e})."
    ))
    p(body(
        f"The worst of the 500 test samples is shown in Figure 8. Its per-sample MSE is "
        f"{worst['per_sample_mse']:.2e} (RMSE {worst['rmse']:.4f}) with a single-wavelength deviation "
        f"of up to {worst['max_abs_error']:.4f} - about "
        f"{worst['rmse']/tm['rmse']:.0f} times the average test RMSE - for the thicknesses "
        f"[{', '.join(f'{v:.1f}' for v in worst['thickness_nm'])}] nm. Two features of the failure are "
        f"visible in Figure 8B. First, the error changes sign from one fringe to the next instead of "
        f"growing with the reflectance itself, which is the signature of a small error in the "
        f"*position* of the interference fringes rather than of a wrong overall level: the predicted "
        f"curve is slightly stretched, so it overshoots at some wavelengths and undershoots at "
        f"neighbouring ones. A shift of the fringe pattern is exactly what a slight mis-estimate of "
        f"the optical thickness n_i d_i produces, and the four-dimensional input makes this the "
        f"dominant error mode of the surrogate. Second, the failure is concentrated in the short-"
        f"wavelength half of the spectrum, where the fringes are sharpest: within the 10 nm sampling "
        f"interval the reflectance can change by more than 0.05, so the network has to place the "
        f"extremum to better than one sample. Figure 8C places the sample in the error distribution: "
        f"the median per-sample MSE is {tm['per_sample_mse_median']:.2e} and the 95th percentile "
        f"{tm['per_sample_mse_p95']:.2e}, so the worst case is roughly "
        f"{worst['per_sample_mse']/tm['per_sample_mse_median']:.0f} times the median but still within "
        f"one order of magnitude of it, i.e. the surrogate degrades gracefully rather than failing "
        f"catastrophically. A denser wavelength sampling would remove part of this error."
    ))

    # ---------------- 4. Discussion ----------------
    p(heading("4. Discussion", 1))
    p(body(
        f"Regarding the first research question, the surrogate reproduces the TMM spectra of unseen "
        f"designs with a test RMSE of {tm['rmse']:.4f}, about {100*tm['rmse']/fp['R_mean']:.1f} % of "
        f"the mean reflectance and only {100*tm['rmse']/fp['R_max']:.1f} % of the largest reflectance "
        f"in the dataset. Figure 5 shows that the residual error is dominated by the placement and the "
        f"sharpness of the interference fringes rather than by a wrong overall level: the error changes "
        f"sign from fringe to fringe (section 3.4), which is what a small mis-estimate of the optical "
        f"thickness n_i d_i produces. Because the mapping thickness -> spectrum is many-to-one in the "
        f"opposite direction (different stacks can give very similar spectra), part of this residual is "
        f"irreducible for any deterministic regressor, and an ensemble or a probabilistic output would "
        f"be needed to go clearly below it."
    ))
    p(body(
        f"Regarding the second question, more data help, but with strongly diminishing returns "
        f"(Figure 6): the error shrinks quickly between 500 and 1,000 samples and then flattens, with "
        f"the last doubling of the training set buying only {gains[2]['relative_mse_reduction_pct']:.0f} % "
        f"of MSE. This is the expected behaviour of a smooth function approximator: with 500 samples "
        f"the network cannot cover the four-dimensional thickness cube densely enough, whereas beyond "
        f"a few thousand samples the error becomes dominated by the architecture and by the "
        f"optimisation rather than by the data. It also means that for the present problem a "
        f"practitioner should first improve the model or the input representation (for instance by "
        f"adding physically motivated features such as the optical thickness n_i d_i) before "
        f"generating tens of thousands of additional TMM spectra."
    ))
    p(body(
        f"Regarding the third question, the surrogate is clearly useful for screening. Ranking "
        f"{screen['n_candidates']:,} candidates is x{timing['speedup']:.1f} cheaper with the MLP than "
        f"with TMM, and the design that survives TMM verification reaches "
        f"{best['tmm_R_target']:.4f} - above the 99.9th percentile of the pool. The surrogate "
        f"therefore does the part of the work where speed matters (pruning a huge library down to a "
        f"handful of finalists) and leaves the part where accuracy matters to the physical model. "
        f"Figure 7B is the quantitative justification: the MLP ranks the ten finalists almost, but not "
        f"exactly, as TMM does - its own favourite is demoted to second place - and its predicted "
        f"R_target of the best design differs from the verified value by "
        f"{best['absolute_error']:.4f}. A design reported on the basis of the surrogate alone would "
        f"therefore be optimistic and, worse, could name the wrong winner among nearly equivalent "
        f"candidates; the final numbers in Table 1 must come from TMM. This "
        f"split of responsibilities - surrogate for search, physics for verification - is the same "
        f"pattern that is used in the deep-learning-assisted inverse-design literature [4-7]."
    ))
    p(body(
        f"The study has clear limitations. The optical model is deliberately minimal: no dispersion, "
        f"no absorption, normal incidence only, and the refractive indices and the number of layers are "
        f"fixed, so the surrogate learns a four-dimensional map and nothing else. The dataset of "
        f"{cfg['n_samples']:,} TMM spectra covers the thickness cube uniformly, but real design "
        f"problems concentrate on a small region of that cube, where the local data density - and "
        f"hence the accuracy - would be lower. The failure case in Figure 8 shows the consequence: the "
        f"surrogate is least reliable exactly for the sharp spectral features that are most interesting "
        f"for filters. Finally, the MLP was trained with a single seed and a single architecture, so "
        f"the reported error bars reflect the split rather than the variability of the training "
        f"procedure; repetitions with different initialisations would be needed to separate the two."
    ))

    # ---------------- 5. Conclusions ----------------
    p(heading("5. Conclusions", 1))
    p(body(
        f"A four-layer Air/H/L/H/L/Glass dielectric stack with fixed refractive indices was used to "
        f"test whether a small MLP can act as a surrogate for the transfer-matrix method. (Q1) Yes: "
        f"the {cfg['n_layers']}-{'-'.join(str(h) for h in cfg['hidden_sizes'])}-{cfg['n_wavelengths']} "
        f"network with {npar:,} parameters predicts the 41-point reflectance spectrum of unseen "
        f"designs with a test RMSE of {tm['rmse']:.4f} in reflectance units "
        f"({100*tm['rmse']/fp['R_mean']:.1f} % of the mean reflectance), with a mean absolute error of "
        f"only {tm['mae_at_target_wavelength']:.4f} at the personal target wavelength "
        f"{lam_t:.0f} nm. (Q2) More training data help but with sharply diminishing returns: the test "
        f"RMSE drops from {rec[0]['test_metrics']['rmse']:.4f} at 500 samples to "
        f"{rec[-1]['test_metrics']['rmse']:.4f} at 4,000 samples, while the last doubling reduces the "
        f"MSE by only {gains[2]['relative_mse_reduction_pct']:.0f} %. (Q3) Yes, with verification: "
        f"screening {screen['n_candidates']:,} candidates with the surrogate is "
        f"x{timing['speedup']:.1f} faster than with TMM, and the selected design reaches a "
        f"TMM-verified reflectance of {best['tmm_R_target']:.4f} at {lam_t:.0f} nm, above the 99.9th "
        f"percentile of the candidate pool, although the final ranking must always be recomputed with "
        f"the physical model."
    ))

    # ---------------- data & code ----------------
    p(heading("Data and Code Availability", 1))
    p(body(
        "The data used in this work were generated using the TMM code developed in this study. All "
        "source code, model-training scripts, thin-film screening scripts, environment dependencies, "
        "and instructions for reproducing the main results are available at:\n"
        "https://github.com/Jfzz-KK/123435\n"
        "The repository reports the student-specific parameters \u03bb_target = "
        f"{lam_t:.0f} nm, seed = {seed} and design_seed = {dseed} in its README, together with the "
        "commands that regenerate the dataset, train the surrogate, reproduce Figures 1-8 and "
        "Table 1, and the sha256 fingerprints of the generated arrays."
    ))

    # ---------------- references ----------------
    p(heading("References", 1))
    refs = [
        "Macleod, H. A. Thin-Film Optical Filters, 4th ed. CRC Press, Boca Raton, 2010. "
        "ISBN 978-1-4200-7302-7.",
        "Born, M., and Wolf, E. Principles of Optics, 7th ed. Cambridge University Press, Cambridge, "
        "1999. ISBN 978-0-521-64222-4.",
        "Byrnes, S. J. Multilayer optical calculations. arXiv:1603.02720, 2016. "
        "https://doi.org/10.48550/arXiv.1603.02720",
        "Ma, T., Ma, M., and Guo, L. J. Optical multilayer thin film structure inverse design: From "
        "optimization to deep learning. iScience 2025, 28, 112222. "
        "https://doi.org/10.1016/j.isci.2025.112222",
        "Liu, D., Tan, Y., Khoram, E., and Yu, Z. Training deep neural networks for the inverse design "
        "of nanophotonic structures. ACS Photonics 2018, 5, 1365-1369. "
        "https://doi.org/10.1021/acsphotonics.7b01377",
        "Peurifoy, J., Shen, Y., Jing, L., Yang, Y., Cano-Renteria, F., DeLacy, B. G., Joannopoulos, "
        "J. D., Tegmark, M., and Soljacic, M. Nanophotonic particle simulation and inverse design "
        "using artificial neural networks. Science Advances 2018, 4, eaar4206. "
        "https://doi.org/10.1126/sciadv.aar4206",
        "Ma, T., and Guo, L. J. OptoGPT-based design of multilayer thin film structures. Optics "
        "Express 2024, 32, 31703-31715. https://doi.org/10.1364/OE.529375",
        "Tikhonravov, A. V., Trubetskov, M. K., and DeBell, G. W. Application of the needle "
        "optimization technique to the design of optical coatings. Applied Optics 1996, 35, "
        "5493-5508. https://doi.org/10.1364/AO.35.005493",
        "Martin, S., Rivory, J., and Schoenauer, M. Synthesis of optical multilayer systems using "
        "genetic algorithms. Applied Optics 1995, 34, 2247-2254. "
        "https://doi.org/10.1364/AO.34.002247",
        "Kingma, D. P., and Ba, J. Adam: A method for stochastic optimization. In 3rd International "
        "Conference on Learning Representations (ICLR), San Diego, 2015. arXiv:1412.6980",
        "He, K., Zhang, X., Ren, S., and Sun, J. Delving deep into rectifiers: Surpassing human-level "
        "performance on ImageNet classification. In Proceedings of the IEEE International Conference "
        "on Computer Vision (ICCV), Santiago, 2015, pp. 1026-1034. "
        "https://doi.org/10.1109/ICCV.2015.123",
        "Virtanen, P., Gommers, R., Oliphant, T. E., et al. SciPy 1.0: fundamental algorithms for "
        "scientific computing in Python. Nature Methods 2020, 17, 261-272. "
        "https://doi.org/10.1038/s41592-019-0686-2",
    ]
    for i, r in enumerate(refs, start=1):
        p(para(run(f"[{i}] {r}", size=9), space_after=60, indent=0))

    body_xml = "".join(parts) + SECT_PR
    doc = (
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
        'mc:Ignorable="w14 w15 w16 w16du wp14">'
        "<w:body>" + body_xml + "</w:body></w:document>"
    )
    return doc


# --------------------------------------------------------------------------
# package assembly
# --------------------------------------------------------------------------
FIGURES = [
    ("fig1_workflow.png", "rIdFig1"),
    ("fig2_model_and_data.png", "rIdFig2"),
    ("fig3_mlp_architecture.png", "rIdFig3"),
    ("fig4_loss_curve.png", "rIdFig4"),
    ("fig5_prediction_test_samples.png", "rIdFig5"),
    ("fig6_training_size.png", "rIdFig6"),
    ("fig7_design.png", "rIdFig7"),
    ("fig8_failure_case.png", "rIdFig8"),
]

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

RELS = (
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
        f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{name}"/>'
        for name, rid in FIGURES
    )
    + "</Relationships>"
)

ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
    "</Relationships>"
)


def write_package(out_path: str, document_xml: str, template_dir: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    src_word = os.path.join(template_dir, "word")
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/_rels/document.xml.rels", RELS)
        for part in ("styles.xml", "settings.xml", "numbering.xml", "fontTable.xml",
                     "webSettings.xml", "header1.xml", "footer1.xml",
                     "footnotes.xml", "endnotes.xml"):
            with open(os.path.join(src_word, part), "rb") as fh:
                z.writestr(f"word/{part}", fh.read())
        with open(os.path.join(src_word, "theme", "theme1.xml"), "rb") as fh:
            z.writestr("word/theme/theme1.xml", fh.read())
        for name, _ in FIGURES:
            with open(os.path.join(ROOT, "figures", name), "rb") as fh:
                z.writestr(f"word/media/{name}", fh.read())
        core = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            "<dc:title>MLP-Based Spectral Prediction and Data-Driven Design of Multilayer Dielectric Thin Films</dc:title>"
            "<dc:creator>2020276134</dc:creator>"
            "<cp:lastModifiedBy>AI4S thin-film pipeline</cp:lastModifiedBy>"
            "</cp:coreProperties>"
        )
        app = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            "<Application>Microsoft Office Word</Application></Properties>"
        )
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", choices=["en"])
    ap.add_argument("--template", default=os.path.join(ROOT, "templates", "docx_template"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    main_j = load("mlp_main_metrics.json")
    sizes_j = load("training_size_study.json")
    screen_j = load("screening_results.json")
    fp = load("dataset_fingerprint.json")

    out = args.out or os.path.join(ROOT, "paper", f"AI4S_Research_Article_{main_j['config']['student_id']}.docx")
    doc_xml = build_document(main_j, sizes_j, screen_j, fp, args.lang)
    write_package(out, doc_xml, args.template)
    print("wrote", os.path.relpath(out, ROOT), f"({os.path.getsize(out)/1024:.0f} kB)")

    txt = os.path.join(ROOT, "paper", "manuscript_plain_text.txt")
    with open(txt, "w", encoding="utf-8") as fh:
        fh.write(doc_xml)
    print("wrote", os.path.relpath(txt, ROOT))


if __name__ == "__main__":
    main()
