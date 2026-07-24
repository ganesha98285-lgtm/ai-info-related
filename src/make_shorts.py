"""Step 5 — Cut 3-4 vertical (9:16) teaser Shorts from the master vlog.

Each short is a highlight window (~30s) center-cropped to 1080x1920 for
YouTube Shorts / Instagram Reels / Facebook Reels, with a hook caption.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from config import settings

SHORT_W, SHORT_H = 1080, 1920
SHORT_LEN = 30  # seconds per teaser


def _run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{res.stderr[-600:]}")


def _duration(path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


def _highlight_windows(total: float, count: int) -> list[float]:
    """Evenly spaced start points across the video (skip the very ends)."""
    if total <= SHORT_LEN:
        return [0.0]
    usable = total - SHORT_LEN
    step = usable / max(count - 1, 1) if count > 1 else 0
    return [round(min(i * step, usable), 2) for i in range(count)]


def make_shorts(storyboard_path: Path, count: int = 4) -> list[Path]:
    date_dir = Path(storyboard_path).parent
    master = date_dir / "vlog_master.mp4"
    if not master.exists():
        raise RuntimeError("vlog_master.mp4 missing. Run assemble first.")

    storyboard = json.loads(Path(storyboard_path).read_text("utf-8"))
    title = storyboard.get("title", "John & Ketty")

    shorts_dir = date_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    total = _duration(master)
    starts = _highlight_windows(total, count)
    hooks = ["Wait for it 🐶", "So cute 🥺", "ASMR vibes ✨", "Full vlog on channel 💛"]

    outputs: list[Path] = []
    for i, start in enumerate(starts):
        hook = hooks[i % len(hooks)].replace(":", "\\:").replace("'", "")
        out = shorts_dir / f"short_{i+1:02d}.mp4"
        vf = (
            # crop center to 9:16 then scale to 1080x1920, add hook caption on top
            f"crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale={SHORT_W}:{SHORT_H},"
            f"drawtext=text='{hook}':fontcolor=white:fontsize=64:box=1:"
            f"boxcolor=black@0.4:boxborderw=22:x=(w-text_w)/2:y=140"
        )
        _run([
            "ffmpeg", "-y", "-ss", str(start), "-i", str(master),
            "-t", str(SHORT_LEN), "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-r", "25", str(out),
        ])
        outputs.append(out)
        print(f"[make_shorts] short {i+1} @ {start}s -> {out.name}")

    (shorts_dir / "shorts_manifest.json").write_text(
        json.dumps(
            {"title": title, "shorts": [str(o) for o in outputs]},
            indent=2, ensure_ascii=False,
        ),
        "utf-8",
    )
    return outputs


if __name__ == "__main__":
    import datetime as _dt
    import sys

    sb = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        settings.output_dir / _dt.date.today().isoformat() / "storyboard.json"
    )
    make_shorts(sb)
