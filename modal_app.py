"""Modal app — REAL GPU video generation on Modal's free $30/month credits.

Deploy once (from your laptop or any shell):

    pip install modal
    modal setup                 # opens browser, links your free account
    modal deploy modal_app.py

After that the daily GitHub Actions run can call this function to generate
cinematic AI b-roll clips on a proper GPU (L4/A10G) instead of relying only on
stock footage. Modal is serverless: it spins up on demand and scales to zero,
so you only burn credits for the seconds you actually generate.

Cost guide (free tier = $30/month, renewed monthly):
  L4  ≈ $0.80/hr  → a 3s clip ≈ 40-70s of GPU ≈ $0.01-0.02
  So roughly 2-3 fully AI-generated shorts per day stay inside the free credits.
"""
from __future__ import annotations

import modal

APP_NAME = "ai-shorts-video"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "torch",
        "diffusers>=0.35.1",
        "transformers>=4.44",
        "accelerate",
        "sentencepiece",
        "imageio-ffmpeg",
        "Pillow",
    )
)

app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name("ltx-model-cache", create_if_missing=True)

MODEL_ID = "Lightricks/LTX-Video"
NEGATIVE = (
    "worst quality, blurry, distorted, deformed, flickering, jittery, "
    "watermark, text, logo, low resolution"
)


@app.function(
    image=image,
    gpu="L4",                      # cheapest GPU that handles LTX comfortably
    volumes={"/cache": model_cache},
    timeout=60 * 20,
    scaledown_window=120,
)
def generate_clip(prompt: str, seconds: int = 3, steps: int = 30,
                  width: int = 704, height: int = 1280) -> bytes:
    """Generate one vertical AI video clip and return the mp4 bytes."""
    import os
    import tempfile

    os.environ.setdefault("HF_HOME", "/cache/hf")

    import torch
    from diffusers import LTXPipeline
    from diffusers.utils import export_to_video

    fps = 24
    # LTX needs frames = k*8 + 1 and dimensions divisible by 32.
    target = max(2, min(int(seconds), 6)) * fps
    num_frames = max(1, round((target - 1) / 8)) * 8 + 1
    width -= width % 32
    height -= height % 32

    pipe = LTXPipeline.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16, low_cpu_mem_usage=False
    ).to("cuda")
    try:
        pipe.vae.enable_tiling()
    except Exception:
        pass

    frames = pipe(
        prompt=prompt,
        negative_prompt=NEGATIVE,
        width=width,
        height=height,
        num_frames=num_frames,
        num_inference_steps=steps,
    ).frames[0]

    out = os.path.join(tempfile.mkdtemp(), "clip.mp4")
    export_to_video(frames, out, fps=fps)
    with open(out, "rb") as f:
        return f.read()


@app.local_entrypoint()
def main(prompt: str = "cinematic shot of a futuristic AI data center, neon lights"):
    data = generate_clip.remote(prompt, 3)
    with open("modal_test_clip.mp4", "wb") as f:
        f.write(data)
    print(f"wrote modal_test_clip.mp4 ({len(data)/1e6:.2f} MB)")
