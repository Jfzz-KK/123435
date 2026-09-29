"""Transfer-matrix method (TMM) for a plane-wave, normal-incidence dielectric stack.

Physical model used throughout the study (see Methods of the paper):

    incident medium : air              n_inc = 1.00
    stack           : Air / H / L / H / L / Glass   (4 layers)
    substrate       : glass            n_s   = 1.52
    polarisation    : normal incidence, non-magnetic, lossless, non-dispersive

Each layer *i* is described by its optical phase thickness

    delta_i = 2*pi*n_i*d_i / lambda

and its characteristic (transfer) matrix

    M_i = [[ cos(delta_i),         1j*sin(delta_i)/eta_i],
           [ 1j*eta_i*sin(delta_i),          cos(delta_i)  ]]

with the optical admittance at normal incidence ``eta_i = n_i`` (free-space
units, Y0 = 1).  The multilayer matrix is the ordered product

    M = M_1 @ M_2 @ ... @ M_N

and, for the admittance of the substrate ``eta_s``, the input admittance is

    Y = (M[1,0] + M[1,1]*eta_s) / (M[0,0] + M[0,1]*eta_s)

so that the amplitude reflection coefficient and the reflectance read

    r = (eta_inc - Y) / (eta_inc + Y),      R = |r|^2 .

For a *lossless* stack this guarantees 0 <= R <= 1, which is checked in the
unit tests.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

ArrayLike = Sequence[float] | np.ndarray


def layer_indices(stack: Sequence[str], n_h: float, n_l: float) -> np.ndarray:
    """Map a stack description like ("H", "L", "H", "L") to refractive indices."""
    table = {"H": float(n_h), "L": float(n_l)}
    try:
        return np.array([table[s] for s in stack], dtype=float)
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"unknown layer label {exc.args[0]!r}; use 'H' or 'L'") from None


def reflectance(
    thicknesses_nm: ArrayLike,
    wavelengths_nm: ArrayLike,
    n_layers: np.ndarray,
    n_inc: float,
    n_sub: float,
) -> np.ndarray:
    """Reflectance spectra for one or many thickness vectors.

    Parameters
    ----------
    thicknesses_nm
        Either shape ``(L,)`` for a single design or ``(B, L)`` for a batch of
        ``B`` designs, with ``L`` layer thicknesses in nanometres.
    wavelengths_nm
        Shape ``(W,)`` vacuum wavelengths in nanometres.
    n_layers
        Shape ``(L,)`` refractive indices of the layers, ordered from the
        air side to the substrate side.

    Returns
    -------
    np.ndarray
        Reflectance of shape ``(W,)`` for a single design or ``(B, W)`` for a
        batch.
    """
    d = np.atleast_2d(np.asarray(thicknesses_nm, dtype=float))     # (B, L)
    lam = np.asarray(wavelengths_nm, dtype=float)                  # (W,)
    n = np.asarray(n_layers, dtype=float)                          # (L,)

    if d.shape[1] != n.shape[0]:
        raise ValueError(
            f"thickness vector has {d.shape[1]} layers but {n.shape[0]} indices were given"
        )

    B = d.shape[0]
    W = lam.shape[0]

    # delta[b, w, l] = 2*pi*n_l*d[b,l]/lambda_w
    delta = 2.0 * np.pi * d[:, None, :] * n[None, None, :] / lam[None, :, None]

    cos_d = np.cos(delta)
    sin_d = np.sin(delta)
    eta = n[None, None, :]

    # Characteristic matrix of every layer, element-wise: (B, W, L)
    m00 = cos_d.astype(complex)
    m01 = 1j * sin_d / eta
    m10 = 1j * eta * sin_d
    m11 = cos_d.astype(complex)

    # Ordered matrix product M_1 @ M_2 @ ... @ M_N, accumulated step by step.
    M00 = np.ones((B, W), dtype=complex)
    M01 = np.zeros((B, W), dtype=complex)
    M10 = np.zeros((B, W), dtype=complex)
    M11 = np.ones((B, W), dtype=complex)

    for l in range(n.shape[0]):
        a00, a01, a10, a11 = M00, M01, M10, M11
        b00, b01, b10, b11 = m00[:, :, l], m01[:, :, l], m10[:, :, l], m11[:, :, l]
        M00 = a00 * b00 + a01 * b10
        M01 = a00 * b01 + a01 * b11
        M10 = a10 * b00 + a11 * b10
        M11 = a10 * b01 + a11 * b11

    # Input admittance seen from the incident medium.
    Y = (M10 + M11 * n_sub) / (M00 + M01 * n_sub)
    r = (n_inc - Y) / (n_inc + Y)
    R = np.abs(r) ** 2

    # Numerical guard: R must stay inside [0, 1] for a passive lossless stack.
    R = np.clip(R.real, 0.0, 1.0)

    if np.ndim(thicknesses_nm) == 1:
        return R[0]
    return R


class ThinFilmStack:
    """Convenience wrapper holding the fixed optical constants of the study."""

    def __init__(
        self,
        stack: Sequence[str] = ("H", "L", "H", "L"),
        n_h: float = 2.30,
        n_l: float = 1.45,
        n_sub: float = 1.52,
        n_inc: float = 1.0,
    ) -> None:
        self.stack = tuple(stack)
        self.n_h = float(n_h)
        self.n_l = float(n_l)
        self.n_sub = float(n_sub)
        self.n_inc = float(n_inc)
        self.n_layers = layer_indices(self.stack, self.n_h, self.n_l)

    @property
    def n_layers_count(self) -> int:
        return len(self.stack)

    def reflectance(self, thicknesses_nm: ArrayLike, wavelengths_nm: ArrayLike) -> np.ndarray:
        return reflectance(
            thicknesses_nm, wavelengths_nm, self.n_layers, self.n_inc, self.n_sub
        )


if __name__ == "__main__":  # tiny smoke test
    stack = ThinFilmStack()
    lam = np.arange(400.0, 801.0, 10.0)
    d = np.array([100.0, 100.0, 100.0, 100.0])
    R = stack.reflectance(d, lam)
    print("single design ->", R.shape, "R in [%.4f, %.4f]" % (R.min(), R.max()))
    D = np.random.default_rng(0).uniform(40, 180, size=(7, 4))
    Rb = stack.reflectance(D, lam)
    print("batch of 7    ->", Rb.shape)
