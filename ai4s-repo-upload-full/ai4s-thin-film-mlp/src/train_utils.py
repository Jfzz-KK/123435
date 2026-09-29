"""MLP surrogate model and its training loop.

Architecture (fixed by the assignment, section 2.4):

    input  4    layer thicknesses [d1, d2, d3, d4] in nm (standardised)
    hidden 128, 128, 64   ReLU
    output 41   reflectance at the 41 wavelength samples

Loss: mean squared error between predicted and TMM-calculated reflectance.
Because a lossless stack always satisfies 0 <= R <= 1, the output layer is a
sigmoid, i.e. the network is physically bounded.  Optimiser: Adam, lr = 1e-3,
batch size 64, minibatches shuffled with a seeded generator so that repeated
runs give bit-identical results on CPU.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg  # noqa: E402
import runtime  # noqa: E402

# Scaling constants for the inputs (fixed numbers, not fitted statistics, so
# that the mapping does not depend on which subset is used for training).
D_MEAN = (cfg.D_MIN_NM + cfg.D_MAX_NM) / 2.0
D_HALF = (cfg.D_MAX_NM - cfg.D_MIN_NM) / 2.0


def standardise_thickness(d: np.ndarray) -> np.ndarray:
    return (np.asarray(d, dtype=np.float32) - D_MEAN) / D_HALF


class MLPSurrogate(nn.Module):
    """Fully connected surrogate: thickness vector -> reflectance spectrum."""

    def __init__(
        self,
        n_inputs: int = cfg.N_LAYERS,
        n_outputs: int = cfg.N_WAVELENGTHS,
        hidden_sizes: tuple[int, ...] = cfg.HIDDEN_SIZES,
        seed: int = cfg.SEED,
    ) -> None:
        super().__init__()
        gen = torch.Generator().manual_seed(int(seed))
        layers: list[nn.Module] = []
        prev = n_inputs
        for h in hidden_sizes:
            lin = nn.Linear(prev, h)
            with torch.no_grad():
                # He initialisation drawn from the seeded generator
                bound = float(np.sqrt(2.0 / prev))
                lin.weight.copy_(torch.empty(h, prev).uniform_(-bound, bound, generator=gen))
                lin.bias.copy_(torch.zeros(h))
            layers += [lin, nn.ReLU()]
            prev = h
        out = nn.Linear(prev, n_outputs)
        with torch.no_grad():
            bound = float(np.sqrt(1.0 / prev))
            out.weight.copy_(torch.empty(n_outputs, prev).uniform_(-bound, bound, generator=gen))
            out.bias.copy_(torch.zeros(n_outputs))
        layers += [out, nn.Sigmoid()]
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

    @property
    def n_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


@dataclass
class TrainResult:
    model: MLPSurrogate
    train_loss: list[float] = field(default_factory=list)
    val_loss: list[float] = field(default_factory=list)
    best_epoch: int = 0
    best_val_loss: float = float("nan")
    state_at_best: dict | None = None
    seconds: float = 0.0
    n_train: int = 0
    n_parameters: int = 0


def train_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    seed: int = cfg.SEED,
    n_epochs: int = cfg.N_EPOCHS,
    batch_size: int = cfg.BATCH_SIZE,
    lr: float = cfg.LEARNING_RATE,
    hidden_sizes: tuple[int, ...] = cfg.HIDDEN_SIZES,
    verbose: bool = True,
    log_every: int = 200,
) -> TrainResult:
    """Train one surrogate and return the model with the best validation loss."""
    runtime.seed_everything(seed)
    torch.set_num_threads(1)

    model = MLPSurrogate(hidden_sizes=hidden_sizes, seed=seed)
    optimiser = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    xt = torch.as_tensor(standardise_thickness(x_train), dtype=torch.float32)
    yt = torch.as_tensor(y_train, dtype=torch.float32)
    xv = torch.as_tensor(standardise_thickness(x_val), dtype=torch.float32)
    yv = torch.as_tensor(y_val, dtype=torch.float32)

    n = xt.shape[0]
    gen = torch.Generator().manual_seed(seed)
    result = TrainResult(model=model, n_train=int(n), n_parameters=model.n_parameters)

    t0 = time.time()
    for epoch in range(1, n_epochs + 1):
        model.train()
        perm = torch.randperm(n, generator=gen)
        running = 0.0
        for start in range(0, n, batch_size):
            idx = perm[start : start + batch_size]
            optimiser.zero_grad(set_to_none=True)
            pred = model(xt[idx])
            loss = loss_fn(pred, yt[idx])
            loss.backward()
            optimiser.step()
            running += float(loss.item()) * idx.numel()
        train_mse = running / n

        model.eval()
        with torch.no_grad():
            val_mse = float(loss_fn(model(xv), yv).item())

        result.train_loss.append(train_mse)
        result.val_loss.append(val_mse)
        if val_mse < result.best_val_loss or np.isnan(result.best_val_loss):
            result.best_val_loss = val_mse
            result.best_epoch = epoch
            result.state_at_best = {k: v.detach().clone() for k, v in model.state_dict().items()}
        if verbose and (epoch == 1 or epoch % log_every == 0 or epoch == n_epochs):
            print(
                f"  epoch {epoch:5d}/{n_epochs}  train MSE {train_mse:.3e}  "
                f"val MSE {val_mse:.3e}"
            )

    if result.state_at_best is not None:
        model.load_state_dict(result.state_at_best)
    model.eval()
    result.seconds = time.time() - t0
    return result


@torch.no_grad()
def predict(model: MLPSurrogate, thickness: np.ndarray, batch: int = 4096) -> np.ndarray:
    """Reflectance spectra predicted for a batch of thickness vectors."""
    model.eval()
    out = []
    for start in range(0, len(thickness), batch):
        chunk = torch.as_tensor(
            standardise_thickness(thickness[start : start + batch]), dtype=torch.float32
        )
        out.append(model(chunk).numpy())
    return np.concatenate(out, axis=0)


def metrics(y_true: np.ndarray, y_pred: np.ndarray, target_index: int = cfg.TARGET_INDEX) -> dict:
    """Error metrics used in the Results section."""
    err = y_pred - y_true
    per_sample = np.mean(err**2, axis=1)
    return {
        "mse": float(np.mean(err**2)),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mae": float(np.mean(np.abs(err))),
        "max_abs_error": float(np.max(np.abs(err))),
        "per_sample_mse_mean": float(np.mean(per_sample)),
        "per_sample_mse_median": float(np.median(per_sample)),
        "per_sample_mse_p95": float(np.percentile(per_sample, 95)),
        "per_sample_mse_max": float(np.max(per_sample)),
        "mse_at_target_wavelength": float(np.mean(err[:, target_index] ** 2)),
        "mae_at_target_wavelength": float(np.mean(np.abs(err[:, target_index]))),
        "per_sample_mse": per_sample,
    }
