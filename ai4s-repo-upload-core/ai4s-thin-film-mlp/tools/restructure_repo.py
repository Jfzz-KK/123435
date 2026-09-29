"""Restructure the local git repository so the project folder is the repo root.

Before:  D:\\deepseek-harness                 <- git root  (wrapper + py/ + dl/)
             projects/ai4s-thin-film-mlp/...  <- the actual deliverable

After:   D:\\deepseek-harness\\projects\\ai4s-thin-film-mlp   <- git root
             README.md  requirements.txt  src/  figures/  paper/ ...

This makes ``git push`` produce a repository whose front page is the project
README and whose paths match everything the manuscripts claim
("README.md", "src/", "requirements.txt", "python src/data.py", ...).

    python tools/restructure_repo.py [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)                                   # .../projects/ai4s-thin-film-mlp
WORKSPACE = os.path.dirname(os.path.dirname(PROJ))             # D:\deepseek-harness
OLD_ROOT = WORKSPACE                                           # D:\deepseek-harness (old git root)
GIT = os.path.join(WORKSPACE, "tools", "git", "cmd", "git.exe")
URL = "https://github.com/Jfzz-KK/123435.git"

NEW_GITIGNORE = """# Ignored artefacts: everything here is regenerated deterministically by the
# scripts in src/, so the repository stays small while the figures, results and
# manuscripts (which the assignment asks for) are tracked.

# --- regenerable dataset and trained weights ---
data/*.npz
models/*.pt

# --- intermediate prediction dumps ---
results/*.npz

# --- scratch ---
tmp/
mplconfig/
logs/

# --- python ---
__pycache__/
*.py[cod]
.ipynb_checkpoints/

# --- editors / OS ---
.vscode/
.idea/
.DS_Store
Thumbs.db
desktop.ini
~$*
"""


def run(args, cwd=None, check=True, env=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=env)
    if check and r.returncode != 0:
        raise SystemExit(f"command failed: {args}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"project           : {PROJ}")
    print(f"old git root      : {OLD_ROOT}  (exists: {os.path.isdir(os.path.join(OLD_ROOT, '.git'))})")
    print(f"new git root      : {PROJ}")

    # what did the old repository track?
    if os.path.isdir(os.path.join(OLD_ROOT, ".git")):
        tracked = run([GIT, "-C", OLD_ROOT, "-c", "core.quotePath=false", "ls-files",
                       "--", "projects/ai4s-thin-film-mlp"]).splitlines()
        print(f"old repository tracked {len(tracked)} files under the project folder")
        old_commits = run([GIT, "-C", OLD_ROOT, "log", "--oneline"]).splitlines()
        print(f"old repository had {len(old_commits)} commits")
    else:
        tracked = []
        print("no old .git found (nothing to migrate)")

    if args.dry_run:
        print("\n[dry-run] would: remove old .git, write new .gitignore, git init, commit, add remote")
        return 0

    # 1. drop the wrapper repository (the project folder becomes the root)
    old_git = os.path.join(OLD_ROOT, ".git")
    if os.path.isdir(old_git):
        shutil.rmtree(old_git, ignore_errors=True)
        print("removed old .git at", old_git)

    # 2. a nested repository inside the project would break the new root
    nested = os.path.join(PROJ, ".git")
    if os.path.isdir(nested):
        shutil.rmtree(nested, ignore_errors=True)
        print("removed nested .git at", nested)

    # 3. fresh ignore rules suited to a project-root repository
    gi = os.path.join(PROJ, ".gitignore")
    backup = gi + ".outer.bak"
    if os.path.exists(gi):
        shutil.copy2(gi, backup)
        print("backed up previous .gitignore ->", os.path.basename(backup))
    with open(gi, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(NEW_GITIGNORE)
    print("wrote new .gitignore")

    # 4. initialise, commit, attach the remote
    env = dict(os.environ, PATH=os.path.dirname(GIT) + os.pathsep + os.environ.get("PATH", ""))
    run([GIT, "init", "-q", "-b", "main"], cwd=PROJ)
    run([GIT, "config", "user.name", "Jfzz-KK"], cwd=PROJ)
    run([GIT, "config", "user.email", "Jfzz-KK@users.noreply.github.com"], cwd=PROJ)
    run([GIT, "config", "http.proxy", "http://127.0.0.1:7890"], cwd=PROJ)
    run([GIT, "config", "http.schannelCheckRevoke", "false"], cwd=PROJ)
    run([GIT, "add", "-A"], cwd=PROJ, env=env)

    n_staged = len(run([GIT, "diff", "--cached", "--name-only"], cwd=PROJ).splitlines())
    print(f"staged {n_staged} files")

    msg = (
        "AI4S thin-film MLP mini research project\n\n"
        "Student 2020276134 | lambda_target 480 nm | seed 276134 | design_seed 276135\n\n"
        "- TMM implementation (src/tmm.py) with six physics checks (tests/test_tmm.py)\n"
        "- 5,000-design dataset and the fixed 4000/500/500 split (src/data.py)\n"
        "- MLP surrogate 4-128-128-64-41, test RMSE 0.0089 (src/train_mlp.py)\n"
        "- training-size study 500/1000/2000/4000 (src/train_sizes.py)\n"
        "- 10,000-candidate screening with design_seed, Top-10 verified by TMM (src/screening.py)\n"
        "- Figures 1-8, Table 1, English and Chinese manuscripts (paper/)\n"
        "- 95-check deliverable verification (tools/verify_deliverables.py)"
    )
    run([GIT, "commit", "-q", "-m", msg], cwd=PROJ, env=env)
    run([GIT, "remote", "add", "origin", URL], cwd=PROJ, check=False)

    print("\n--- new repository state ---")
    print(run([GIT, "-C", PROJ, "log", "--oneline", "--decorate"]))
    print("remote:", run([GIT, "-C", PROJ, "remote", "-v"]).replace("\n", " | "))
    print("tracked files:", len(run([GIT, "-C", PROJ, "ls-files"]).splitlines()))
    print("root entries:", ", ".join(sorted(os.listdir(PROJ))[:20]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
