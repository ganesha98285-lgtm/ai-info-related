"""Client for the Modal GPU video generator (see modal_app.py).

Used as *premium* b-roll: when enabled, scenes are generated on a real GPU
(Modal free tier = $30/month credits) instead of being pulled from stock.
Any failure falls back to stock footage, so a run never breaks because of this.

Enable with:
    AI_BROLL=true
    MODAL_TOKEN_ID / MODAL_TOKEN_SECRET   (GitHub secrets)
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "ai-shorts-video"
FN_NAME = "generate_clip"


def available() -> bool:
    if os.getenv("AI_BROLL", "false").lower() != "true":
        return False
    if not (os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET")):
        return False
    try:
        import modal  # noqa: F401

        return True
    except Exception:
        return False


def _lookup():
    import modal

    # modal >= 1.0
    if hasattr(modal.Function, "from_name"):
        return modal.Function.from_name(APP_NAME, FN_NAME)
    return modal.Function.lookup(APP_NAME, FN_NAME)  # older SDKs


def build_prompt(scene: dict) -> str:
    """Turn a scene's visual keywords into a cinematic generation prompt."""
    kws = ", ".join((scene.get("stock_keywords") or [])[:3]) or "technology, ai"
    return (
        f"Cinematic vertical b-roll: {kws}. Modern tech aesthetic, shallow depth "
        f"of field, smooth camera movement, soft volumetric lighting, 4k, "
        f"highly detailed, no text, no watermark."
    )


def fetch_clip(scene: dict, out_dir: Path, seconds: int = 3) -> Path | None:
    """Generate one AI clip on Modal's GPU. Returns None on any problem."""
    if not available():
        return None
    try:
        fn = _lookup()
        prompt = build_prompt(scene)
        print(f"[modal] generating AI b-roll for scene {scene.get('id')} ...",
              flush=True)
        data = fn.remote(prompt, int(seconds))
        if not data or len(data) < 20_000:
            print("[modal] returned no usable data; falling back to stock.")
            return None
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"ai_{int(scene.get('id', 0)):02d}.mp4"
        dest.write_bytes(data)
        print(f"[modal] scene {scene.get('id')} -> {dest.name} "
              f"({len(data)/1e6:.2f} MB)", flush=True)
        return dest
    except Exception as exc:
        print(f"[modal] unavailable ({exc}); falling back to stock footage.")
        return None
