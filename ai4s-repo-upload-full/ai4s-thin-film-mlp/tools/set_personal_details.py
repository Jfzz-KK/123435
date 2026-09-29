#!/usr/bin/env python
"""Fill in the two personal placeholders and rebuild both manuscripts.

    python tools/set_personal_details.py --name "张三" \
        --github https://github.com/zhangsan/ai4s-thin-film-mlp

What it does
------------
1. writes ``STUDENT_NAME`` in ``src/config.py``;
2. replaces ``https://github.com/USERNAME/REPOSITORY`` everywhere it appears
   (both manuscript builders, the README and the traceability document);
3. rebuilds the English and Chinese Word and PDF manuscripts.

Only ``--name`` is required; ``--github`` may be omitted if the repository does
not exist yet (the placeholder then stays in place and is reported).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDER = "https://github.com/USERNAME/REPOSITORY"

PATTERN = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def replace_in(path: str, old: str, new: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    n = text.count(old)
    if not n:
        return 0
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="你的姓名 (student name)")
    ap.add_argument("--github", default=None, help="GitHub repository URL")
    ap.add_argument("--skip-build", action="store_true", help="only edit the sources")
    args = ap.parse_args()

    # 1) student name ---------------------------------------------------------
    cfg_path = os.path.join(ROOT, "src", "config.py")
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = fh.read()
    cfg_new, n_name = re.subn(
        r'STUDENT_NAME = "[^"]*"', f'STUDENT_NAME = "{args.name}"', cfg, count=1
    )
    if n_name != 1:
        print("!! could not find STUDENT_NAME in src/config.py", file=sys.stderr)
        return 1
    with open(cfg_path, "w", encoding="utf-8") as fh:
        fh.write(cfg_new)
    print(f"src/config.py: STUDENT_NAME = {args.name!r}")

    # 2) GitHub URL -----------------------------------------------------------
    urls = [args.github] if args.github else []
    targets = [
        os.path.join(ROOT, "README.md"),
        os.path.join(ROOT, "docs", "requirements_traceability.md"),
        os.path.join(ROOT, "src", "make_paper.py"),
        os.path.join(ROOT, "src", "make_pdf.py"),
        os.path.join(ROOT, "src", "texts_zh.py"),
    ]
    if urls:
        total = 0
        for t in targets:
            k = replace_in(t, PLACEHOLDER, urls[0])
            if k:
                print(f"{os.path.relpath(t, ROOT)}: replaced {k} placeholder(s)")
            total += k
        # also catch a previously substituted URL so the script is idempotent
        for t in targets:
            if os.path.exists(t):
                with open(t, "r", encoding="utf-8") as fh:
                    text = fh.read()
                new = PATTERN.sub(urls[0], text)
                if new != text:
                    with open(t, "w", encoding="utf-8") as fh:
                        fh.write(new)
        print(f"GitHub URL set to {urls[0]} ({total} placeholder(s) replaced)")
    else:
        remaining = sum(
            open(t, encoding="utf-8").read().count(PLACEHOLDER)
            for t in targets if os.path.exists(t)
        )
        print(f"no --github given; {remaining} placeholder(s) still in place: {PLACEHOLDER}")

    if args.skip_build:
        return 0

    # 3) rebuild the four manuscripts ----------------------------------------
    scripts = [
        "src/make_paper.py",      # English Word
        "src/make_pdf.py",        # English PDF
        "src/make_paper_zh.py",   # Chinese Word
        "src/make_pdf_zh.py",     # Chinese PDF
    ]
    for s in scripts:
        print(f"\n--- {s}")
        rc = subprocess.call([sys.executable, os.path.join(ROOT, s)], cwd=ROOT)
        if rc != 0:
            print(f"!! {s} failed with exit code {rc}", file=sys.stderr)
            return rc
    print("\nall manuscripts rebuilt; they now carry the personal details.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
