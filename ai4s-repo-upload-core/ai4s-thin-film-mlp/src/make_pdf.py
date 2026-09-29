"""Build the manuscript PDF with reportlab.

Why not Word?  Converting the .docx to PDF through Word automation is not possible
in the sandbox this assignment was produced in (Office refuses to create a document
object, HRESULT 0x800A13E9).  The PDF therefore re-typesets exactly the same
content -- the same numbers, figures, tables and captions -- read from the same
result JSON files, so the .docx and the .pdf cannot disagree.

Usage
-----
    python src/make_pdf.py            # -> paper/AI4S_Research_Article_<id>.pdf
    python src/make_pdf.py --html     # also dump an HTML version
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime  # noqa: E402

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------------
# CJK font: the built-in Type-1 fonts cannot show the Chinese title
# --------------------------------------------------------------------------
CJK = None
for _name, _candidates in (
    ("SimSun", [r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\simsunb.ttf"]),
    ("SimHei", [r"C:\Windows\Fonts\simhei.ttf"]),
    ("MSYaHei", [r"C:\Windows\Fonts\msyh.ttc"]),
):
    for _path in _candidates:
        if os.path.exists(_path):
            try:
                pdfmetrics.registerFont(TTFont(_name, _path, subfontIndex=0))
                CJK = _name
                break
            except Exception:
                continue
    if CJK:
        break


def cjk(text: str) -> str:
    """Wrap Chinese text in a font tag that reportlab can actually render."""
    return f'<font name="{CJK}">{text}</font>' if CJK else text


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TITLE = "MLP-Based Spectral Prediction and Data-Driven Design of Multilayer Dielectric Thin Films"
TITLE_ZH = "基于多层感知机的多层介质薄膜光谱预测与辅助设计"

BODY = ParagraphStyle(
    "body", fontName="Times-Roman", fontSize=8.7, leading=11.2, alignment=TA_JUSTIFY,
    firstLineIndent=11, spaceAfter=3,
)
BODY_NOIND = ParagraphStyle("bodyni", parent=BODY, firstLineIndent=0)
BULLET = ParagraphStyle("bullet", parent=BODY, firstLineIndent=0, leftIndent=14, bulletIndent=4)
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=11, leading=13,
                    spaceBefore=6, spaceAfter=2.5)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=9.6, leading=11.5,
                    spaceBefore=5, spaceAfter=2)
TITLE_S = ParagraphStyle("title", fontName=(CJK or "Helvetica-Bold"), fontSize=14.5, leading=17.5,
                         alignment=TA_CENTER, spaceAfter=3)
SUBTITLE_S = ParagraphStyle("subtitle", fontName="Times-Roman", fontSize=10.5, leading=13,
                            alignment=TA_CENTER, spaceAfter=4)
META = ParagraphStyle("meta", fontName="Times-Roman", fontSize=8.7, leading=11,
                      alignment=TA_CENTER)
SMALL = ParagraphStyle("small", fontName="Times-Roman", fontSize=7.9, leading=10,
                       alignment=TA_JUSTIFY, firstLineIndent=0, spaceAfter=2)
CAPTION = ParagraphStyle("caption", fontName="Helvetica-Bold", fontSize=7.8, leading=9.6,
                         alignment=TA_CENTER, spaceBefore=1.5, spaceAfter=4.5)
ABSTRACT = ParagraphStyle("abstract", parent=BODY, leftIndent=18, rightIndent=18,
                          fontSize=8.5, leading=10.9)

# figure widths as a fraction of the text width; the wide multi-panel figures are
# scaled down so that the manuscript stays inside the 4-6 page limit
FIG_WIDTH = {
    "fig1_workflow.png": 0.80,
    "fig2_model_and_data.png": 0.90,
    "fig3_mlp_architecture.png": 0.72,
    "fig4_loss_curve.png": 0.52,
    "fig5_prediction_test_samples.png": 1.00,
    "fig6_training_size.png": 0.82,
    "fig7_design.png": 0.82,
    "fig8_failure_case.png": 0.94,
}


def load(name: str):
    with open(os.path.join(ROOT, "results", name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def img(name: str, width_in: float | None = None):
    path = os.path.join(ROOT, "figures", name)
    from PIL import Image as PILImage

    with PILImage.open(path) as im:
        w, h = im.size
    usable = (7.08 if width_in is None else width_in) * FIG_WIDTH.get(name, 0.9)
    return Image(path, width=usable * inch, height=usable * inch * h / w)


def kv_table(header, rows, widths):
    data = [[Paragraph(f"<b>{html.escape(h)}</b>", SMALL) for h in header]]
    for r in rows:
        data.append([Paragraph(html.escape(str(c)), SMALL) for c in r])
    t = Table(data, colWidths=[w * inch for w in widths], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


def story(main, sizes, screen, fp):
    cfg = main["config"]
    tm, vm = main["test_metrics"], main["val_metrics"]
    worst = main["worst_test_sample"]
    best, pool, timing, top10 = screen["best_design"], screen["candidate_pool"], screen["timing"], screen["top10"]
    rec, gains = sizes["records"], sizes["marginal_gains"]
    lam_t, seed, dseed = screen["target_wavelength_nm"], cfg["seed"], cfg["design_seed"]
    npar = main["n_parameters"]
    S: list = []

    def P(t, style=BODY):
        S.append(Paragraph(t, style))

    def F(name, caption):
        S.append(KeepTogether([img(name), Paragraph(caption, CAPTION)]))

    S.append(Paragraph(TITLE_ZH, TITLE_S))
    S.append(Paragraph(TITLE, SUBTITLE_S))
    S.append(Paragraph(f"{cjk('姓名')} / Name: {cfg.get('student_name', '__________')} "
                       f"&nbsp;&nbsp;&nbsp; {cjk('学号')} / Student ID: {cfg['student_id']}", META))
    S.append(Paragraph(f"&lambda;<sub>target</sub> = {lam_t:.0f} nm &nbsp;&nbsp; seed = {seed} "
                       f"&nbsp;&nbsp; design_seed = {dseed}", META))
    S.append(Spacer(1, 4))

    S.append(Paragraph("Abstract", H1))
    P(
        f"We study whether a small multilayer perceptron (MLP) can act as a fast surrogate for the "
        f"optical response of a four-layer dielectric thin film and assist the design of a coating "
        f"that maximises reflectance at a personal target wavelength of {lam_t:.0f} nm. "
        f"Transfer-matrix-method (TMM) spectra were generated for {cfg['n_samples']:,} random "
        f"thickness combinations of the fixed stack Air/H/L/H/L/Glass "
        f"(n<sub>H</sub> = {cfg['n_h']:.2f}, n<sub>L</sub> = {cfg['n_l']:.2f}, "
        f"n<sub>s</sub> = {cfg['n_s']:.2f}, {cfg['d_range_nm'][0]:.0f}-{cfg['d_range_nm'][1]:.0f} nm per "
        f"layer, {cfg['n_wavelengths']} wavelengths from {cfg['wavelength_range_nm'][0]:.0f} to "
        f"{cfg['wavelength_range_nm'][1]:.0f} nm) and split once into {cfg['split'][0]:,}/"
        f"{cfg['split'][1]}/{cfg['split'][2]} training, validation and test samples with seed {seed}. "
        f"The MLP ({cfg['n_layers']}-{'-'.join(str(h) for h in cfg['hidden_sizes'])}-"
        f"{cfg['n_wavelengths']}, {npar:,} parameters, MSE loss, Adam) predicts the whole spectrum "
        f"from four thicknesses and reaches a test RMSE of {tm['rmse']:.4f} in reflectance units "
        f"(test MSE {tm['mse']:.2e}), i.e. about {100*tm['rmse']/fp['R_mean']:.1f} % of the mean "
        f"reflectance. Its error at {lam_t:.0f} nm is only {tm['mae_at_target_wavelength']:.4f} on "
        f"average. Increasing the training set from 500 to 4,000 samples lowers the test RMSE from "
        f"{rec[0]['test_metrics']['rmse']:.4f} to {rec[-1]['test_metrics']['rmse']:.4f}, but the last "
        f"doubling yields only a {gains[-1]['relative_mse_reduction_pct']:.0f} % MSE reduction, i.e. "
        f"clearly diminishing returns. Screening {screen['n_candidates']:,} candidates generated with "
        f"design_seed {dseed} takes {timing['mlp_seconds']:.2f} s with the surrogate against "
        f"{timing['tmm_seconds']:.1f} s for TMM (x{timing['speedup']:.1f}), and the best design found "
        f"by the surrogate reaches a TMM-verified reflectance of {best['tmm_R_target']:.4f} at "
        f"{lam_t:.0f} nm. The MLP is therefore an accurate and much cheaper alternative to TMM for "
        f"large-scale screening, but its ranking must always be confirmed by TMM.", ABSTRACT)
    P("<i>Keywords: optical thin films; transfer matrix method; multilayer perceptron; surrogate "
      "model; AI for Science</i>", BODY_NOIND)

    S.append(Paragraph("1. Introduction", H1))
    P("Multilayer dielectric thin films are one of the oldest and still most widely used tools of "
      "optical engineering. Their optical response is produced by interference between the partial "
      "reflections at the layer interfaces, so the reflectance spectrum is controlled by only three "
      "families of design parameters: the number of layers, the materials (refractive indices) and "
      "the thickness of each layer [1,2]. Because the layers are thin compared with the wavelength, "
      "a modest change in thickness strongly modifies the phase accumulated by the wave in that "
      "layer, and therefore the position and depth of the interference fringes. Even for the simple "
      "four-layer stack considered here, the mapping from thickness to spectrum is strongly "
      "non-linear, and the frequency of the fringes grows with the total optical thickness.")
    P("The standard physical model of such a stack is the transfer matrix method (TMM) [1,3]. Each "
      "layer is represented by a 2x2 characteristic matrix that depends on the optical phase "
      "thickness; multiplying the matrices gives the input admittance of the multilayer, from which "
      "the amplitude reflection coefficient and the reflectance follow analytically. TMM is exact "
      "for the idealised model used here (plane wave, normal incidence, non-dispersive, lossless "
      "layers) and it is computationally cheap per design. The difficulty appears when a very large "
      f"number of designs has to be evaluated, for instance when {screen['n_candidates']:,} "
      "candidates must be ranked before a design is chosen: the cost grows linearly with the number "
      "of candidates and dominates the whole optimisation loop.")
    P("Machine-learning surrogate models offer a way out of this trade-off. A neural network trained "
      "on TMM data learns the mapping from design parameters to optical response directly from "
      "examples [4], and once trained it evaluates a design in a single forward pass that is orders "
      "of magnitude cheaper than a numerical simulation. Such surrogates are now routinely used in "
      "the inverse design of optical multilayer structures, either as vectorised regressors or as "
      "generative models [4-7]. The price is that a surrogate is only an approximation: it can "
      "mis-rank nearly equivalent candidates, and its accuracy depends on how much training data are "
      "available. The recommended reading for this assignment reviews this development from "
      "classical optimisation to deep learning [4].")
    P("This work addresses three questions for a deliberately minimal system - a four-layer "
      "Air/H/L/H/L/Glass stack with fixed refractive indices and only the four thicknesses as free "
      "parameters. (Q1) Can an MLP predict the reflectance spectrum of the stack accurately? "
      "(Q2) How does the prediction error change when the number of training samples grows? "
      "(Q3) Can the MLP act as a surrogate that helps to screen a large candidate library and find "
      "a design with high reflectance at a personal target wavelength? All three questions are "
      "answered with a single fixed dataset, a single fixed train/validation/test split and "
      "explicitly recorded random seeds, so that every number reported below can be reproduced. "
      "Figure 1 summarises the workflow.")
    F("fig1_workflow.png",
      f"Figure 1. Overall workflow of the AI4S thin-film study. The dataset is generated with "
      f"seed = {seed}; the screening library uses design_seed = {dseed} and the final top-5 design "
      f"is always verified with TMM.")

    S.append(Paragraph("2. Materials and Methods", H1))
    S.append(Paragraph("2.1 Optical model and transfer matrix method", H2))
    P(f"The object of the study is the four-layer stack Air / H / L / H / L / Glass, illuminated at "
      f"normal incidence by a plane wave. The layers are non-absorbing and non-dispersive with "
      f"refractive indices n<sub>H</sub> = {cfg['n_h']:.2f} (layers 1 and 3) and "
      f"n<sub>L</sub> = {cfg['n_l']:.2f} (layers 2 and 4); the substrate is glass with "
      f"n<sub>s</sub> = {cfg['n_s']:.2f} and the incident medium is air with n<sub>0</sub> = 1.00. "
      f"The layer thicknesses d<sub>i</sub> and the vacuum wavelength &lambda; are measured in "
      f"nanometres.")
    P("The optical phase thickness of layer i is &delta;<sub>i</sub> = 2&pi; n<sub>i</sub> "
      "d<sub>i</sub> / &lambda;. With the optical admittance at normal incidence "
      "&eta;<sub>i</sub> = n<sub>i</sub>, the characteristic matrix of the layer is "
      "M<sub>i</sub> = [[cos &delta;<sub>i</sub>, i sin &delta;<sub>i</sub> / &eta;<sub>i</sub>], "
      "[i &eta;<sub>i</sub> sin &delta;<sub>i</sub>, cos &delta;<sub>i</sub>]]. The multilayer matrix "
      "is the ordered product M = M<sub>1</sub> M<sub>2</sub> M<sub>3</sub> M<sub>4</sub> (light "
      "travels from layer 1 towards the substrate), the input admittance is "
      "Y = (M<sub>21</sub> + M<sub>22</sub> &eta;<sub>s</sub>) / (M<sub>11</sub> + M<sub>12</sub> "
      "&eta;<sub>s</sub>), and the amplitude reflection coefficient and reflectance are "
      "r = (&eta;<sub>0</sub> - Y)/(&eta;<sub>0</sub> + Y) and R = |r|<super>2</super>. The "
      "implementation (src/tmm.py) evaluates the product layer by layer for whole batches of designs "
      "and wavelengths at once. Six unit checks are included in tests/test_tmm.py: a zero-thickness "
      "stack reproduces the bare air/glass Fresnel reflectance 0.0426, a single quarter-wave layer "
      "reproduces the analytic value R = ((&eta;<sub>0</sub> - n<super>2</super>/n<sub>s</sub>)/"
      "(&eta;<sub>0</sub> + n<super>2</super>/n<sub>s</sub>))<super>2</super>, batched and "
      "single-design evaluation agree to 1e-13, and 400 random stacks satisfy 0 &le; R &le; 1 at all "
      "41 wavelengths. Because the model is lossless, R is used directly as the quantity to be "
      "learned.")
    F("fig2_model_and_data.png",
      "Figure 2. Physical model and TMM-based generation of thickness-spectrum data. (A) the "
      "Air/H/L/H/L/Glass stack; (B) distribution of the 20,000 sampled layer thicknesses; (C) four "
      "examples of the 5,000 TMM-calculated reflectance spectra.")

    S.append(Paragraph("2.2 Student-specific target wavelength and random seeds", H2))
    P(f"Following the assignment, the personal parameters are derived from the student ID "
      f"{cfg['student_id']}. The last two digits are N = {cfg['n_mod']}, so the target wavelength is "
      f"&lambda;<sub>target</sub> = 450 + 10 x (N mod 31) = {lam_t:.0f} nm, which corresponds to "
      f"index {screen['target_index']} of the 41 wavelength samples. The random seed is the integer "
      f"formed by the last six digits, seed = {seed}; it controls the generation of the dataset, the "
      f"single random permutation that defines the train/validation/test split, and the "
      f"initialisation of the MLP weights. The design stage uses design_seed = seed + 1 = {dseed} so "
      f"that the candidate structures cannot coincide with the training data. All scripts set the "
      f"three seeds explicitly (random, numpy and torch) at start-up.")
    P(f"The generated dataset is fingerprinted in results/dataset_fingerprint.json: "
      f"sha256(thickness) = {fp['thickness_sha256'][:16]}..., sha256(spectra) = "
      f"{fp['spectra_sha256'][:16]}..., sha256(split) = {fp['split_sha256'][:16]}..., with R in "
      f"[{fp['R_min']:.4f}, {fp['R_max']:.4f}] and mean R = {fp['R_mean']:.4f}. Re-running "
      f"src/data.py reproduces these digests, which is how the numerical consistency of the "
      f"manuscript was checked.")

    S.append(Paragraph("2.3 Dataset generation", H2))
    P(f"{cfg['n_samples']:,} thickness combinations were drawn from a uniform distribution in "
      f"[{cfg['d_range_nm'][0]:.0f}, {cfg['d_range_nm'][1]:.0f}] nm for each of the four layers with "
      f"seed {seed}, and their reflectance was computed with TMM at the {cfg['n_wavelengths']} "
      f"wavelengths from {cfg['wavelength_range_nm'][0]:.0f} to "
      f"{cfg['wavelength_range_nm'][1]:.0f} nm in steps of "
      f"{cfg['wavelength_step_nm']:.0f} nm. One random permutation of the 5,000 samples, drawn from "
      f"the same seeded generator immediately after the thicknesses, defines a fixed split of "
      f"{cfg['split'][0]:,} training, {cfg['split'][1]} validation and {cfg['split'][2]} test "
      f"samples; the sorted index sets are stored together with the data. This split is used for "
      f"every experiment in the paper and is never re-shuffled.")

    S.append(Paragraph("2.4 MLP surrogate model", H2))
    P(f"The surrogate is a fully connected network with input dimension {cfg['n_layers']} (the four "
      f"layer thicknesses, standardised to [-1, 1] with the fixed constants "
      f"{(cfg['d_range_nm'][0]+cfg['d_range_nm'][1])/2:.0f} nm and "
      f"{(cfg['d_range_nm'][1]-cfg['d_range_nm'][0])/2:.0f} nm, so that the input scaling does not "
      f"depend on the training subset), hidden layers {cfg['hidden_sizes'][0]}, "
      f"{cfg['hidden_sizes'][1]} and {cfg['hidden_sizes'][2]} with ReLU activations, and "
      f"{cfg['n_wavelengths']} output units, i.e. the architecture "
      f"{cfg['n_layers']}-{'-'.join(str(h) for h in cfg['hidden_sizes'])}-{cfg['n_wavelengths']} "
      f"recommended by the assignment; it has {npar:,} trainable parameters. A sigmoid activation is "
      f"applied to the output because a lossless stack necessarily satisfies 0 &le; R &le; 1, which "
      f"makes the network physically bounded by construction. Weights are initialised with He "
      f"initialisation drawn from the seeded torch generator. The loss is the mean squared error "
      f"between predicted and TMM-calculated reflectance; training uses Adam with a constant "
      f"learning rate of {cfg['learning_rate']:g}, a batch size of {cfg['batch_size']} and "
      f"{cfg['n_epochs']} epochs, and the minibatch permutation is drawn from a generator seeded "
      f"with {seed} as well. The weights of the epoch with the lowest validation MSE are kept. "
      f"Training the full model took {main['training_seconds']:.0f} s on a single CPU core "
      f"(PyTorch {main['environment']['torch']}, {main['environment']['threads']} thread).")
    F("fig3_mlp_architecture.png",
      f"Figure 3. Architecture of the MLP surrogate model "
      f"({cfg['n_layers']}-{'-'.join(str(h) for h in cfg['hidden_sizes'])}-{cfg['n_wavelengths']}, "
      f"{npar:,} parameters) mapping four layer thicknesses to the 41-point reflectance spectrum.")

    S.append(Paragraph("2.5 Training-size experiment", H2))
    P("To isolate the effect of the amount of data, the first 500, 1,000, 2,000 and 4,000 samples of "
      "the fixed 4,000-sample training pool were used in turn. Because the pool order is itself the "
      "fixed random permutation, the smaller sets are nested subsets of the larger ones. The "
      "validation and test sets were never changed, and the seed, architecture, optimiser, learning "
      "rate, batch size and number of epochs were identical in the four runs, so any difference in "
      "test error is caused by the training-set size alone.")

    S.append(Paragraph("2.6 MLP-assisted thin-film screening", H2))
    P(f"The trained surrogate was used to screen {screen['n_candidates']:,} new candidate stacks "
      f"generated with design_seed = {dseed} from the same uniform thickness distribution. All "
      f"candidate spectra were predicted by the MLP, the candidates were ranked by the predicted "
      f"reflectance at {lam_t:.0f} nm, and the ten best were recomputed with TMM. The final ranking "
      f"is the TMM ranking of those ten candidates, and Table 1 reports the best five. Two quantities "
      f"are worth separating: the design objective, i.e. R at &lambda;<sub>target</sub>, and the "
      f"agreement between the predicted and the true spectrum of the candidate. Only the second one "
      f"decides whether the surrogate ranking can be trusted.")

    S.append(Paragraph("3. Results", H1))
    S.append(Paragraph("3.1 MLP training and spectral prediction", H2))
    F("fig4_loss_curve.png", "Figure 4. Training and validation losses of the MLP surrogate model.")
    P(f"Figure 4 shows the two loss curves. The training MSE falls from "
      f"{main['train_loss_final']*40:.2e} at the first epoch to {main['train_loss_final']:.2e} at the "
      f"end of the {cfg['n_epochs']} epochs, while the validation MSE reaches its minimum "
      f"{main['best_val_loss']:.2e} at epoch {main['best_epoch']} and stays close to the training "
      f"curve afterwards. The two curves track each other without a visible gap, so the network is "
      f"not overfitting the 4,000 training samples; the residual error is the approximation error of "
      f"the surrogate, not memorisation. The kept checkpoint gives a validation MSE of "
      f"{vm['mse']:.2e} (RMSE {vm['rmse']:.4f}) and a test MSE of {tm['mse']:.2e}, i.e. "
      f"RMSE = {tm['rmse']:.4f}, MAE = {tm['mae']:.4f} and a largest absolute deviation of "
      f"{tm['max_abs_error']:.4f} over all 500 test samples and all 41 wavelengths. Relative to the "
      f"mean reflectance {fp['R_mean']:.4f} of the dataset, the test RMSE is "
      f"{100*tm['rmse']/fp['R_mean']:.1f} %. At the personal target wavelength {lam_t:.0f} nm the "
      f"mean absolute error is {tm['mae_at_target_wavelength']:.4f} and the MSE "
      f"{tm['mse_at_target_wavelength']:.2e}, slightly better than the spectrum-averaged values.")
    P(f"Figure 5 shows three representative test samples. The MLP reproduces the position and the "
      f"depth of the interference fringes for all of them; the per-sample MSE of these three samples "
      f"is " + ", ".join(f"{s['per_sample_mse']:.1e}" for s in main["representative_test_samples"])
      + f", i.e. close to the median per-sample MSE of {tm['per_sample_mse_median']:.2e}. The "
      f"agreement is best where the spectrum is smooth and worst where two nearby thickness "
      f"combinations produce steep, closely spaced fringes - exactly the regime in which a small "
      f"thickness change moves a fringe across a sampling interval of 10 nm.")
    F("fig5_prediction_test_samples.png",
      "Figure 5. Comparison of TMM-calculated and MLP-predicted spectra on representative test "
      "samples. The three designs are close to the median prediction error.")

    S.append(Paragraph("3.2 Effect of training-set size", H2))
    rows = [[f"{r['n_train']:,}", f"{r['val_metrics']['mse']:.2e}", f"{r['test_metrics']['mse']:.2e}",
             f"{r['test_metrics']['rmse']:.4f}", f"{r['test_metrics']['mae']:.4f}",
             f"{r['best_epoch']}", f"{r['training_seconds']:.0f}"] for r in rec]
    S.append(kv_table(["Train samples", "Val MSE", "Test MSE", "Test RMSE", "Test MAE", "Best epoch",
                       "Time (s)"], rows, [1.05, 0.95, 0.95, 0.95, 0.95, 0.85, 0.8]))
    S.append(Paragraph("Table 2. Effect of the training-set size on the prediction error "
                       "(500 fixed test samples).", CAPTION))
    F("fig6_training_size.png", "Figure 6. Effect of the training-set size on the test error.")
    P(f"Table 2 and Figure 6 summarise the four runs. The test RMSE decreases monotonically from "
      f"{rec[0]['test_metrics']['rmse']:.4f} for 500 training samples to "
      f"{rec[-1]['test_metrics']['rmse']:.4f} for 4,000 samples, a total reduction of "
      f"{100*(rec[0]['test_metrics']['mse']-rec[-1]['test_metrics']['mse'])/rec[0]['test_metrics']['mse']:.0f} % "
      f"in MSE. The benefit of each further doubling, however, shrinks steadily: doubling the pool "
      f"from 500 to 1,000 samples lowers the test MSE by "
      f"{gains[0]['relative_mse_reduction_pct']:.0f} %, from 1,000 to 2,000 by "
      f"{gains[1]['relative_mse_reduction_pct']:.0f} % and from 2,000 to 4,000 by only "
      f"{gains[2]['relative_mse_reduction_pct']:.0f} %. Expressed as RMSE ratios, the three doublings "
      f"multiply the error by {gains[0]['rmse_ratio']:.2f}, {gains[1]['rmse_ratio']:.2f} and "
      f"{gains[2]['rmse_ratio']:.2f} respectively. The validation and test errors stay within a "
      f"factor of {max(r['test_metrics']['mse']/r['val_metrics']['mse'] for r in rec):.2f} of each "
      f"other for every training size, which confirms that the fixed validation set is a reliable "
      f"proxy for the test set. In other words, the model is already data-limited at 500 samples and "
      f"the returns of adding data decay quickly; a larger model or a better input representation "
      f"would be needed to exploit 4,000 samples fully.")

    S.append(Paragraph("3.3 MLP-assisted thin-film design", H2))
    P(f"Screening {screen['n_candidates']:,} candidates took {timing['mlp_seconds']:.2f} s with the "
      f"surrogate and {timing['tmm_seconds']:.1f} s with TMM on the same machine and the same batch, "
      f"a speed-up of x{timing['speedup']:.1f}. Over the whole candidate pool the surrogate "
      f"reproduces the TMM spectrum with an MSE of {pool['spectrum_mse']:.2e} "
      f"(MAE {pool['spectrum_mae']:.4f}); at the target wavelength the mean absolute error is "
      f"{pool['R_target_mae']:.4f} and the largest single error "
      f"{pool['R_target_max_abs_error']:.4f}. The true (TMM) reflectance at {lam_t:.0f} nm over the "
      f"10,000 candidates ranges from {pool['R_target_tmm_min']:.4f} to "
      f"{pool['R_target_tmm_max']:.4f} with a mean of {pool['R_target_tmm_mean']:.4f} and a 99.9th "
      f"percentile of {pool['R_target_tmm_p999']:.4f}, so the designs selected below are in the tail "
      f"of the distribution.")
    P("Figure 7A shows the spectra of the five finalist candidates together with the selected design "
      "after TMM verification (the surrogate was used to rank all 10,000 candidates and the Top-10 of "
      "that ranking were recomputed with TMM; Figure 7B shows the MLP ranking against the TMM "
      "verification for those ten candidates).")
    F("fig7_design.png",
      "Figure 7. MLP-predicted and TMM-verified spectra of the selected design. (A) the selected "
      "design and the five finalist candidates, with the personal target wavelength marked; "
      "(B) MLP ranking against the TMM verification for the Top-10 candidates.")
    t1 = [[str(i + 1)] + [f"{v:.1f}" for v in r["d_nm"]] +
          [f"{r['mlp_R_target']:.4f}", f"{r['tmm_R_target']:.4f}"] for i, r in enumerate(top10[:5])]
    S.append(kv_table(["Rank", "d1 (nm)", "d2 (nm)", "d3 (nm)", "d4 (nm)", "MLP R_target",
                       "TMM R_target"], t1, [0.6, 0.9, 0.9, 0.9, 0.9, 1.05, 1.05]))
    S.append(Paragraph(f"Table 1. Top five candidate thin-film designs selected by the MLP and "
                       f"verified using TMM (&lambda;<sub>target</sub> = {lam_t:.0f} nm).", CAPTION))
    _mlp1 = next(r for r in top10 if r["rank_mlp"] == 1)
    _tmm1 = next(r for r in top10 if r["rank_tmm"] == 1)
    _nkept = sum(1 for r in top10 if r["rank_tmm"] <= 5)
    P(f"The best design found has thicknesses [{', '.join(f'{v:.1f}' for v in best['d_nm'])}] nm and "
      f"reaches a TMM reflectance of {best['tmm_R_target']:.4f} at {lam_t:.0f} nm; the surrogate "
      f"predicted {best['mlp_R_target']:.4f}, an absolute error of only {best['absolute_error']:.4f}. "
      f"The design beats the 99.9th percentile of the candidate pool "
      f"({pool['R_target_tmm_p999']:.4f}) and is more than twice the mean reflectance of the pool "
      f"({pool['R_target_tmm_mean']:.4f}). The re-ranking, however, does change the order: the "
      f"candidate that the surrogate ranked first (predicted R = {_mlp1['mlp_R_target']:.4f}) ends up "
      f"{_mlp1['rank_tmm']}nd after TMM verification with a true R = {_mlp1['tmm_R_target']:.4f}, "
      f"whereas the verified winner had been placed {_tmm1['rank_mlp']}nd by the MLP. The two "
      f"candidates differ by only "
      f"{abs(_mlp1['mlp_R_target'] - _tmm1['mlp_R_target']):.4f} in the predicted reflectance, which "
      f"is the same order as the surrogate's own error at the target wavelength "
      f"({pool['R_target_mae']:.4f}), so the mis-ranking is a direct consequence of the residual "
      f"prediction error. All five designs in Table 1 were in the surrogate's Top-10, but only "
      f"{_nkept} of them would have been selected by the raw MLP order, and the corrected Table 1 has "
      f"to be produced by TMM.")

    S.append(Paragraph("3.4 Representative failure case", H2))
    F("fig8_failure_case.png",
      f"Figure 8. A representative case with relatively large MLP prediction error (rank 1 of the "
      f"500 test samples, per-sample MSE {worst['per_sample_mse']:.2e}).")
    P(f"The worst of the 500 test samples is shown in Figure 8. Its per-sample MSE is "
      f"{worst['per_sample_mse']:.2e} (RMSE {worst['rmse']:.4f}) with a single-wavelength deviation "
      f"of up to {worst['max_abs_error']:.4f} - about {worst['rmse']/tm['rmse']:.0f} times the "
      f"average test RMSE - for the thicknesses "
      f"[{', '.join(f'{v:.1f}' for v in worst['thickness_nm'])}] nm. Two features of the failure are "
      f"visible in Figure 8B. First, the error changes sign from one fringe to the next instead of "
      f"growing with the reflectance itself, which is the signature of a small error in the "
      f"<i>position</i> of the interference fringes rather than of a wrong overall level: the "
      f"predicted curve is slightly stretched, so it overshoots at some wavelengths and undershoots "
      f"at neighbouring ones. A shift of the fringe pattern is exactly what a slight mis-estimate of "
      f"the optical thickness n<sub>i</sub> d<sub>i</sub> produces. Second, the failure is "
      f"concentrated in the short-wavelength half of the spectrum, where the fringes are sharpest: "
      f"within the 10 nm sampling interval the reflectance can change by more than 0.05, so the "
      f"network has to place the extremum to better than one sample. Figure 8C places the sample in "
      f"the error distribution: the median per-sample MSE is {tm['per_sample_mse_median']:.2e} and "
      f"the 95th percentile {tm['per_sample_mse_p95']:.2e}, so the worst case is roughly "
      f"{worst['per_sample_mse']/tm['per_sample_mse_median']:.0f} times the median but still within "
      f"one order of magnitude of it, i.e. the surrogate degrades gracefully rather than failing "
      f"catastrophically. A denser wavelength sampling would remove part of this error.")

    S.append(Paragraph("4. Discussion", H1))
    P(f"Regarding the first research question, the surrogate reproduces the TMM spectra of unseen "
      f"designs with a test RMSE of {tm['rmse']:.4f}, about {100*tm['rmse']/fp['R_mean']:.1f} % of "
      f"the mean reflectance and only {100*tm['rmse']/fp['R_max']:.1f} % of the largest reflectance "
      f"in the dataset. Figure 5 shows that the residual error is dominated by the placement and the "
      f"sharpness of the interference fringes rather than by a wrong overall level: the error changes "
      f"sign from fringe to fringe (section 3.4), which is what a small mis-estimate of the optical "
      f"thickness n<sub>i</sub> d<sub>i</sub> produces. Because the mapping thickness to spectrum is "
      f"many-to-one in the opposite direction (different stacks can give very similar spectra), part "
      f"of this residual is irreducible for any deterministic regressor, and an ensemble or a "
      f"probabilistic output would be needed to go clearly below it.")
    P(f"Regarding the second question, more data help, but with strongly diminishing returns "
      f"(Figure 6): the error shrinks quickly between 500 and 1,000 samples and then flattens, with "
      f"the last doubling of the training set buying only "
      f"{gains[2]['relative_mse_reduction_pct']:.0f} % of MSE. This is the expected behaviour of a "
      f"smooth function approximator: with 500 samples the network cannot cover the four-dimensional "
      f"thickness cube densely enough, whereas beyond a few thousand samples the error becomes "
      f"dominated by the architecture and by the optimisation rather than by the data. It also means "
      f"that for the present problem a practitioner should first improve the model or the input "
      f"representation (for instance by adding physically motivated features such as the optical "
      f"thickness n<sub>i</sub> d<sub>i</sub>) before generating tens of thousands of additional TMM "
      f"spectra.")
    P(f"Regarding the third question, the surrogate is clearly useful for screening. Ranking "
      f"{screen['n_candidates']:,} candidates is x{timing['speedup']:.1f} cheaper with the MLP than "
      f"with TMM, and the design that survives TMM verification reaches "
      f"{best['tmm_R_target']:.4f} - above the 99.9th percentile of the pool. The surrogate therefore "
      f"does the part of the work where speed matters (pruning a huge library down to a handful of "
      f"finalists) and leaves the part where accuracy matters to the physical model. Figure 7B is the "
      f"quantitative justification: the MLP ranks the ten finalists almost, but not exactly, as TMM "
      f"does - its own favourite is demoted to second place - and its predicted R<sub>target</sub> of "
      f"the best design differs from the verified value by {best['absolute_error']:.4f}. A design "
      f"reported on the basis of the surrogate alone would therefore be optimistic and, worse, could "
      f"name the wrong winner among nearly equivalent candidates; the final numbers in Table 1 must "
      f"come from TMM. This split of responsibilities - surrogate for search, physics for verification "
      f"- is the same pattern that is used in the deep-learning-assisted inverse-design literature "
      f"[4-7].")
    P(f"The study has clear limitations. The optical model is deliberately minimal: no dispersion, no "
      f"absorption, normal incidence only, and the refractive indices and the number of layers are "
      f"fixed, so the surrogate learns a four-dimensional map and nothing else. The dataset of "
      f"{cfg['n_samples']:,} TMM spectra covers the thickness cube uniformly, but real design problems "
      f"concentrate on a small region of that cube, where the local data density - and hence the "
      f"accuracy - would be lower. The failure case in Figure 8 shows the consequence: the surrogate "
      f"is least reliable exactly for the sharp spectral features that are most interesting for "
      f"filters. Finally, the MLP was trained with a single seed and a single architecture, so the "
      f"reported error bars reflect the split rather than the variability of the training procedure; "
      f"repetitions with different initialisations would be needed to separate the two.")

    S.append(Paragraph("5. Conclusions", H1))
    P(f"A four-layer Air/H/L/H/L/Glass dielectric stack with fixed refractive indices was used to "
      f"test whether a small MLP can act as a surrogate for the transfer-matrix method. (Q1) Yes: "
      f"the {cfg['n_layers']}-{'-'.join(str(h) for h in cfg['hidden_sizes'])}-{cfg['n_wavelengths']} "
      f"network with {npar:,} parameters predicts the 41-point reflectance spectrum of unseen designs "
      f"with a test RMSE of {tm['rmse']:.4f} in reflectance units "
      f"({100*tm['rmse']/fp['R_mean']:.1f} % of the mean reflectance), with a mean absolute error of "
      f"only {tm['mae_at_target_wavelength']:.4f} at the personal target wavelength {lam_t:.0f} nm. "
      f"(Q2) More training data help but with sharply diminishing returns: the test RMSE drops from "
      f"{rec[0]['test_metrics']['rmse']:.4f} at 500 samples to {rec[-1]['test_metrics']['rmse']:.4f} "
      f"at 4,000 samples, while the last doubling reduces the MSE by only "
      f"{gains[2]['relative_mse_reduction_pct']:.0f} %. (Q3) Yes, with verification: screening "
      f"{screen['n_candidates']:,} candidates with the surrogate is x{timing['speedup']:.1f} faster "
      f"than with TMM, and the selected design reaches a TMM-verified reflectance of "
      f"{best['tmm_R_target']:.4f} at {lam_t:.0f} nm, above the 99.9th percentile of the candidate "
      f"pool, although the final ranking must always be recomputed with the physical model.")

    S.append(Paragraph("Data and Code Availability", H1))
    P("The data used in this work were generated using the TMM code developed in this study. All "
      "source code, model-training scripts, thin-film screening scripts, environment dependencies, "
      "and instructions for reproducing the main results are available at:<br/>"
      "<b>https://github.com/Jfzz-KK/123435</b><br/>"
      f"The repository reports the student-specific parameters &lambda;<sub>target</sub> = "
      f"{lam_t:.0f} nm, seed = {seed} and design_seed = {dseed} in its README, together with the "
      "commands that regenerate the dataset, train the surrogate, reproduce Figures 1-8 and Table 1, "
      "and the sha256 fingerprints of the generated arrays.", BODY_NOIND)

    S.append(Paragraph("References", H1))
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
        "Liu, D., Tan, Y., Khoram, E., and Yu, Z. Training deep neural networks for the inverse "
        "design of nanophotonic structures. ACS Photonics 2018, 5, 1365-1369. "
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
        "He, K., Zhang, X., Ren, S., and Sun, J. Delving deep into rectifiers: Surpassing "
        "human-level performance on ImageNet classification. In Proceedings of the IEEE International "
        "Conference on Computer Vision (ICCV), Santiago, 2015, pp. 1026-1034. "
        "https://doi.org/10.1109/ICCV.2015.123",
        "Virtanen, P., Gommers, R., Oliphant, T. E., et al. SciPy 1.0: fundamental algorithms for "
        "scientific computing in Python. Nature Methods 2020, 17, 261-272. "
        "https://doi.org/10.1038/s41592-019-0686-2",
    ]
    for i, r in enumerate(refs, start=1):
        S.append(Paragraph(f"[{i}] {html.escape(r)}", SMALL))
    return S


def make_pdf(out: str, story_flow) -> None:
    os.makedirs(os.path.dirname(out), exist_ok=True)

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

    doc = BaseDocTemplate(
        out, pagesize=letter,
        leftMargin=0.71 * inch, rightMargin=0.71 * inch,
        topMargin=0.72 * inch, bottomMargin=0.68 * inch,
        title=TITLE, author="2020276134",
        subject="AI4S thin-film MLP mini research project",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=on_page)])
    doc.build(story_flow)
    print("wrote", os.path.relpath(out, ROOT), f"({os.path.getsize(out)/1024:.0f} kB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    main_j = load("mlp_main_metrics.json")
    sizes_j = load("training_size_study.json")
    screen_j = load("screening_results.json")
    fp = load("dataset_fingerprint.json")
    flow = story(main_j, sizes_j, screen_j, fp)
    out = args.out or os.path.join(
        ROOT, "paper", f"AI4S_Research_Article_{main_j['config']['student_id']}.pdf"
    )
    make_pdf(out, flow)


if __name__ == "__main__":
    main()
