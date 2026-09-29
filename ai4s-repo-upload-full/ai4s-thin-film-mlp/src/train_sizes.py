"""Experiment 3.2 -- how does the test error depend on the training-set size?

The first 500 / 1000 / 2000 / 4000 samples of the *fixed* 4,000-sample training
pool are used; the validation and test sets never change and every other
training setting is identical (seed, architecture, Adam, lr, batch size, epochs).
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
from data import build_dataset  # noqa: E402
from train_utils import MLPSurrogate, metrics, predict, train_model  # noqa: E402

import torch  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", choices=["en", "zh"])
    args = ap.parse_args()
    lang = args.lang

    paths = cfg.paths()
    runtime.seed_everything(cfg.SEED)

    data = build_dataset(verbose=False)
    X, Y = data["thickness"], data["spectra"]
    x_pool, y_pool = X[data["idx_train"]], Y[data["idx_train"]]
    x_val, y_val = X[data["idx_val"]], Y[data["idx_val"]]
    x_test, y_test = X[data["idx_test"]], Y[data["idx_test"]]
    print(f"training pool {len(x_pool)}, validation {len(x_val)}, test {len(x_test)}")

    records = []
    for n in cfg.TRAIN_SIZES:
        print(f"\n=== training with {n} samples ===")
        # identical initialisation for every subset: same seed -> same weights
        res = train_model(x_pool[:n], y_pool[:n], x_val, y_val, seed=cfg.SEED)
        pred_val = predict(res.model, x_val)
        pred_test = predict(res.model, x_test)
        m_val = metrics(y_val, pred_val)
        m_test = metrics(y_test, pred_test)
        m_test.pop("per_sample_mse", None)
        rec = {
            "n_train": int(n),
            "best_epoch": int(res.best_epoch),
            "best_val_loss": float(res.best_val_loss),
            "final_train_loss": float(res.train_loss[-1]),
            "training_seconds": float(res.seconds),
            "val_metrics": m_val,
            "test_metrics": m_test,
        }
        records.append(rec)
        print(f"  -> test MSE {m_test['mse']:.4e}, RMSE {m_test['rmse']:.4e}, "
              f"MAE {m_test['mae']:.4e}, best epoch {res.best_epoch}")

        torch.save(
            {
                "state_dict": res.model.state_dict(),
                "hidden_sizes": list(cfg.HIDDEN_SIZES),
                "n_train": int(n),
                "seed": int(cfg.SEED),
                "best_epoch": int(res.best_epoch),
            },
            os.path.join(paths.models, f"mlp_n{n}.pt"),
        )

    sizes = [r["n_train"] for r in records]
    test_mse = [r["test_metrics"]["mse"] for r in records]
    test_rmse = [r["test_metrics"]["rmse"] for r in records]
    val_mse = [r["val_metrics"]["mse"] for r in records]

    # marginal benefit of each doubling of the training set
    gains = []
    for a, b in zip(records[:-1], records[1:]):
        mse_a = a["test_metrics"]["mse"]
        mse_b = b["test_metrics"]["mse"]
        gains.append(
            {
                "from": a["n_train"],
                "to": b["n_train"],
                "absolute_mse_reduction": float(mse_a - mse_b),
                "relative_mse_reduction_pct": float(100.0 * (mse_a - mse_b) / mse_a),
                "rmse_ratio": float(b["test_metrics"]["rmse"] / a["test_metrics"]["rmse"]),
            }
        )

    viz.fig6_training_size(sizes, test_mse, test_rmse, val_mse, lang, paths)

    lines = ["n_train,val_MSE,test_MSE,test_RMSE,test_MAE,best_epoch,train_seconds"]
    for r in records:
        lines.append(
            f"{r['n_train']},{r['val_metrics']['mse']:.6e},{r['test_metrics']['mse']:.6e},"
            f"{r['test_metrics']['rmse']:.6e},{r['test_metrics']['mae']:.6e},"
            f"{r['best_epoch']},{r['training_seconds']:.1f}"
        )
    csv_path = os.path.join(paths.tables, "training_size_results.csv")
    with open(csv_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote", os.path.relpath(csv_path, paths.root))

    runtime.dump_json(
        {
            "config": cfg.as_dict(),
            "records": records,
            "marginal_gains": gains,
            "environment": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "torch": torch.__version__,
            },
        },
        os.path.join(paths.results, "training_size_study.json"),
    )
    print("\nmarginal gains:")
    for g in gains:
        print(
            f"  {g['from']:>5} -> {g['to']:<5} samples: test MSE "
            f"-{g['absolute_mse_reduction']:.3e} ({g['relative_mse_reduction_pct']:.1f} %), "
            f"RMSE x{g['rmse_ratio']:.3f}"
        )


if __name__ == "__main__":
    main()
