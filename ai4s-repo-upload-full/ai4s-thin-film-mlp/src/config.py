"""Student-specific configuration for the AI4S thin-film MLP mini project.

All personal parameters are derived from the student ID, exactly as required by
the assignment (section 3 of the assignment sheet):

    lambda_target = 450 + 10 * (N mod 31)  nm,  N = last two digits of the ID
    seed          = integer value of the last six digits of the ID
    design_seed   = seed + 1

The values below are the only place in the repository where the personal
parameters are written down; every other script imports them from here so that
the whole study can be reproduced with a single edit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# --------------------------------------------------------------------------
# 1. Personal parameters  (EDIT THIS BLOCK ONLY IF THE STUDENT ID CHANGES)
# --------------------------------------------------------------------------
STUDENT_ID = "2020276134"
STUDENT_NAME = "Jfzz-KK"  # fill in your name before submission

# --------------------------------------------------------------------------
# 2. Physics constants fixed by the assignment
# --------------------------------------------------------------------------
N_H = 2.30          # high-index layer
N_L = 1.45          # low-index layer (spacer)
N_S = 1.52          # glass substrate
N_INC = 1.0         # air, incident medium
N_LAYERS = 4
STACK = ("H", "L", "H", "L")   # Air / H / L / H / L / Glass

D_MIN_NM = 40.0
D_MAX_NM = 180.0

WAVELENGTH_MIN_NM = 400.0
WAVELENGTH_MAX_NM = 800.0
WAVELENGTH_STEP_NM = 10.0

N_SAMPLES = 5000
N_TRAIN = 4000
N_VAL = 500
N_TEST = 500

N_CANDIDATES = 10_000

# --------------------------------------------------------------------------
# 3. Model / training hyper-parameters
# --------------------------------------------------------------------------
HIDDEN_SIZES = (128, 128, 64)
BATCH_SIZE = 64
LEARNING_RATE = 1e-3
N_EPOCHS = 2000
TRAIN_SIZES = (500, 1000, 2000, 4000)


def _last_two_digits(student_id: str) -> int:
    return int(student_id[-2:])


def _last_six_digits(student_id: str) -> int:
    return int(student_id[-6:])


N_MOD = _last_two_digits(STUDENT_ID)
SEED = _last_six_digits(STUDENT_ID)
DESIGN_SEED = SEED + 1
LAMBDA_TARGET_NM = 450.0 + 10.0 * (N_MOD % 31)
TARGET_INDEX = int(round((LAMBDA_TARGET_NM - WAVELENGTH_MIN_NM) / WAVELENGTH_STEP_NM))

WAVELENGTHS_NM = tuple(
    WAVELENGTH_MIN_NM + WAVELENGTH_STEP_NM * i
    for i in range(int(round((WAVELENGTH_MAX_NM - WAVELENGTH_MIN_NM) / WAVELENGTH_STEP_NM)) + 1)
)
N_WAVELENGTHS = len(WAVELENGTHS_NM)


@dataclass(frozen=True)
class Paths:
    root: str
    data: str
    figures: str
    results: str
    models: str
    tables: str


def project_root() -> str:
    """Repository root (the folder that contains ``src/``)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def paths() -> Paths:
    root = project_root()
    p = Paths(
        root=root,
        data=os.path.join(root, "data"),
        figures=os.path.join(root, "figures"),
        results=os.path.join(root, "results"),
        models=os.path.join(root, "models"),
        tables=os.path.join(root, "results", "tables"),
    )
    for d in (p.data, p.figures, p.results, p.models, p.tables):
        os.makedirs(d, exist_ok=True)
    return p


def as_dict() -> dict:
    return {
        "student_id": STUDENT_ID,
        "n_mod": N_MOD,
        "lambda_target_nm": LAMBDA_TARGET_NM,
        "target_index": TARGET_INDEX,
        "seed": SEED,
        "design_seed": DESIGN_SEED,
        "n_layers": N_LAYERS,
        "stack": list(STACK),
        "n_h": N_H,
        "n_l": N_L,
        "n_s": N_S,
        "d_range_nm": [D_MIN_NM, D_MAX_NM],
        "wavelength_range_nm": [WAVELENGTH_MIN_NM, WAVELENGTH_MAX_NM],
        "wavelength_step_nm": WAVELENGTH_STEP_NM,
        "n_wavelengths": N_WAVELENGTHS,
        "n_samples": N_SAMPLES,
        "split": [N_TRAIN, N_VAL, N_TEST],
        "hidden_sizes": list(HIDDEN_SIZES),
        "batch_size": BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
        "n_epochs": N_EPOCHS,
        "train_sizes": list(TRAIN_SIZES),
        "n_candidates": N_CANDIDATES,
    }


def summary() -> str:
    return (
        f"student_id = {STUDENT_ID}\n"
        f"N (last two digits)      = {N_MOD}\n"
        f"lambda_target            = {LAMBDA_TARGET_NM:.0f} nm  "
        f"(index {TARGET_INDEX} of {N_WAVELENGTHS})\n"
        f"seed                     = {SEED}\n"
        f"design_seed              = {DESIGN_SEED}\n"
    )


if __name__ == "__main__":
    print(summary())
