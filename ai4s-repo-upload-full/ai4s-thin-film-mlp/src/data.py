"""Deterministic dataset construction for the thin-film surrogate study.

Everything here is driven by the student-specific :mod:`config`, so running the
script twice (or on another machine) reproduces exactly the same arrays:

* thicknesses      -- ``(5000, 4)`` uniform in [40, 180] nm
* target spectra   -- ``(5000, 41)`` TMM reflectance for 400-800 nm, 10 nm step
* one fixed random permutation splits the data into 4000 / 500 / 500

The split is created *once* and never touched again, which is what the
assignment requires ("此划分在后续所有实验中保持不变").
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg  # noqa: E402
import runtime  # noqa: E402  (sets matplotlib/temp env vars)
from tmm import ThinFilmStack  # noqa: E402


def thickness_grid(rng: np.random.Generator) -> np.ndarray:
    """``(N, 4)`` uniform random layer thicknesses in nm, one row per sample."""
    return rng.uniform(cfg.D_MIN_NM, cfg.D_MAX_NM, size=(cfg.N_SAMPLES, cfg.N_LAYERS))


def build_dataset(seed: int | None = None, verbose: bool = True) -> dict:
    """Generate thicknesses + TMM spectra and one fixed 4000/500/500 split."""
    seed = cfg.SEED if seed is None else int(seed)
    rng = np.random.default_rng(seed)

    thickness = thickness_grid(rng)
    stack = ThinFilmStack(cfg.STACK, cfg.N_H, cfg.N_L, cfg.N_S, cfg.N_INC)
    spectra = stack.reflectance(thickness, np.asarray(cfg.WAVELENGTHS_NM))
    assert spectra.shape == (cfg.N_SAMPLES, cfg.N_WAVELENGTHS)

    # one fixed random permutation -> train / val / test index sets
    order = rng.permutation(cfg.N_SAMPLES)
    idx_train = np.sort(order[: cfg.N_TRAIN])
    idx_val = np.sort(order[cfg.N_TRAIN : cfg.N_TRAIN + cfg.N_VAL])
    idx_test = np.sort(order[cfg.N_TRAIN + cfg.N_VAL :])

    if verbose:
        print(
            f"dataset: {thickness.shape[0]} samples, spectra {spectra.shape}, "
            f"R in [{spectra.min():.4f}, {spectra.max():.4f}]"
        )
        print(f"         train {idx_train.size} / val {idx_val.size} / test {idx_test.size}")

    return {
        "seed": seed,
        "thickness": thickness,
        "spectra": spectra,
        "idx_train": idx_train,
        "idx_val": idx_val,
        "idx_test": idx_test,
        "wavelengths_nm": np.asarray(cfg.WAVELENGTHS_NM, dtype=float),
    }


def sha256_of_arrays(**arrays) -> str:
    """Stable digest of the generated arrays, quoted in the paper/README."""
    h = hashlib.sha256()
    for name in sorted(arrays):
        arr = np.ascontiguousarray(np.asarray(arrays[name], dtype=np.float64))
        h.update(name.encode())
        h.update(str(arr.shape).encode())
        h.update(arr.tobytes())
    return h.hexdigest()


def fingerprint(data: dict) -> dict:
    return {
        "seed": int(data["seed"]),
        "n_samples": int(data["thickness"].shape[0]),
        "n_wavelengths": int(data["spectra"].shape[1]),
        "thickness_sha256": sha256_of_arrays(thickness=data["thickness"]),
        "spectra_sha256": sha256_of_arrays(spectra=data["spectra"]),
        "split_sha256": sha256_of_arrays(
            idx_train=data["idx_train"], idx_val=data["idx_val"], idx_test=data["idx_test"]
        ),
        "R_min": float(data["spectra"].min()),
        "R_max": float(data["spectra"].max()),
        "R_mean": float(data["spectra"].mean()),
    }


def main() -> None:
    runtime.seed_everything(cfg.SEED)
    data = build_dataset()
    fp = fingerprint(data)
    paths = cfg.paths()
    runtime.dump_json(
        {**fp, "config": cfg.as_dict()}, os.path.join(paths.results, "dataset_fingerprint.json")
    )
    np.savez_compressed(
        os.path.join(paths.data, "dataset.npz"),
        thickness=data["thickness"],
        spectra=data["spectra"],
        idx_train=data["idx_train"],
        idx_val=data["idx_val"],
        idx_test=data["idx_test"],
        wavelengths_nm=data["wavelengths_nm"],
    )
    print(json.dumps(fp, indent=2))
    print(cfg.summary())


if __name__ == "__main__":
    main()
