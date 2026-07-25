"""On-screen text helpers: speech bubbles (dialogue), hooks, and CTAs.

We render text with FFmpeg drawtext. To avoid missing-glyph "tofu" boxes (the
default fonts don't include emoji), all on-screen text is sanitized to plain
ASCII. Emojis still live in the YouTube title/description where they render.
"""
from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

import os

BRAND = os.getenv("BRAND_HANDLE", "@aitooldrop")
DEFAULT_HOOK = "Watch till the end!"
CTA_TEXT = "FOLLOW  +  SUBSCRIBE"


def sanitize(text: str) -> str:
    if not text:
        return ""
    repl = {"’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-", "…": "..."}
    for k, v in repl.items():
        text = text.replace(k, v)
    text = re.sub(r"[^\x20-\x7E]", "", text)  # drop emoji / non-ASCII
    return re.sub(r"\s+", " ", text).strip()


def wrap(text: str, width: int = 32) -> str:
    s = sanitize(text)
    return "\n".join(textwrap.wrap(s, width=width)) if s else ""


def write_text(dirpath: Path, name: str, text: str) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    p = dirpath / name
    p.write_text(text if text else " ", encoding="utf-8")
    return p


def _font() -> str:
    """Prefer an explicit bold font file (more reliable than fontconfig)."""
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ):
        if os.path.exists(p):
            return f":fontfile='{p}'"
    return ""


def _drawtext(textfile: Path, *, fontsize: int, y: str,
              boxcolor: str = "black@0.6", color: str = "white",
              enable: str | None = None) -> str:
    parts = [
        f"drawtext=textfile={textfile}{_font()}",
        f"fontcolor={color}",
        f"fontsize={fontsize}",
        "line_spacing=10",
        "box=1",
        f"boxcolor={boxcolor}",
        "boxborderw=26",
        "x=(w-text_w)/2",
        f"y={y}",
    ]
    if enable:
        parts.append(f"enable='{enable}'")
    return ":".join(parts)


def dialogue_vf(scene: dict, work_dir: Path) -> str:
    """drawtext chain for a scene: speech bubble (speaker + line) + brand handle."""
    speaker = sanitize(scene.get("speaker") or "")
    line = scene.get("narration") or scene.get("caption") or ""
    big = bool(scene.get("hook") or scene.get("cta"))
    label = f"{speaker}: " if speaker and speaker.lower() != "narrator" else ""
    text = wrap(f"{label}{line}", width=26 if big else 34)
    tf = write_text(work_dir, f"cap_{int(scene.get('id', 0)):02d}.txt", text)

    bubble = _drawtext(
        tf,
        fontsize=66 if big else 46,
        y="(h-text_h)/2" if big else "h*0.10",
        boxcolor="black@0.65" if big else "black@0.55",
    )
    brand_tf = write_text(work_dir, "brand.txt", BRAND)
    brand = _drawtext(brand_tf, fontsize=34, y="h-90", boxcolor="black@0.35")
    return bubble + "," + brand


def overlay_on_file(clip_path: Path, scene: dict, work_dir: Path) -> None:
    """Burn the dialogue bubble onto an existing clip (used by the LTX backend)."""
    vf = dialogue_vf(scene, work_dir)
    tmp = clip_path.with_suffix(".cap.mp4")
    try:
        res = subprocess.run(
            ["ffmpeg", "-y", "-i", str(clip_path), "-vf", vf,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", str(tmp)],
            capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired:
        print("[captions] overlay timed out; keeping clip without bubble.")
        return
    if res.returncode == 0:
        tmp.replace(clip_path)
    else:
        print(f"[captions] overlay failed: {res.stderr[-300:]}")


def shorts_hook_cta_vf(work_dir: Path, hook: str, short_len: int, uid: str = "") -> str:
    """Hook in the first 3s (retention) + LIKE/SUBSCRIBE CTA in the last 3s."""
    hook_tf = write_text(work_dir, f"hook_{uid}.txt", wrap(hook or DEFAULT_HOOK, 24))
    cta_tf = write_text(work_dir, f"cta_{uid}.txt", CTA_TEXT)
    brand_tf = write_text(work_dir, f"brand_{uid}.txt", BRAND)
    hook_dt = _drawtext(
        hook_tf, fontsize=84, y="h*0.10", color="yellow", boxcolor="black@0.6",
        enable="lt(t,3)",
    )
    cta_dt = _drawtext(
        cta_tf, fontsize=78, y="h*0.16", color="yellow", boxcolor="black@0.65",
        enable=f"gt(t,{max(short_len - 3, 1)})",
    )
    brand_dt = _drawtext(brand_tf, fontsize=40, y="h-110", boxcolor="black@0.35")
    return hook_dt + "," + cta_dt + "," + brand_dt
