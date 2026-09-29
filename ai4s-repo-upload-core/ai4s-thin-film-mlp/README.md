# AI for Thin Films — MLP-Based Spectral Prediction and Data-Driven Design of Multilayer Dielectric Thin Films

Course assignment for **薄膜技术 · AI4S** (AI for Thin Films · MLP Mini Research Project).

This repository contains everything needed to reproduce the accompanying Research Article:
the transfer-matrix-method (TMM) data generator, the MLP surrogate, the three experiments
(spectral prediction, training-set-size study, MLP-assisted screening), all figures and
tables, and the manuscript itself.

## Student-specific parameters (required in this README)

| Quantity | Value | How it is obtained |
|---|---|---|
| Student ID | `2020276134` | — |
| `N` (last two digits) | `34` | `int(student_id[-2:])` |
| **λtarget** | **480 nm** | `450 + 10 × (N mod 31) = 450 + 10 × 3` |
| **seed** | **276134** | `int(student_id[-6:])` |
| **design_seed** | **276135** | `seed + 1` |

Wavelength index of λtarget: **8** of the 41 samples (400, 410, …, 800 nm).

All three values are defined in exactly one place, [`src/config.py`](src/config.py), and every
script imports them from there. The scripts set them explicitly at start-up:

```python
random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); design_seed = seed + 1
```

## Repository layout

```
ai4s-thin-film-mlp/
├── src/
│   ├── config.py          # personal parameters + all physics/training constants
│   ├── tmm.py             # transfer-matrix method (Air/H/L/H/L/Glass, normal incidence)
│   ├── data.py            # 5,000-design dataset + the fixed 4000/500/500 split
│   ├── train_utils.py     # MLP 4-128-128-64-41, training loop, error metrics
│   ├── train_mlp.py       # experiment 3.1  (Figures 1-5 and 8)
│   ├── train_sizes.py     # experiment 3.2  (Figure 6, Table 2)
│   ├── screening.py       # experiment 3.3  (Figure 7, Table 1)
│   ├── viz.py             # all figures (PNG + PDF)
│   ├── make_paper.py      # builds the Word manuscript from the result JSONs
│   └── runtime.py         # seeding and matplotlib/headless helpers
├── tools/wheel_install.py # dependency-free wheel installer (fallback for pip)
├── tests/test_tmm.py      # six physics sanity checks for the TMM implementation
├── templates/docx_template/  # styles of the course Word template
├── data/                  # dataset.npz (generated)
├── figures/               # fig1..fig8 .png + .pdf (generated)
├── models/                # mlp_main.pt, mlp_n500/1000/2000.pt (generated)
├── results/               # JSON metrics, fingerprints, tables/ (generated)
├── paper/                 # the generated manuscript (docx + pdf)
└── requirements.txt
```

## Environment

Python 3.12, PyTorch CPU. No GPU is required; the full pipeline runs in about
**9 minutes on a single CPU core**.

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# CPU-only PyTorch build:
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Verified with `numpy 2.5.3`, `matplotlib 3.11.2`, `torch 2.14.0+cpu`, `Python 3.12.8`.

## How to reproduce every result

Run the four commands below **in order** from the repository root. All of them are
deterministic: the same commands reproduce the same numbers, figures and tables on any
machine (single-threaded BLAS/OpenMP is forced by `src/runtime.py`).

```bash
# 0) physics sanity checks (6 asserts)
python tests/test_tmm.py

# 1) dataset: 5,000 TMM spectra + the fixed 4000/500/500 split   (~10 s)
python src/data.py
#    -> data/dataset.npz, results/dataset_fingerprint.json

# 2) main training run: Figures 1-5 and 8                        (~90 s)
python src/train_mlp.py
#    -> models/mlp_main.pt, results/mlp_main_metrics.json, figures/fig{1,2,3,4,5,8}_*

# 3) training-set-size study: Figure 6 and Table 2               (~2-3 min)
python src/train_sizes.py
#    -> models/mlp_n{500,1000,2000}.pt, results/training_size_study.json,
#       results/tables/training_size_results.csv, figures/fig6_*

# 4) MLP-assisted screening: Figure 7 and Table 1                (~10 s)
python src/screening.py
#    -> results/screening_results.json, results/tables/table1_top5.md, figures/fig7_*

# 5) build the manuscript (optional; needs the results of steps 2-4)
python src/make_paper.py       # Word, English
python src/make_pdf.py         # PDF,  English
```

A Chinese manuscript (Chinese body text *and* Chinese figure labels) is produced with:

```bash
python src/train_mlp.py   --lang zh
python src/train_sizes.py --lang zh
python src/screening.py   --lang zh
python src/make_paper_zh.py    # Word
python src/make_pdf_zh.py      # PDF
```

`python run_all.py` runs the whole English pipeline in one go (`--quick` skips the
training-size study).

### Numerical fingerprint of the dataset

`results/dataset_fingerprint.json` records sha256 digests that make the data checkable at a
glance:

| Array | sha256 (first 16 hex) |
|---|---|
| thicknesses (5000 × 4) | `b01a114170b65a8f` |
| spectra (5000 × 41) | `55bda16158cadb23` |
| train/val/test split | `9898a922634fd93b` |

`R ∈ [0.000005, 0.658225]`, mean `R = 0.301736`.

## Main results (all numbers produced by the commands above)

**Q1 — Can the MLP predict the spectrum?** Yes.

| Metric (500 test samples × 41 wavelengths) | Value |
|---|---|
| Test MSE | 7.93 × 10⁻⁵ |
| Test RMSE | 8.91 × 10⁻³ |
| Test MAE | 6.52 × 10⁻³ |
| Largest single deviation (all samples/wavelengths) | 7.12 × 10⁻² |
| MAE at λtarget = 480 nm | 7.76 × 10⁻³ |
| Trainable parameters | 28,073 |
| Best epoch / training time | 1918 / 85.6 s |

Test RMSE is 3.0 % of the mean reflectance and 1.4 % of the maximum reflectance in the
dataset. No overfitting is visible: the validation and training curves coincide.

**Q2 — Effect of the training-set size?** Monotone improvement with clearly diminishing returns.

| Training samples | Val MSE | Test MSE | Test RMSE | Test MAE | Best epoch |
|---|---|---|---|---|---|
| 500 | 9.43 × 10⁻⁴ | 8.33 × 10⁻⁴ | 0.02886 | 0.02034 | 1837 |
| 1000 | 3.46 × 10⁻⁴ | 2.87 × 10⁻⁴ | 0.01695 | 0.01206 | 1971 |
| 2000 | 1.64 × 10⁻⁴ | 1.35 × 10⁻⁴ | 0.01160 | 0.00832 | 1938 |
| 4000 | 8.55 × 10⁻⁵ | 7.93 × 10⁻⁵ | 0.00891 | 0.00652 | 1918 |

Each doubling reduces the test MSE by **65.5 %**, **53.2 %** and **41.1 %** respectively
(RMSE ratios 0.587, 0.684, 0.768): the marginal benefit decays steadily.

**Q3 — Can the MLP assist the design?** Yes, with TMM verification.

| Quantity | Value |
|---|---|
| Candidates screened (design_seed = 276135) | 10,000 |
| Forward-model time, MLP / TMM | 0.008 s / 0.111 s (×13–14) |
| Selected design (d₁…d₄) | 51.9 / 86.8 / 158.1 / 77.7 nm |
| MLP prediction at 480 nm | 0.6636 |
| **TMM-verified reflectance at 480 nm** | **0.6566** |
| 99.9th percentile of the candidate pool | 0.6492 |
| Mean reflectance of the candidate pool | 0.2994 |

The surrogate's own number-one candidate (predicted R = 0.6674, d = 161.5 / 84.9 / 49.7 / 76.1 nm)
is **demoted to second place** by TMM (true R = 0.6527), while the verified winner had been placed
second by the MLP. The two predictions differ by 0.0038, i.e. the same order as the surrogate's own
error at λtarget — which is exactly why the final table must be produced by TMM. The full
MLP-vs-TMM ranking of the ten finalists is in
[`results/tables/screening_top10_rankings.md`](results/tables/screening_top10_rankings.md).

Table 1 (top five, TMM-verified) is in [`results/tables/table1_top5.md`](results/tables/table1_top5.md).

**Failure case.** The worst of the 500 test samples (per-sample MSE 5.33 × 10⁻⁴, RMSE
0.0231, largest single deviation 0.0619) is analysed in Figure 8; the error changes sign
from fringe to fringe, i.e. it is dominated by a small error in the position of the
interference fringes, and it is largest in the short-wavelength half of the spectrum.

## Physical and numerical conventions

* Stack Air / H / L / H / L / Glass, 4 layers; normal incidence; no absorption, no dispersion.
* `n_H = 2.30`, `n_L = 1.45`, `n_s = 1.52`, `n_0 = 1.00`; each `d_i ∈ [40, 180] nm`.
* δᵢ = 2π nᵢ dᵢ / λ; characteristic matrix
  `M_i = [[cos δᵢ, i sin δᵢ / ηᵢ], [i ηᵢ sin δᵢ, cos δᵢ]]` with `ηᵢ = nᵢ`;
  `M = M₁M₂M₃M₄`, `Y = (M₂₁ + M₂₂η_s)/(M₁₁ + M₁₂η_s)`, `r = (η₀ − Y)/(η₀ + Y)`, `R = |r|²`.
* Wavelengths 400–800 nm in 10 nm steps (41 points).
* MLP 4–128–128–64–41, ReLU hidden layers, sigmoid output, He initialisation, MSE loss,
  Adam (lr 1e-3), batch 64, 2000 epochs, weights of the best validation epoch kept.

## Data and Code Availability

All source code, model-training scripts, screening scripts, environment dependencies and the
instructions above live in this public repository:

**<https://github.com/Jfzz-KK/123435>**

The dataset is not stored in the repository: it is regenerated deterministically with
`python src/data.py` and verified against the sha256 fingerprints quoted in the
[dataset fingerprint](results/dataset_fingerprint.json) table above.

## License / academic integrity

The code in this repository was written for this assignment. AI assistance was used for
debugging, code structure and language polishing; all reported numbers, figures and tables
are produced by the scripts in this repository and were not fabricated. See the manuscript's
"Data and Code Availability" section for the public repository URL.
