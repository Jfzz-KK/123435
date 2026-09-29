"""Main experiment: train the MLP surrogate on the full 4,000-sample training set.

Outputs (all reproducible from ``python src/train_mlp.py``):

    models/mlp_main.pt                 trained weights (best validation epoch)
    results/mlp_main_metrics.json      loss history + error metrics + sample picks
    figures/fig1_workflow.png/.pdf     Figure 1
    figures/fig2_model_and_data.*      Figure 2
    figures/fig3_mlp_architecture.*    Figure 3
    figures/fig4_loss_curve.*          Figure 4
    figures/fig5_prediction_test_samples.*  Figure 5
    figures/fig8_failure_case.*        Figure 8
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg  # noqa: E402
import runtime  # noqa: E402
import viz  # noqa: E402
from data import build_dataset, fingerprint  # noqa: E402
from train_utils import metrics, predict, train_model  # noqa: E402

import torch  # noqa: E402


def pick_representative(per_sample_mse: np.ndarray, n: int = 3) -> list[int]:
    """Three samples with error close to the median, spread over the test set."""
    order = np.argsort(per_sample_mse)
    picks = []
    for frac in (0.35, 0.5, 0.65):
        k = int(round(frac * (len(order) - 1)))
        cand = int(order[k])
        while cand in picks:
            k = (k + 1) % len(order)
            cand = int(order[k])
        picks.append(cand)
    return picks[:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", choices=["en", "zh"],
                    help="label language of the generated figures")
    args = ap.parse_args()
    lang = args.lang

    paths = cfg.paths()
    runtime.seed_everything(cfg.SEED)
    print(cfg.summary())
    data = build_dataset()
    fp = fingerprint(data)
    X, Y = data["thickness"], data["spectra"]
    lam = data["wavelengths_nm"]

    x_train, y_train = X[data["idx_train"]], Y[data["idx_train"]]
    x_val, y_val = X[data["idx_val"]], Y[data["idx_val"]]
    x_test, y_test = X[data["idx_test"]], Y[data["idx_test"]]

    print(f"\ntraining on {len(x_train)} samples ...")
    res = train_model(x_train, y_train, x_val, y_val, seed=cfg.SEED, log_every=500)
    print(f"  finished in {res.seconds:.1f} s, best epoch {res.best_epoch}, "
          f"best val MSE {res.best_val_loss:.4e}, parameters {res.n_parameters}")

    pred_val = predict(res.model, x_val)
    pred_test = predict(res.model, x_test)
    m_val = metrics(y_val, pred_val)
    m_test = metrics(y_test, pred_test)
    per_sample = m_test.pop("per_sample_mse")

    worst = int(np.argmax(per_sample))
    representative = pick_representative(per_sample, 3)
    print(f"  test MSE {m_test['mse']:.4e}  RMSE {m_test['rmse']:.4e}  "
          f"MAE {m_test['mae']:.4e}  max|err| {m_test['max_abs_error']:.4e}")
    print(f"  worst test sample: index {worst}, per-sample MSE {per_sample[worst]:.4e}")

    # ---------------- figures ----------------
    viz.fig1_workflow(lang, paths)
    viz.fig2_model(data, lang, paths)
    viz.fig3_architecture(res.n_parameters, lang, paths)
    viz.fig4_loss(res.train_loss, res.val_loss, res.best_epoch, lang, paths)
    viz.fig5_prediction(y_test, pred_test, lam, x_test, representative, lang, paths)
    viz.fig8_failure(y_test, pred_test, lam, x_test, worst, per_sample, lang, paths)

    # ---------------- persist ----------------
    torch.save(
        {
            "state_dict": res.model.state_dict(),
            "hidden_sizes": list(cfg.HIDDEN_SIZES),
            "n_train": int(len(x_train)),
            "seed": int(cfg.SEED),
            "best_epoch": int(res.best_epoch),
            "best_val_loss": float(res.best_val_loss),
        },
        os.path.join(paths.models, "mlp_main.pt"),
    )
    print("wrote", os.path.relpath(os.path.join(paths.models, "mlp_main.pt"), paths.root))

    np.savez_compressed(
        os.path.join(paths.results, "mlp_main_predictions.npz"),
        idx_test=data["idx_test"],
        y_test=y_test,
        y_pred=pred_test,
        per_sample_mse=per_sample,
        train_loss=np.asarray(res.train_loss),
        val_loss=np.asarray(res.val_loss),
    )

    runtime.dump_json(
        {
            "dataset_fingerprint": fp,
            "config": cfg.as_dict(),
            "n_parameters": int(res.n_parameters),
            "training_seconds": float(res.seconds),
            "best_epoch": int(res.best_epoch),
            "best_val_loss": float(res.best_val_loss),
            "train_loss_final": float(res.train_loss[-1]),
            "val_loss_final": float(res.val_loss[-1]),
            "val_metrics": m_val,
            "test_metrics": m_test,
            "worst_test_sample": {
                "local_index": worst,
                "dataset_index": int(data["idx_test"][worst]),
                "thickness_nm": [float(v) for v in x_test[worst]],
                "per_sample_mse": float(per_sample[worst]),
                "rmse": float(np.sqrt(per_sample[worst])),
                "max_abs_error": float(np.max(np.abs(pred_test[worst] - y_test[worst]))),
            },
            "representative_test_samples": [
                {
                    "local_index": int(r),
                    "dataset_index": int(data["idx_test"][r]),
                    "thickness_nm": [float(v) for v in x_test[r]],
                    "per_sample_mse": float(per_sample[r]),
                }
                for r in representative
            ],
            "environment": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "torch": torch.__version__,
                "threads": int(torch.get_num_threads()),
            },
        },
        os.path.join(paths.results, "mlp_main_metrics.json"),
    )


if __name__ == "__main__":
    main()
