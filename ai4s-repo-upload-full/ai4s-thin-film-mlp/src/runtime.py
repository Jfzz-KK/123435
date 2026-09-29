"""Runtime helpers shared by every script.

Two jobs:

1.  Make matplotlib work in a sandboxed environment (its default config/cache
    directory may not be writable) and use a headless backend.
2.  Provide deterministic seeding and JSON helpers so that every reported number
    can be traced back to a script run.

Import this module *before* matplotlib::

    import runtime  # noqa: F401
    import matplotlib.pyplot as plt
"""

from __future__ import annotations

import json
import os
import random
import sys

# --------------------------------------------------------------------------
# writable matplotlib config directory
# --------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# Temporary/cache directories must live inside the active workspace.  The study
# is developed on D: but the code also runs from the original C: checkout.
_TMP_CANDIDATES = (
    r"D:\deepseek-harness\default-workspace\tmp",
    r"C:\Users\JF\Documents\deepseek-harness\default-workspace\tmp",
    os.path.join(_ROOT, "tmp"),
)
_TMP = next((p for p in _TMP_CANDIDATES if os.path.isdir(os.path.dirname(p))), _TMP_CANDIDATES[-1])
_MPL = os.path.join(os.path.dirname(_TMP), "mplconfig")
for _d in (_TMP, _MPL):
    try:
        os.makedirs(_d, exist_ok=True)
    except OSError:
        pass
os.environ.setdefault("TMPDIR", _TMP)
os.environ.setdefault("TEMP", _TMP)
os.environ.setdefault("MPLCONFIGDIR", _MPL)
os.environ.setdefault("MPLBACKEND", "Agg")
# keep BLAS/OpenMP single-threaded so that results are reproducible run to run
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

sys.path.insert(0, _HERE)


def seed_everything(seed: int, deterministic: bool = True) -> None:
    """Seed python, numpy and torch (if available)."""
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except Exception:  # pragma: no cover
        pass
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.use_deterministic_algorithms(deterministic, warn_only=True)
        if deterministic:
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    except Exception:  # pragma: no cover
        pass


def dump_json(obj, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False, default=_default)
    print("wrote", os.path.relpath(path, _ROOT))


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _default(o):
    try:
        import numpy as np

        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except Exception:
        pass
    raise TypeError(f"not JSON serialisable: {type(o)!r}")


def root() -> str:
    return _ROOT


def fmt(x: float, nd: int = 4) -> str:
    return f"{x:.{nd}f}"
