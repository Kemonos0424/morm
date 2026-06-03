#!/usr/bin/env python3
"""
MORM ラスタアセット生成（hero-bg / og-image / favicon）
docs/MORM_ASSET_SPEC.md §7 のプロンプトに準拠。

- hero-bg.png 1920x1080 : Gemini で群れ粒子フィールド（文字なし）
- og-image.png 1200x630 : Gemini で粒子背景（文字なし）→ PIL で MORM/タグライン/logo を別レイヤ合成
- favicon-512.png + favicon.ico : SVG マーク(logo)を暗角丸タイルに乗せて cairosvg で書き出し
                                   （小アイコンは AI より決定論レンダの方がシャープ）

実行: source ~/Desktop/Team/.venv-brand/bin/activate
      python scripts/generate_morm_png.py
"""
import io
import os

import cairosvg
import numpy as np
from google import genai
from google.genai import types as gtypes
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "public", "icons")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # 環境変数から注入（ソースに鍵を埋め込まない）
GEMINI_MODEL = "gemini-3.1-flash-image-preview"

# fonts
F_HEAVY = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
F_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
F_JP = "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"

HERO_PROMPT = (
    "Abstract swarm particle field on pure black background, thousands of tiny glowing "
    "dots forming an organic fog-like cloud, density peak slightly upper-center fading to "
    "black at the edges, nebula of electric violet (#8b5cf6) blending into blue (#3b82f6) "
    "and cyan (#00d2ff), a few rare amber (#fbbf24) sparks, soft bloom, depth of field, "
    "no text, no logo, no letters, no words, cinematic, ultra-clean, low contrast in the "
    "center area so UI text stays readable, 16:9."
)

OG_PROMPT = (
    "Dark social card background, deep black-to-indigo (#000 to #0c0c1d) gradient, a swarm "
    "of luminous particles drifting from left into a dense glowing cluster on the right, "
    "electric violet and cyan with subtle amber accents, generous empty dark space on the "
    "left-center, premium web3 aesthetic, soft glow, no text, no letters, no words, no logo, "
    "flat, crisp, wide 16:9 banner."
)


def gemini_image(prompt, ar="16:9"):
    client = genai.Client(api_key=GEMINI_API_KEY)
    cfg = gtypes.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=gtypes.ImageConfig(aspect_ratio=ar),
    )
    resp = client.models.generate_content(model=GEMINI_MODEL, contents=[prompt], config=cfg)
    for part in resp.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            return Image.open(io.BytesIO(part.inline_data.data))
    raise RuntimeError("Gemini returned no image")


def cover_resize(img, w, h):
    img = img.convert("RGB")
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    img = img.resize((round(sw * scale), round(sh * scale)), Image.LANCZOS)
    x = (img.width - w) // 2
    y = (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def left_scrim(img, frac=0.62, strength=200):
    """左側を暗くして文字の可読性を確保（中央低コントラスト維持）。"""
    w, h = img.size
    arr = np.array(img.convert("RGB")).astype(np.float32)
    xx = np.linspace(0, 1, w)[None, :]
    a = np.clip((frac - xx) / frac, 0, 1) ** 1.3 * (strength / 255.0)
    a = np.repeat(a, h, axis=0)[:, :, None]
    arr = arr * (1 - a)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def build_hero():
    print("[D] hero-bg.png 1920x1080 (Gemini)")
    img = gemini_image(HERO_PROMPT, "16:9")
    img = cover_resize(img, 1920, 1080)
    out = os.path.join(ICONS, "hero-bg.png")
    img.save(out, "PNG")
    print(f"   saved {out}  ({os.path.getsize(out)/1024:.0f} KB)")


def build_og():
    print("[D] og-image.png 1200x630 (Gemini bg + PIL text)")
    bg = gemini_image(OG_PROMPT, "16:9")
    base = cover_resize(bg, 1200, 630)
    base = left_scrim(base, frac=0.66, strength=205).convert("RGBA")

    # logo-full（左上）
    tmp = os.path.join(ICONS, "_tmp_logofull.png")
    cairosvg.svg2png(url=os.path.join(ICONS, "logo-full.svg"), write_to=tmp, output_width=360)
    lf = Image.open(tmp).convert("RGBA")
    base.alpha_composite(lf, (84, 86))
    os.remove(tmp)

    d = ImageDraw.Draw(base)
    f_big = ImageFont.truetype(F_HEAVY, 132)
    f_tag = ImageFont.truetype(F_REG, 40)
    f_jp = ImageFont.truetype(F_JP, 36)
    d.text((84, 200), "MORM", font=f_big, fill="#ffffff")
    d.text((88, 372), "The Swarm for Every Frame", font=f_tag, fill="#e2e8f0")
    d.text((90, 432), "すべてのフレームに、群れの力を", font=f_jp, fill=(255, 255, 255, 110))
    # amber アクセントの細線
    d.line([(90, 356), (90 + 470, 356)], fill=(251, 191, 36, 180), width=3)

    for dst in (os.path.join(ICONS, "og-image.png"),):
        base.convert("RGB").save(dst, "PNG")
        print(f"   saved {dst}  ({os.path.getsize(dst)/1024:.0f} KB)")


def build_favicon():
    print("[D] favicon-512.png + favicon.ico (SVG マーク → 暗角丸タイル)")
    # logo マーク（群れ）を 512 タイルに合成した SVG を即席で組む
    mark = open(os.path.join(ICONS, "logo.svg")).read()
    inner = mark.split(">", 1)[1].rsplit("</svg>", 1)[0]  # defs + body
    tile = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" fill="none">'
        '<rect x="0" y="0" width="512" height="512" rx="112" fill="#0c0c1d"/>'
        '<rect x="0" y="0" width="512" height="512" rx="112" fill="none" stroke="#8b5cf6" '
        'stroke-width="4" opacity="0.25"/>'
        f'<g transform="translate(116,116) scale(7.0)">{inner}</g>'
        '</svg>'
    )
    out512 = os.path.join(ICONS, "favicon-512.png")
    cairosvg.svg2png(bytestring=tile.encode(), write_to=out512, output_width=512, output_height=512)
    print(f"   saved {out512}  ({os.path.getsize(out512)/1024:.0f} KB)")

    # マルチ解像度 ico（16/32/48）
    im = Image.open(out512).convert("RGBA")
    ico = os.path.join(ICONS, "favicon.ico")
    im.save(ico, sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"   saved {ico}  ({os.path.getsize(ico)/1024:.1f} KB)")


def run():
    build_favicon()  # ネット不要を先に
    build_hero()
    build_og()
    print("PNG 完了。")


if __name__ == "__main__":
    run()
