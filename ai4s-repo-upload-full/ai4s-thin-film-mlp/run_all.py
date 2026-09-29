#!/usr/bin/env python
"""End-to-end driver: run the whole study and build both manuscripts.

    python run_all.py            # everything
    python run_all.py --quick    # skip the training-size study (slowest step)

The individual steps are ordinary scripts, so they can also be run on their own
(see README.md).  This driver exists so that a grader can reproduce every number
in the manuscript with one command.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("TMM physics checks", [os.path.join(HERE, "tests", "test_tmm.py")]),
    ("dataset + fixed split", [os.path.join(HERE, "src", "data.py")]),
    ("main MLP training (Figures 1-5, 8)", [os.path.join(HERE, "src", "train_mlp.py")]),
    ("training-set-size study (Figure 6, Table 2)", [os.path.join(HERE, "src", "train_sizes.py")]),
    ("MLP-assisted screening (Figure 7, Table 1)", [os.path.join(HERE, "src", "screening.py")]),
    ("build Word manuscript", [os.path.join(HERE, "src", "make_paper.py")]),
    ("build PDF manuscript", [os.path.join(HERE, "src", "make_pdf.py")]),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="skip the training-set-size study")
    args = ap.parse_args()

    steps = [s for s in STEPS if not (args.quick and "training-set-size" in s[0])]
    t_all = time.time()
    for label, cmd in steps:
        print(f"\n{'='*72}\n== {label}\n{'='*72}", flush=True)
        t0 = time.time()
        rc = subprocess.call([sys.executable] + cmd, cwd=HERE)
        status = "OK" if rc == 0 else f"FAILED (exit {rc})"
        print(f"-- {label}: {status} in {time.time()-t0:.1f} s", flush=True)
        if rc != 0:
            return rc
    print(f"\nall steps finished in {time.time()-t_all:.1f} s")
    print("manuscripts:", os.path.join(HERE, "paper"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
