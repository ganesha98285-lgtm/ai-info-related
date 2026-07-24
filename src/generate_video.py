"""Step 3 — Generate a video clip per scene (character-consistent).

Backends (set VIDEO_BACKEND in .env):
  - "stub"   : no GPU needed. Makes a clean animated placeholder clip from the
               reference image (Ken Burns pan/zoom) + caption. Great for building
               and testing the whole pipeline for free with zero setup.
  - "kaggle" : submit scene prompts + reference images to a Kaggle notebook that
               runs LTX-2 (open-source, free GPU) image-to-video, then download
               the rendered clips. (Notebook template documented in docs/kaggle.md)
  - "local"  : call a local LTX-2 / ComfyUI HTTP endpoint if you have a GPU.

Every backend takes the SAME reference images (characters/refs/john.png &
ketty.png) so John & Ketty look identical across scenes.

Output: one mp4 per scene in output/<date>/clips/ ; returns ordered clip paths.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from config import settings

TARGET_W, TARGET_H = 1920, 1080  # HD landscape master; shorts are cropped later


def _has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _pick_reference(scene: dict) -> Path | None:
    """Choose which character reference image best fits a scene (simple heuristic)."""
    john = settings.refs_dir / "john.png"
    ketty = settings.refs_dir / "ketty.png"
    text = f"{scene.get('visual_prompt','')} {scene.get('narration','')}".lower()
    if "ketty" in text and "john" not in text and ketty.exists():
        return ketty
    if john.exists():
        return john
    return ketty if ketty.exists() else None


def _stub_clip(scene: dict, out_path: Path) -> bool:
    """Make a gentle Ken-Burns clip from a reference image + caption overlay.

    Uses only FFmpeg (free, no GPU). If no reference image exists, renders a
    solid pastel card so the pipeline still completes end-to-end.
    """
    seconds = int(scene.get("seconds", 7))
    caption = (scene.get("caption") or "").replace(":", "\\:").replace("'", "")
    ref = _pick_reference(scene)

    drawtext = (
        f"drawtext=text='{caption}':fontcolor=white:fontsize=54:"
        f"box=1:boxcolor=black@0.35:boxborderw=20:x=(w-text_w)/2:y=h-160"
    )

    if ref and ref.exists():
        # Slow zoom (Ken Burns) on the character image.
        vf = (
            f"scale={TARGET_W*1.2:.0f}:-1,"
            f"zoompan=z='min(zoom+0.0006,1.15)':d={seconds*25}:"
            f"s={TARGET_W}x{TARGET_H}:fps=25,"
            f"{drawtext}"
        )
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", str(ref),
            "-t", str(seconds), "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
            str(out_path),
        ]
    else:
        # Pastel placeholder card.
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=0xF6D6C2:s={TARGET_W}x{TARGET_H}:d={seconds}:r=25",
            "-vf", drawtext, "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(out_path),
        ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[generate_video] stub ffmpeg error: {res.stderr[-400:]}")
        return False
    return True


def _kaggle_clips(storyboard: dict, clips_dir: Path) -> list[Path]:
    """Render scenes on Kaggle free GPU via LTX-2.

    This ships the storyboard + reference images to a Kaggle kernel using the
    Kaggle API, triggers a run, and pulls the resulting mp4s. The heavy LTX-2
    code lives in the Kaggle notebook (see docs/kaggle.md) so the free GPU does
    the work, not this machine.
    """
    try:
        from src.backends.kaggle_runner import run_ltx_on_kaggle  # type: ignore

        return run_ltx_on_kaggle(storyboard, settings.refs_dir, clips_dir)
    except Exception as exc:
        print(f"[generate_video] Kaggle backend unavailable ({exc}); using stub.")
        return _render_all_stub(storyboard, clips_dir)


def _local_clips(storyboard: dict, clips_dir: Path) -> list[Path]:
    try:
        from src.backends.local_ltx import run_ltx_local  # type: ignore

        return run_ltx_local(storyboard, settings.refs_dir, clips_dir)
    except Exception as exc:
        print(f"[generate_video] Local backend unavailable ({exc}); using stub.")
        return _render_all_stub(storyboard, clips_dir)


def _render_all_stub(storyboard: dict, clips_dir: Path) -> list[Path]:
    clips: list[Path] = []
    for scene in storyboard.get("scenes", []):
        out = clips_dir / f"scene_{scene['id']:02d}.mp4"
        if _stub_clip(scene, out):
            clips.append(out)
    return clips


def generate_clips(storyboard_path: Path) -> list[Path]:
    if not _has_ffmpeg():
        raise RuntimeError("FFmpeg not found. Install ffmpeg to render clips.")

    storyboard = json.loads(Path(storyboard_path).read_text("utf-8"))
    clips_dir = Path(storyboard_path).parent / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    backend = settings.video_backend.lower()
    print(f"[generate_video] backend = {backend}")
    if backend == "kaggle":
        clips = _kaggle_clips(storyboard, clips_dir)
    elif backend == "local":
        clips = _local_clips(storyboard, clips_dir)
    else:
        clips = _render_all_stub(storyboard, clips_dir)

    manifest = clips_dir / "clips_manifest.json"
    manifest.write_text(
        json.dumps([str(c) for c in clips], indent=2), "utf-8"
    )
    print(f"[generate_video] {len(clips)} clips -> {clips_dir}")
    return clips


if __name__ == "__main__":
    import datetime as _dt
    import sys

    sb = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        settings.output_dir / _dt.date.today().isoformat() / "storyboard.json"
    )
    generate_clips(sb)
