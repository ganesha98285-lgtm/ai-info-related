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


def make_thumbnail(video: Path, hook: str, out: Path,
                   grab_at: float = 1.5) -> Path | None:
    """Grab a frame from the short and stamp a big hook on it."""
    work = out.parent
    work.mkdir(parents=True, exist_ok=True)

    top = captions.wrap(hook or "WATCH THIS", width=16).upper()
    top_tf = captions.write_text(work, "thumb_top.txt", top)
    brand_tf = captions.write_text(work, "thumb_brand.txt", captions.BRAND)
    f = captions.font_opt()

    vf = (
        # fill 16:9 from the vertical video, blur the sides, keep subject centered
        f"scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=increase,"
        f"crop={THUMB_W}:{THUMB_H},eq=brightness=-0.06:saturation=1.25,"
        # dark band behind the text for contrast
        f"drawbox=x=0:y=ih*0.60:w=iw:h=ih*0.40:color=black@0.55:t=fill,"
        f"drawtext=textfile={top_tf}{f}:fontcolor=yellow:fontsize=104:"
        f"line_spacing=12:borderw=8:bordercolor=black:"
        f"x=(w-text_w)/2:y=h*0.63,"
        f"drawtext=textfile={brand_tf}{f}:fontcolor=white:fontsize=44:"
        f"box=1:boxcolor=black@0.5:boxborderw=16:x=w-text_w-40:y=40"
    )
    ok = _run(
        ["ffmpeg", "-y", "-ss", str(grab_at), "-i", str(video), "-vframes", "1",
         "-vf", vf, "-q:v", "2", str(out)],
        "thumbnail",
    )
    if not ok or not out.exists():
        return None
    print(f"[thumb] thumbnail -> {out} ({out.stat().st_size/1000:.0f} KB)")
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
