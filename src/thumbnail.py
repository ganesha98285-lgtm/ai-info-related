"""Viral thumbnail + channel banner generator (FFmpeg only, no GPU).

* Thumbnail (1280x720): a real frame grabbed from the short, darkened, with a
  huge bold hook in yellow + the brand handle. High-contrast, mobile-readable.
* Banner (2048x1152 safe area inside 2560x1440): channel art with the name,
  tagline and posting promise.

Thumbnails are set on the uploaded video via the YouTube API. The banner is
generated once as a file for you to upload in YouTube Studio.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from src import captions

THUMB_W, THUMB_H = 1280, 720
BANNER_W, BANNER_H = 2560, 1440


def _run(cmd: list[str], what: str) -> bool:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[thumb] {what} failed: {res.stderr[-300:]}")
        return False
    return True


# Thumbnail variety: no two thumbnails on the channel should look the same.
# LAYOUTS control where/how the hook sits; PALETTES control the colours. The
# source frame is also grabbed at a different timestamp each time, so even the
# same layout+palette pair never produces a visually identical image.
# 6 layouts x 8 palettes = 48 distinct looks, tracked in content/history.json.
LAYOUTS = [
    # (band_y, band_h, text_y, fontsize, x_expr)
    (0.60, 0.40, 0.63, 104, "(w-text_w)/2"),   # classic bottom, centred
    (0.00, 0.34, 0.05, 100, "(w-text_w)/2"),   # top band, centred
    (0.62, 0.38, 0.66, 96, "60"),              # bottom band, left aligned
    (0.30, 0.40, 0.36, 108, "(w-text_w)/2"),   # centre band
    (0.55, 0.45, 0.58, 88, "w-text_w-60"),     # bottom band, right aligned
    (0.66, 0.34, 0.70, 118, "(w-text_w)/2"),   # low band, extra large
]

PALETTES = [
    # (text colour, band colour+alpha, border colour, brightness, saturation)
    ("yellow", "black@0.55", "black", -0.06, 1.25),
    ("white", "0x0B1220@0.70", "black", -0.10, 1.15),
    ("0x00E0FF", "black@0.60", "black", -0.08, 1.30),
    ("0xFFD166", "0x1A0B2E@0.65", "black", -0.05, 1.20),
    ("0xFF5A5F", "black@0.50", "white", -0.04, 1.35),
    ("0x7CFFB2", "0x06231A@0.65", "black", -0.09, 1.22),
    ("white", "0xB3000F@0.55", "black", -0.03, 1.28),
    ("0xFFFFFF", "0x123B7A@0.62", "0x001133", -0.07, 1.18),
]


def make_thumbnail(video: Path, hook: str, out: Path,
                   grab_at: float | None = None,
                   style: tuple[int, int] | None = None) -> Path | None:
    """Grab a frame from the short and stamp a big hook on it.

    `style` = (layout index, palette index), normally supplied by
    src.history.next_thumb_style() so the least-used look is chosen every time.
    `grab_at` defaults to a rotating timestamp so the background frame differs.
    """
    work = out.parent
    work.mkdir(parents=True, exist_ok=True)

    layout_i, palette_i = style if style else (0, 0)
    band_y, band_h, text_y, fsize, x_expr = LAYOUTS[layout_i % len(LAYOUTS)]
    fg, band, border, bright, sat = PALETTES[palette_i % len(PALETTES)]

    if grab_at is None:
        # Rotate the grabbed frame so the background is never the same shot.
        grab_at = 1.0 + 0.9 * ((layout_i * len(PALETTES) + palette_i) % 7)

    top = captions.wrap(hook or "WATCH THIS", width=16).upper()
    top_tf = captions.write_text(work, "thumb_top.txt", top)
    brand_tf = captions.write_text(work, "thumb_brand.txt", captions.BRAND)
    f = captions.font_opt()

    vf = (
        # fill 16:9 from the vertical video, keep the subject centred
        f"scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=increase,"
        f"crop={THUMB_W}:{THUMB_H},eq=brightness={bright}:saturation={sat},"
        # contrast band behind the text
        f"drawbox=x=0:y=ih*{band_y}:w=iw:h=ih*{band_h}:color={band}:t=fill,"
        f"drawtext=textfile={top_tf}{f}:fontcolor={fg}:fontsize={fsize}:"
        f"line_spacing=12:borderw=8:bordercolor={border}:"
        f"x={x_expr}:y=h*{text_y},"
        f"drawtext=textfile={brand_tf}{f}:fontcolor=white:fontsize=44:"
        f"box=1:boxcolor=black@0.5:boxborderw=16:x=w-text_w-40:y=40"
    )
    ok = _run(
        ["ffmpeg", "-y", "-ss", f"{grab_at:.2f}", "-i", str(video),
         "-vframes", "1", "-vf", vf, "-q:v", "2", str(out)],
        "thumbnail",
    )
    if not ok or not out.exists():
        return None
    print(f"[thumb] thumbnail -> {out.name} "
          f"(layout {layout_i}, palette {palette_i}, frame @{grab_at:.1f}s, "
          f"{out.stat().st_size/1000:.0f} KB)")
    return out


def make_banner(out: Path, channel: str = "AI TOOL DROP",
                tagline: str = "New AI tools, tips & hacks - every single day") -> Path | None:
    """Generate channel art (banner). Upload it once in YouTube Studio."""
    work = out.parent
    work.mkdir(parents=True, exist_ok=True)
    name_tf = captions.write_text(work, "banner_name.txt", captions.sanitize(channel).upper())
    tag_tf = captions.write_text(work, "banner_tag.txt", captions.sanitize(tagline))
    sub_tf = captions.write_text(work, "banner_sub.txt", "SUBSCRIBE FOR DAILY AI")
    f = captions.font_opt()

    vf = (
        f"drawbox=x=0:y=0:w=iw:h=ih:color=0x0B1220@1:t=fill,"
        # subtle diagonal accent
        f"drawbox=x=0:y=ih*0.72:w=iw:h=ih*0.03:color=0x00E0FF@0.9:t=fill,"
        f"drawtext=textfile={name_tf}{f}:fontcolor=white:fontsize=210:"
        f"borderw=6:bordercolor=black:x=(w-text_w)/2:y=h*0.34,"
        f"drawtext=textfile={tag_tf}{f}:fontcolor=0x9EE7FF:fontsize=80:"
        f"x=(w-text_w)/2:y=h*0.52,"
        f"drawtext=textfile={sub_tf}{f}:fontcolor=yellow:fontsize=64:"
        f"box=1:boxcolor=black@0.35:boxborderw=20:x=(w-text_w)/2:y=h*0.61"
    )
    ok = _run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c=0x0B1220:s={BANNER_W}x{BANNER_H}",
         "-vframes", "1", "-vf", vf, "-q:v", "2", str(out)],
        "banner",
    )
    if not ok or not out.exists():
        return None
    print(f"[thumb] banner -> {out}")
    return out


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        make_thumbnail(Path(sys.argv[1]), "THIS AI TOOL IS INSANE",
                       Path("thumb.jpg"))
    make_banner(Path("banner.jpg"))
