"""Minimal, dependency-free wheel installer.

The DSH file sandbox forbids creating files inside *freshly created* directories,
which breaks pip's build/unpack temp directories.  This script therefore resolves
and installs wheels without pip:

  1. query the JSON API of an index for candidate files,
  2. pick a wheel compatible with the running interpreter / platform,
  3. read ``*.dist-info/METADATA`` of that wheel to discover its dependencies,
  4. repeat breadth-first over the dependency closure (marker-evaluated),
  5. download every wheel and extract it into ``Lib/site-packages``.

Usage
-----
    python tools/wheel_install.py numpy matplotlib torch --cpu-torch
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import sysconfig
import time
import urllib.request
import zipfile

try:  # provided by the `packaging` wheel, which this script installs first
    from packaging.version import Version as _Version
except Exception:  # pragma: no cover
    _Version = None  # type: ignore


def _version_key(s: str):
    """Sortable key for a version string, with or without `packaging`."""
    raw = s.split("+")[0]
    if _Version is not None:
        try:
            return (1, _Version(raw), ())
        except Exception:
            pass
    nums = []
    for part in raw.replace("-", ".").split("."):
        digits = re.match(r"^(\d+)", part)
        nums.append(int(digits.group(1)) if digits else 0)
    return (0, None, tuple(nums))

PYPI = "https://pypi.org/pypi/{name}/json"
PYTORCH_CPU = "https://download.pytorch.org/whl/cpu/{name}/"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _interpreter_tags() -> list[str]:
    """All wheel tags this interpreter can install, most specific first."""
    try:
        from packaging.tags import sys_tags  # type: ignore

        return [str(t) for t in sys_tags()]
    except Exception:
        pass
    # fallback: build the tags we need by hand (cp312, abi3, py3, win_amd64)
    impl = f"cp{sys.version_info.major}{sys.version_info.minor}"
    plat = "win_amd64"
    tags = [
        f"{impl}-{impl}-{plat}",
        f"{impl}-abi3-{plat}",
        f"{impl}-none-{plat}",
        "py3-none-any",
        f"{impl}-none-any",
    ]
    return tags


def _marker_env() -> dict:
    from packaging.markers import default_environment  # type: ignore

    return default_environment()


def _marker_ok(marker: str | None) -> bool:
    if not marker:
        return True
    try:
        from packaging.markers import Marker

        return bool(Marker(marker).evaluate(_marker_env()))
    except Exception:
        # unparsable markers (rare) -> keep the dependency, pip-compatible
        return True


def _parse_requires(raw: str):
    """Yield (name, extras, specifier, marker) for each Requires-Dist line."""
    for line in raw.splitlines():
        if not line.startswith("Requires-Dist:"):
            continue
        body = line.split(":", 1)[1].strip()
        marker = None
        if ";" in body:
            body, marker = body.split(";", 1)
            body, marker = body.strip(), marker.strip()
        spec = ""
        m = re.match(r"^([A-Za-z0-9._-]+)\s*(?:\[([^\]]*)\])?\s*(.*)$", body)
        if not m:
            continue
        name, extras, spec = m.group(1), m.group(2), (m.group(3) or "").strip()
        if not _marker_ok(marker):
            continue
        yield name, extras, spec, marker


def _wheel_metadata(zf: zipfile.ZipFile) -> tuple[str, str, list[str]]:
    """Return (version, requires_dist_blob, provides) from a wheel."""
    meta = None
    for n in zf.namelist():
        if n.endswith(".dist-info/METADATA"):
            meta = n
            break
    if meta is None:
        return "", "", []
    raw = zf.read(meta).decode("utf-8", "replace")
    version = ""
    for line in raw.splitlines():
        if line.startswith("Version:"):
            version = line.split(":", 1)[1].strip()
            break
    return version, raw, []


def _pick_wheel(files: list[dict], tags: list[str]) -> dict | None:
    """Choose the best compatible wheel from a list of index files."""
    tag_rank = {t: i for i, t in enumerate(tags)}
    best, best_rank, best_build = None, 10**9, -1
    for f in files:
        fn = f.get("filename", "")
        if not fn.endswith(".whl"):
            continue
        packagetype = f.get("packagetype")
        if packagetype and packagetype != "bdist_wheel":
            continue
        stem = fn[:-4]
        parts = stem.split("-")
        if len(parts) < 5:
            continue
        build = 0
        if len(parts) >= 6 and parts[-3].isdigit():
            build = int(parts[-3])
        pythons = parts[-3] if build == 0 else parts[-4]
        abis = parts[-2] if build == 0 else parts[-3]
        plats = parts[-1]
        ok = False
        rank = 10**9
        for py in pythons.split("."):
            for abi in abis.split("."):
                for pl in plats.split("."):
                    t = f"{py}-{abi}-{pl}"
                    if t in tag_rank and tag_rank[t] < rank:
                        rank, ok = tag_rank[t], True
        if not ok:
            continue
        if rank < best_rank or (rank == best_rank and build > best_build):
            best, best_rank, best_build = f, rank, build
    return best


def _download(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "wheel_install/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as fh:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)


def _html_index_files(name: str, index: str) -> tuple[str, list[dict]]:
    """Parse a PEP 503 simple index page (used by download.pytorch.org)."""
    url = index.format(name=name)
    req = urllib.request.Request(url, headers={"User-Agent": "wheel_install/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        html = r.read().decode("utf-8", "replace")
    files = []
    for m in re.finditer(r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', html):
        href, label = m.group(1), m.group(2).strip()
        if not label.endswith(".whl"):
            continue
        if any(x in label for x in ("+cu", "+rocm", "+xpu", "+mtia")):
            continue  # accelerated builds live in other sub-indices
        files.append({"filename": label, "url": href, "packagetype": "bdist_wheel"})
    if not files:
        raise RuntimeError(f"no wheels found on index page {url}")
    # newest version first: the wheel filename embeds the version as field 2
    def ver_key(f):
        parts = f["filename"].split("-")
        return _version_key(parts[1] if len(parts) > 1 else "0")

    files.sort(key=ver_key, reverse=True)
    latest = files[0]["filename"].split("-")[1] if files else "unknown"
    return latest, files


def _project_files(name: str, version: str | None, index: str) -> tuple[str, list[dict]]:
    if "pypi.org" in index:
        url = index.format(name=name)
        req = urllib.request.Request(url, headers={"User-Agent": "wheel_install/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        if version:
            rel = data.get("releases", {}).get(version, [])
            return version, rel
        v = data["info"]["version"]
        return v, data.get("releases", {}).get(v, [])
    latest, files = _html_index_files(name, index)
    if version:
        files = [f for f in files if f["filename"].split("-")[1] == version]
    return latest, files


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("packages", nargs="+")
    ap.add_argument("--cpu-torch", action="store_true", help="use download.pytorch.org/whl/cpu")
    ap.add_argument("--cache", default=None, help="wheel cache directory")
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache = args.cache or os.path.join(root, "dl", "wheels")
    os.makedirs(cache, exist_ok=True)
    site = os.path.join(os.path.dirname(sys.executable), "Lib", "site-packages")
    os.makedirs(site, exist_ok=True)

    tags = _interpreter_tags()
    todo = [(p, None) for p in args.packages]
    seen: dict[str, str] = {}
    installed = {
        d.split("-")[0].lower().replace("_", "-")
        for d in os.listdir(site)
        if d.endswith(".dist-info")
    }

    while todo:
        name, version = todo.pop(0)
        key = name.lower().replace("_", "-")
        if key in seen:
            continue
        seen[key] = version or "latest"
        index = PYTORCH_CPU if (args.cpu_torch and key == "torch") else PYPI
        try:
            ver, files = _project_files(key, version, index)
        except Exception as exc:
            print(f"!! cannot resolve {name}: {exc}", flush=True)
            continue
        wheel = _pick_wheel(files, tags)
        if wheel is None:
            print(f"!! no compatible wheel for {name} {ver} (win_amd64/cp312)", flush=True)
            continue
        fn = wheel["filename"]
        path = os.path.join(cache, fn)
        if not os.path.exists(path):
            t0 = time.time()
            _download(wheel["url"], path)
            print(f"   downloaded {fn} ({os.path.getsize(path)/1e6:.1f} MB, "
                  f"{time.time()-t0:.1f}s)", flush=True)
        try:
            with zipfile.ZipFile(path) as zf:
                _, raw, _ = _wheel_metadata(zf)
        except Exception as exc:
            print(f"!! bad wheel {fn}: {exc}", flush=True)
            continue
        if not os.path.exists(os.path.join(site, fn.replace(".whl", ".dist-info"))):
            with zipfile.ZipFile(path) as zf:
                zf.extractall(site)
            print(f"   installed  {key} {ver}", flush=True)
        for dep, extras, spec, _ in _parse_requires(raw):
            if extras:
                continue  # optional extras are not required by this project
            dkey = dep.lower().replace("_", "-")
            if dkey in seen:
                continue
            todo.append((dkey, None))

    print("done; installed:", ", ".join(sorted(seen)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
