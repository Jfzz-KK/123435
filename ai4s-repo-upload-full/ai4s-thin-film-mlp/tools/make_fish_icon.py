"""Draw the "blue chubby fish" icon for the DSH desktop shortcut.

Everything is drawn programmatically with Pillow (4x supersampling), so the icon
is reproducible from this file:

    python tools/make_fish_icon.py

Outputs (into assets/):
    dsh-fish.png     256 px preview (transparent)
    dsh-fish-512.png 512 px preview (transparent)
    dsh-fish.ico     multi-size Windows icon (16/24/32/48/64/128/256)
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")

S = 512
SS = 4
W = S * SS                      # supersampled working size (2048)
K = W / 1000.0                  # design space is 1000 x 1000


def P(x, y):
    """Design coordinates (0..1000) -> supersampled pixels."""
    return (x * K, y * K)


def box(x0, y0, x1, y1):
    return [x0 * K, y0 * K, x1 * K, y1 * K]


def poly(points, fill=None, outline=None, width=0):
    pts = [P(x, y) for x, y in points]
    d = ImageDraw.Draw(layer)
    d.polygon(pts, fill=fill, outline=outline, width=int(width * K))


# DeepSeek-ish blues
DEEP = (10, 56, 138)
MAIN = (40, 118, 255)
LIGHT = (104, 186, 255)
PALE = (183, 226, 255)
BELLY = (233, 246, 255)
LINE = (8, 40, 100)
ROSE = (255, 143, 156)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def gradient(size, top, bottom):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        row = lerp(top, bottom, y / max(size - 1, 1))
        for x in range(size):
            px[x, y] = row
    return img


def layer_new():
    return Image.new("RGBA", (W, W), (0, 0, 0, 0))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    global layer

    canvas = layer_new()

    # ------------------------------------------------------------- tail (left)
    layer = layer_new()
    poly([(232, 500), (60, 300), (150, 470), (60, 700), (232, 560)],
         fill=lerp(MAIN, DEEP, 0.15) + (255,), outline=LINE + (255,), width=6)
    poly([(228, 520), (120, 395), (168, 520)], fill=LIGHT + (255,))
    poly([(228, 540), (120, 660), (168, 540)], fill=PALE + (255,))
    canvas.alpha_composite(layer)

    # -------------------------------------------------------- dorsal fin (top)
    layer = layer_new()
    poly([(430, 210), (560, 40), (655, 235)], fill=LIGHT + (255,), outline=LINE + (255,), width=6)
    canvas.alpha_composite(layer)

    # ---------------------------------------------------- pelvic fin (bottom)
    layer = layer_new()
    poly([(450, 700), (540, 830), (620, 690)], fill=lerp(MAIN, DEEP, 0.3) + (255,),
         outline=LINE + (255,), width=6)
    canvas.alpha_composite(layer)

    # ------------------------------------------------------------------- body
    body_box = box(190, 190, 890, 760)
    body_mask = layer_new()
    ImageDraw.Draw(body_mask).ellipse(body_box, fill=(255, 255, 255, 255))
    mask = body_mask.getchannel("A")

    body = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    body.paste(gradient(W, LIGHT, DEEP), (0, 0), mask)
    canvas.alpha_composite(body)

    # belly highlight (clipped to the body via the mask)
    layer = layer_new()
    ImageDraw.Draw(layer).ellipse(box(250, 470, 800, 745), fill=BELLY + (230,))
    layer = layer.filter(ImageFilter.GaussianBlur(18 * SS))
    clipped = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    clipped.paste(layer, (0, 0), mask)
    canvas.alpha_composite(clipped)

    # top gloss
    layer = layer_new()
    ImageDraw.Draw(layer).ellipse(box(300, 250, 700, 400), fill=(255, 255, 255, 90))
    layer = layer.filter(ImageFilter.GaussianBlur(22 * SS))
    clipped = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    clipped.paste(layer, (0, 0), mask)
    canvas.alpha_composite(clipped)

    # crisp body outline
    layer = layer_new()
    ImageDraw.Draw(layer).ellipse(body_box, outline=LINE + (255,), width=int(9 * K))
    canvas.alpha_composite(layer)

    # ------------------------------------------------------------- gill cover
    layer = layer_new()
    ImageDraw.Draw(layer).arc(box(300, 230, 520, 700), start=290, end=55,
                              fill=LINE + (120,), width=int(6 * K))
    layer = layer.filter(ImageFilter.GaussianBlur(2 * SS))
    canvas.alpha_composite(layer)

    # --------------------------------------------------------- pectoral fin
    layer = layer_new()
    ImageDraw.Draw(layer).ellipse(box(455, 545, 680, 720),
                                  fill=lerp(MAIN, DEEP, 0.22) + (240,),
                                  outline=LINE + (235,), width=int(7 * K))
    ImageDraw.Draw(layer).arc(box(500, 580, 640, 680), start=200, end=340,
                              fill=(255, 255, 255, 140), width=int(5 * K))
    canvas.alpha_composite(layer)

    # ------------------------------------------------------------ scale hints
    layer = layer_new()
    d = ImageDraw.Draw(layer)
    for cx, cy, r in [(600, 330, 78), (700, 420, 78), (700, 560, 78),
                      (600, 640, 78), (510, 470, 68), (510, 600, 68)]:
        d.arc(box(cx - r, cy - r, cx + r, cy + r), start=200, end=340,
              fill=(255, 255, 255, 85), width=int(5 * K))
    canvas.alpha_composite(layer)

    # ------------------------------------------------------------------- face
    layer = layer_new()
    d = ImageDraw.Draw(layer)
    # eye
    d.ellipse(box(690, 350, 800, 470), fill=(255, 255, 255, 255), outline=LINE + (255,),
              width=int(7 * K))
    d.ellipse(box(722, 384, 780, 448), fill=(15, 28, 50, 255))
    d.ellipse(box(730, 392, 748, 412), fill=(255, 255, 255, 240))
    d.ellipse(box(762, 424, 772, 436), fill=(255, 255, 255, 190))
    # cheek blush
    d.ellipse(box(620, 500, 720, 560), fill=ROSE + (110,))
    # smile
    d.arc(box(700, 470, 810, 570), start=10, end=140, fill=LINE + (235,), width=int(7 * K))
    canvas.alpha_composite(layer)

    # --------------------------------------------------------------- bubbles
    layer = layer_new()
    d = ImageDraw.Draw(layer)
    for cx, cy, r, a in [(880, 230, 26, 200), (940, 150, 17, 170), (820, 140, 13, 140)]:
        d.ellipse(box(cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, a),
                  outline=(255, 255, 255, min(a + 55, 255)), width=int(4 * K))
    canvas.alpha_composite(layer)

    icon = canvas.resize((S, S), Image.LANCZOS)

    # rounded tile version for small sizes (keeps the fish readable at 16 px)
    tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.20),
                                           fill=(243, 249, 255, 255))
    inner = icon.resize((int(S * 0.92), int(S * 0.92)), Image.LANCZOS)
    tile.alpha_composite(inner, (int(S * 0.04), int(S * 0.04)))

    png256 = os.path.join(OUT, "dsh-fish.png")
    png512 = os.path.join(OUT, "dsh-fish-512.png")
    ico = os.path.join(OUT, "dsh-fish.ico")
    icon.resize((256, 256), Image.LANCZOS).save(png256)
    icon.save(png512)
    tile.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                          (64, 64), (128, 128), (256, 256)])

    for p in (png256, png512, ico):
        print(f"wrote {os.path.relpath(p, ROOT)} ({os.path.getsize(p)} bytes)")


if __name__ == "__main__":
    main()
