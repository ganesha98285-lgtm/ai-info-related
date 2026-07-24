"""REAL image-to-video generation with LTX-Video (open source, free).

This turns each scene's reference image (a sliced activity panel from the
character sheet, or jon.png/katie.png) into an actual MOTION video clip using
the LTX-Video image-to-video diffusion model. It runs on a single ~10-16 GB GPU
(e.g. Kaggle's free T4), so it is meant to be executed inside the Kaggle
notebook (see kaggle/notebook.py), NOT on the GPU-less GitHub Actions runner.

Output matches what assemble.py expects:
  output/<date>/clips/scene_XX.mp4  +  clips_manifest.json
"""
from __future__ import annotations

import gc
import json
import os
from pathlib import Path

# LTX-Video works best with resolutions divisible by 32 and num_frames = k*8 + 1.
FRAME_W, FRAME_H = 768, 512
FPS = 24
# Tunable for speed vs quality (env-overridable). Fewer steps + shorter clips
# = much faster on a free GPU and avoids memory build-up between scenes.
STEPS = int(os.getenv("LTX_STEPS", "24"))
MAX_SECONDS = int(os.getenv("LTX_MAX_SECONDS", "3"))


def _num_frames(seconds: int) -> int:
    # nearest (k*8 + 1) for the requested duration, clamped for free-GPU speed.
    target = max(2, min(int(seconds), MAX_SECONDS)) * FPS
    k = max(1, round((target - 1) / 8))
    return k * 8 + 1  # e.g. ~73 frames ≈ 3s @ 24fps


def _pick_reference(scene: dict, index: int, panels: dict, refs_dir: Path):
    """Choose the conditioning image for a scene (panel > jon/katie)."""
    from src import sheet_slicer

    if panels:
        text = (
            f"{scene.get('activity','')} {scene.get('beat','')} "
            f"{scene.get('visual_prompt','')}"
        ).lower()
        for act in sheet_slicer.ACTIVITY_ORDER:
            if act in text and act in panels:
                return panels[act]
        order = [a for a in sheet_slicer.ACTIVITY_ORDER if a in panels]
        if order:
            return panels[order[index % len(order)]]
        if "duo" in panels:
            return panels["duo"]

    jon = refs_dir / "jon.png"
    katie = refs_dir / "katie.png"
    text = f"{scene.get('visual_prompt','')} {scene.get('narration','')}".lower()
    if "katie" in text and "jon" not in text and katie.exists():
        return katie
    if jon.exists():
        return jon
    return katie if katie.exists() else None


NEGATIVE = (
    "worst quality, blurry, distorted, deformed, extra limbs, extra legs, "
    "fused fingers, warped face, flickering, jittery, watermark, text, logo"
)


def run_ltx(storyboard: dict, refs_dir: Path, clips_dir: Path) -> list[Path]:
    import torch
    from diffusers import LTXImageToVideoPipeline
    from diffusers.utils import export_to_video, load_image

    from src import sheet_slicer

    clips_dir.mkdir(parents=True, exist_ok=True)

    # Slice the character sheet into 8 activity panels (if present).
    panels: dict = {}
    sheet = refs_dir / "sheet.png"
    if sheet.exists():
        panels = sheet_slicer.slice_sheet(sheet, clips_dir / "_panels")

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    print(f"[ltx] loading Lightricks/LTX-Video (dtype={dtype}) ...", flush=True)
    # low_cpu_mem_usage=False avoids the meta-device "Materializing param..."
    # path that can hang on Kaggle. LTX-Video (~10GB) fits a 16GB GPU, so we
    # load it fully onto the GPU (faster + reliable) instead of cpu-offload.
    pipe = LTXImageToVideoPipeline.from_pretrained(
        "Lightricks/LTX-Video", torch_dtype=dtype, low_cpu_mem_usage=False
    )
    if torch.cuda.is_available():
        try:
            pipe = pipe.to("cuda")
        except Exception as exc:
            print(f"[ltx] to(cuda) failed ({exc}); using cpu offload.", flush=True)
            pipe.enable_model_cpu_offload()
    try:
        pipe.vae.enable_tiling()
    except Exception:
        pass
    print("[ltx] model ready — generating scenes...", flush=True)

    clips: list[Path] = []
    scenes = storyboard.get("scenes", [])
    for i, scene in enumerate(scenes):
        ref = _pick_reference(scene, i, panels, refs_dir)
        prompt = scene.get("visual_prompt", "cute animated Jon and Katie scene")
        n_frames = _num_frames(scene.get("seconds", 5))
        out = clips_dir / f"scene_{scene['id']:02d}.mp4"
        print(f"[ltx] scene {scene['id']}/{len(scenes)} ({scene.get('activity','')}) "
              f"-> {n_frames} frames, {STEPS} steps, ref={ref.name if ref else 'none'}",
              flush=True)

        frames = None
        try:
            kwargs = dict(
                prompt=prompt,
                negative_prompt=NEGATIVE,
                width=FRAME_W,
                height=FRAME_H,
                num_frames=n_frames,
                num_inference_steps=STEPS,
            )
            if ref is not None:
                kwargs["image"] = load_image(str(ref)).resize((FRAME_W, FRAME_H))
            frames = pipe(**kwargs).frames[0]
            export_to_video(frames, str(out), fps=FPS)
            # Burn the speech bubble (speaker + dialogue) onto the motion clip.
            try:
                from src import captions

                captions.overlay_on_file(out, scene, clips_dir)
            except Exception as exc:
                print(f"[ltx] caption overlay skipped: {exc}", flush=True)
            clips.append(out)
            print(f"[ltx] scene {scene['id']} DONE ({out.name})", flush=True)
        except Exception as exc:
            print(f"[ltx] scene {scene['id']} failed: {exc}", flush=True)

        # Free GPU/CPU memory so later scenes don't stall or OOM.
        del frames
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    if not clips:
        raise RuntimeError("LTX produced no clips")

    (clips_dir / "clips_manifest.json").write_text(
        json.dumps([str(c) for c in clips], indent=2), "utf-8"
    )
    print(f"[ltx] {len(clips)} motion clips -> {clips_dir}")
    return clips
