"""Tidy the project-root repository: drop stray files, fix UTF-8 names, recommit."""

from __future__ import annotations

import os
import shutil
import subprocess

PROJ = r"D:\deepseek-harness\projects\ai4s-thin-film-mlp"
GIT = r"D:\deepseek-harness\tools\git\cmd\git.exe"


def run(args, cwd=PROJ, check=True):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise SystemExit(f"failed: {args}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def main() -> None:
    # 1. stray files / folders that do not belong to the deliverable
    strays = [
        os.path.join(PROJ, "default-workspace"),          # accidental, holds an old upload zip
        os.path.join(PROJ, ".gitignore.outer.bak"),       # backup of the previous gitignore
        os.path.join(PROJ, "paper", "~$4S_Research_Article_2020276134.docx"),  # Word lock file
    ]
    for s in strays:
        if os.path.isdir(s):
            shutil.rmtree(s, ignore_errors=True)
            print("removed dir ", s)
        elif os.path.exists(s):
            os.remove(s)
            print("removed file", s)

    # 2. keep the Word lock file out of the repository for good
    gi = os.path.join(PROJ, ".gitignore")
    text = open(gi, encoding="utf-8").read()
    if "~$*" not in text:
        text = text.rstrip() + "\n~$*\n"
        open(gi, "w", encoding="utf-8", newline="\n").write(text)
        print("added ~$* to .gitignore")

    # 3. UTF-8 filenames must not be escaped (they were, hence the stray quotes)
    run([GIT, "config", "core.quotePath", "false"])
    run([GIT, "config", "i18n.commitEncoding", "utf-8"])
    run([GIT, "config", "i18n.logOutputEncoding", "utf-8"])
    print("configured core.quotePath=false, i18n utf-8")

    # 4. rebuild the single commit
    if os.path.isdir(os.path.join(PROJ, ".git")):
        shutil.rmtree(os.path.join(PROJ, ".git"), ignore_errors=True)
        print("cleared the previous .git")
    run([GIT, "init", "-q", "-b", "main"])
    run([GIT, "config", "user.name", "Jfzz-KK"])
    run([GIT, "config", "user.email", "Jfzz-KK@users.noreply.github.com"])
    run([GIT, "config", "http.proxy", "http://127.0.0.1:7890"])
    run([GIT, "config", "http.schannelCheckRevoke", "false"])
    run([GIT, "config", "core.quotePath", "false"])
    run([GIT, "add", "-A"])

    files = run([GIT, "diff", "--cached", "--name-only"]).splitlines()
    print(f"staged {len(files)} files")
    bad = [f for f in files if f.startswith('"')]
    print("escaped names:", bad if bad else "none")

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
    run([GIT, "commit", "-q", "-m", msg])
    run([GIT, "remote", "add", "origin", "https://github.com/Jfzz-KK/123435.git"], check=False)

    print("\n--- final repository ---")
    print(run([GIT, "log", "--oneline", "--decorate"]))
    print("tracked:", len(run([GIT, "ls-files"]).splitlines()), "files")
    print("root entries:", ", ".join(sorted(os.listdir(PROJ))))
    print("\n--- tracked top-level groups ---")
    groups: dict[str, int] = {}
    for f in run([GIT, "ls-files"]).splitlines():
        key = f.split("/")[0] if "/" in f else "(root file)"
        groups[key] = groups.get(key, 0) + 1
    for k in sorted(groups):
        print(f"   {groups[k]:4d}  {k}")
    print("\n--- Chinese-named tracked files (must show as UTF-8) ---")
    for f in run([GIT, "ls-files"]).splitlines():
        if any(ord(c) > 127 for c in f):
            print("   ", f)


if __name__ == "__main__":
    main()
