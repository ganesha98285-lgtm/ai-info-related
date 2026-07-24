"""Local LTX-2 / ComfyUI backend (only if you have a GPU).

Talks to a local HTTP endpoint (e.g. a ComfyUI or LTX server) that accepts a
prompt + reference image and returns an mp4. Configure LTX_LOCAL_URL.
Raises if unavailable so generate_video.py falls back to the stub backend.
"""
from __future__ import annotations

import os
from pathlib import Path


def run_ltx_local(storyboard: dict, refs_dir: Path, clips_dir: Path) -> list[Path]:
    url = os.getenv("LTX_LOCAL_URL")
    if not url:
        raise RuntimeError("LTX_LOCAL_URL not set")

    import requests

    clips: list[Path] = []
    for scene in storyboard.get("scenes", []):
        sid = scene["id"]
        ref_name = "katie.png" if "katie" in scene.get("visual_prompt", "").lower() else "jon.png"
        ref = refs_dir / ref_name
        files = {"image": ref.open("rb")} if ref.exists() else {}
        data = {
            "prompt": scene.get("visual_prompt", ""),
            "seconds": scene.get("seconds", 7),
            "width": 1920,
            "height": 1080,
        }
        resp = requests.post(f"{url}/generate", data=data, files=files, timeout=600)
        resp.raise_for_status()
        out = clips_dir / f"scene_{sid:02d}.mp4"
        out.write_bytes(resp.content)
        clips.append(out)
    if not clips:
        raise RuntimeError("Local LTX produced no clips")
    return clips
