"""Kaggle free-GPU backend: render scene clips with LTX-2 (open source).

How it works (free):
  1. We write the storyboard + reference images into a Kaggle *dataset*.
  2. We push/trigger a Kaggle *kernel* (notebook) that installs LTX-2 and does
     image-to-video for each scene on Kaggle's free GPU (~30h/week).
  3. When the kernel finishes, we pull its output (the rendered mp4s) back here.

This module orchestrates that via the official `kaggle` CLI/API. The heavy
LTX-2 notebook itself lives in `kaggle/ltx_render_kernel.ipynb` (see docs/kaggle.md).

If the Kaggle API isn't configured, we raise so generate_video.py can fall back
to the free `stub` backend and keep the pipeline unblocked.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

KERNEL_SLUG_ENV = "KAGGLE_KERNEL_SLUG"  # e.g. "youruser/ltx-render-kernel"


def _require_kaggle() -> None:
    if not (os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY")):
        raise RuntimeError("KAGGLE_USERNAME/KAGGLE_KEY not set")
    if shutil.which("kaggle") is None:
        raise RuntimeError("kaggle CLI not installed (pip install kaggle)")


def _push_inputs(storyboard: dict, refs_dir: Path, staging: Path) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "storyboard.json").write_text(
        json.dumps(storyboard, ensure_ascii=False), "utf-8"
    )
    for name in ("john.png", "ketty.png"):
        src = refs_dir / name
        if src.exists():
            shutil.copy(src, staging / name)


def run_ltx_on_kaggle(storyboard: dict, refs_dir: Path, clips_dir: Path) -> list[Path]:
    _require_kaggle()
    kernel = os.getenv(KERNEL_SLUG_ENV)
    if not kernel:
        raise RuntimeError(f"{KERNEL_SLUG_ENV} not set")

    staging = clips_dir / "_kaggle_in"
    _push_inputs(storyboard, refs_dir, staging)

    # Trigger the kernel run (kernel reads the attached dataset & renders clips).
    subprocess.run(["kaggle", "kernels", "push", "-p", str(staging)], check=True)

    # Poll for completion, then download outputs.
    out = clips_dir / "_kaggle_out"
    out.mkdir(parents=True, exist_ok=True)
    for _ in range(60):  # up to ~30 min
        status = subprocess.run(
            ["kaggle", "kernels", "status", kernel],
            capture_output=True, text=True,
        ).stdout.lower()
        if "complete" in status:
            break
        if "error" in status:
            raise RuntimeError(f"Kaggle kernel errored: {status}")
        time.sleep(30)

    subprocess.run(
        ["kaggle", "kernels", "output", kernel, "-p", str(out)], check=True
    )

    clips = sorted(out.glob("scene_*.mp4"))
    # move into clips_dir with canonical names
    final: list[Path] = []
    for c in clips:
        dest = clips_dir / c.name
        shutil.move(str(c), dest)
        final.append(dest)
    if not final:
        raise RuntimeError("Kaggle produced no clips")
    return final
