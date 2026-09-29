"""Sanity checks for the TMM implementation.

Run with ``python tests/test_tmm.py`` (plain asserts, no pytest required).
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import config as cfg  # noqa: E402
from tmm import ThinFilmStack, reflectance  # noqa: E402


def test_single_interface_matches_fresnel() -> None:
    """Zero-thickness layers must reduce to a single air/glass interface."""
    stack = ThinFilmStack(("H",), n_h=cfg.N_S)  # one layer with n = n_s
    lam = np.array([550.0])
    R = stack.reflectance(np.array([0.0]), lam)[0]
    r_fresnel = ((cfg.N_INC - cfg.N_S) / (cfg.N_INC + cfg.N_S)) ** 2
    assert abs(R - r_fresnel) < 1e-12, (R, r_fresnel)
    print(f"  air/glass interface: R = {R:.6f} (Fresnel {r_fresnel:.6f})  OK")


def test_quarter_wave_layer() -> None:
    """A quarter-wave layer of index n on a substrate n_s: analytic reflectance.

    For an incident medium n0, a single quarter-wave layer of index n and a
    substrate n_s the input admittance is n^2/n_s, hence
        R = ((n0 - n^2/n_s)/(n0 + n^2/n_s))^2 .
    """
    n_layer = 2.0
    n_sub = 1.5
    lam = 600.0
    d = lam / (4.0 * n_layer)
    stack = ThinFilmStack(("H",), n_h=n_layer, n_l=n_layer, n_sub=n_sub)
    R = stack.reflectance(np.array([d]), np.array([lam]))[0]
    Y = n_layer**2 / n_sub
    R_analytic = ((cfg.N_INC - Y) / (cfg.N_INC + Y)) ** 2
    assert abs(R - R_analytic) < 1e-10, (R, R_analytic)
    print(f"  quarter-wave layer: R = {R:.6f} (analytic {R_analytic:.6f})  OK")


def test_energy_conservation() -> None:
    """A lossless stack must satisfy 0 <= R <= 1 everywhere."""
    stack = ThinFilmStack(
        cfg.STACK, cfg.N_H, cfg.N_L, cfg.N_S, cfg.N_INC
    )
    rng = np.random.default_rng(12345)
    D = rng.uniform(cfg.D_MIN_NM, cfg.D_MAX_NM, size=(400, cfg.N_LAYERS))
    R = stack.reflectance(D, np.asarray(cfg.WAVELENGTHS_NM))
    assert R.shape == (400, cfg.N_WAVELENGTHS)
    assert np.all(np.isfinite(R))
    assert R.min() >= -1e-12 and R.max() <= 1.0 + 1e-12
    print(f"  400 random stacks x 41 wavelengths: R in [{R.min():.4f}, {R.max():.4f}]  OK")


def test_batch_equals_single() -> None:
    """Batched evaluation must agree with one-at-a-time evaluation."""
    stack = ThinFilmStack(cfg.STACK, cfg.N_H, cfg.N_L, cfg.N_S, cfg.N_INC)
    lam = np.asarray(cfg.WAVELENGTHS_NM)
    rng = np.random.default_rng(7)
    D = rng.uniform(cfg.D_MIN_NM, cfg.D_MAX_NM, size=(5, cfg.N_LAYERS))
    R_batch = stack.reflectance(D, lam)
    for i in range(len(D)):
        R_one = stack.reflectance(D[i], lam)
        assert np.allclose(R_batch[i], R_one, atol=1e-13)
    print("  batch == single-evaluation for 5 designs  OK")


def test_zero_thickness_stack_is_bare_substrate() -> None:
    """All layers 0 nm -> bare substrate reflectance."""
    stack = ThinFilmStack(cfg.STACK, cfg.N_H, cfg.N_L, cfg.N_S, cfg.N_INC)
    R = stack.reflectance(np.zeros(cfg.N_LAYERS), np.array([500.0, 700.0]))
    expected = ((cfg.N_INC - cfg.N_S) / (cfg.N_INC + cfg.N_S)) ** 2
    assert np.allclose(R, expected, atol=1e-12)
    print(f"  zero-thickness stack -> bare substrate R = {expected:.6f}  OK")


def test_free_function_matches_class() -> None:
    stack = ThinFilmStack(cfg.STACK, cfg.N_H, cfg.N_L, cfg.N_S, cfg.N_INC)
    lam = np.asarray(cfg.WAVELENGTHS_NM)
    d = np.array([90.0, 130.0, 60.0, 170.0])
    a = stack.reflectance(d, lam)
    b = reflectance(d, lam, stack.n_layers, cfg.N_INC, cfg.N_S)
    assert np.allclose(a, b, atol=1e-14)
    print("  free function == class wrapper  OK")


if __name__ == "__main__":
    print("TMM unit checks")
    test_single_interface_matches_fresnel()
    test_quarter_wave_layer()
    test_zero_thickness_stack_is_bare_substrate()
    test_energy_conservation()
    test_batch_equals_single()
    test_free_function_matches_class()
    print("all TMM checks passed")
