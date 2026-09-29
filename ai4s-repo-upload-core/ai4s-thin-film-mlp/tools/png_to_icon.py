"""Convert the DeepSeek kawaii mascot PNG into a Windows icon.

    python tools/png_to_icon.py --src "C:\\Users\\JF\\Desktop\\1.png" --out assets/dsh-mascot.ico

The source image is never modified.  The artwork is trimmed of uniform borders,
padded back to a square with a small margin (so the character does not touch the
icon edge) and resampled into every size Windows asks for.
"""

from __future__ import annotations

import argparse
import os

from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def trim_uniform_border(im: Image.Image, tolerance: int = 12) -> Image.Image:
    """Crop away a uniform (usually white) border."""
    rgb = im.convert("RGB")
    corners = [rgb.getpixel(p) for p in ((0, 0), (rgb.width - 1, 0), (0, rgb.height - 1),
                                         (rgb.width - 1, rgb.height - 1))]
    if len(set(corners)) != 1:
        return im
    bg = Image.new("RGB", rgb.size, corners[0])
    diff = ImageChops.difference(rgb, bg).convert("L").point(lambda v: 255 if v > tolerance else 0)
    bbox = diff.getbbox()
    if not bbox:
        return im
    return im.crop(bbox)


def square_pad(im: Image.Image, margin_frac: float, background) -> Image.Image:
    """Pad to a square canvas with a margin, keeping the artwork centred."""
    w, h = im.size
    side = int(max(w, h) * (1.0 + 2.0 * margin_frac))
    canvas = Image.new("RGBA", (side, side), background)
    canvas.alpha_composite(im.convert("RGBA"), ((side - w) // 2, (side - h) // 2))
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, "assets", "dsh-mascot.ico"))
    ap.add_argument("--preview", default=os.path.join(ROOT, "assets", "dsh-mascot.png"))
    ap.add_argument("--margin", type=float, default=0.05,
                    help="fraction of the artwork size added as padding")
    ap.add_argument("--transparent", action="store_true",
                    help="use a transparent background instead of white")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    if not os.path.exists(src):
        raise SystemExit(f"source image not found: {src}")

    with Image.open(src) as raw:
        im = raw.convert("RGBA")
        print(f"source: {os.path.basename(src)} {raw.size[0]}x{raw.size[1]} {raw.mode}")

        im = trim_uniform_border(im)
        print(f"trimmed: {im.size[0]}x{im.size[1]}")

        background = (0, 0, 0, 0) if args.transparent else (255, 255, 255, 255)
        im = square_pad(im, args.margin, background)
        print(f"padded: {im.size[0]}x{im.size[1]}")

        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        im.resize((256, 256), Image.LANCZOS).save(args.preview)
        im.save(args.out, sizes=SIZES)

    for p in (args.preview, args.out):
        print(f"wrote {os.path.relpath(p, ROOT)} ({os.path.getsize(p)} bytes)")


if __name__ == "__main__":
    main()
