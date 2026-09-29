"""Build the manual-upload archives for the GitHub repository.

The project folder *is* the git root now, so the archives contain the repository
exactly as ``git push`` would produce it.

  core  -- the files tracked by git (source, README, manuscripts, figures,
           results, templates, tools).
  full  -- core plus the regenerable artefacts that are intentionally ignored by
           git (the dataset and the trained weights), for a repository that can
           be verified immediately after download.

GitHub's web uploader does **not** unpack zip files, so these archives are meant
to be *extracted* and the resulting folder dragged into the upload page (or use
"Add file -> Upload files" with the folder).

    python tools/make_upload_zip.py
"""

from __future__ import annotations

import os
import subprocess
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)                                    # repository root
WORKSPACE = os.path.dirname(os.path.dirname(PROJ))              # D:\deepseek-harness
GIT = os.path.join(WORKSPACE, "tools", "git", "cmd", "git.exe")
OUT_DIR = os.path.join(WORKSPACE, "default-workspace", "AI4S_提交物")
PREFIX = os.path.basename(PROJ)                                 # ai4s-thin-film-mlp

IGNORED_BUT_WANTED = ("data/dataset.npz", "models/mlp_main.pt",
                      "models/mlp_n500.pt", "models/mlp_n1000.pt",
                      "models/mlp_n2000.pt", "models/mlp_n4000.pt")


def run(args: list[str]) -> str:
    return subprocess.run([GIT] + args, cwd=PROJ, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    core = [f for f in run(["ls-files"]).splitlines() if f.strip()]
    extra = [f for f in IGNORED_BUT_WANTED if os.path.exists(os.path.join(PROJ, f))]
    full = sorted(set(core) | set(extra))

    for name, rels in (("ai4s-repo-upload-core.zip", core),
                       ("ai4s-repo-upload-full.zip", full)):
        path = os.path.join(OUT_DIR, name)
        raw = 0
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for rel in rels:
                src = os.path.join(PROJ, rel.replace("/", os.sep))
                if not os.path.exists(src):
                    print("   missing, skipped:", rel)
                    continue
                z.write(src, f"{PREFIX}/{rel}")
                raw += os.path.getsize(src)
        with zipfile.ZipFile(path) as z:
            ok = z.testzip() is None
            entries = z.namelist()
        print(f"{name}: {len(entries)} entries, {raw/1024/1024:.2f} MB raw -> "
              f"{os.path.getsize(path)/1024/1024:.2f} MB zip, integrity {'OK' if ok else 'BAD'}")
        print("   ", path)
        tops: dict[str, int] = {}
        for n in entries:
            key = n.split("/")[1] if len(n.split("/")) > 1 else "(file)"
            if key.endswith(".md") or key.endswith(".txt") or key.endswith(".py"):
                key = "(top-level files)"
            tops[key] = tops.get(key, 0) + 1
        print("    ", ", ".join(f"{k}:{v}" for k, v in sorted(tops.items())))


if __name__ == "__main__":
    main()
