# 🧊 Free HD video on Kaggle GPU (LTX-2)

The `kaggle` backend renders each scene with **LTX-2** (open-source, native HD,
image-to-video) on Kaggle's **free GPU (~30h/week)** so your own machine and
GitHub Actions never need a GPU.

## Flow
1. `src/backends/kaggle_runner.py` writes `storyboard.json` + `john.png` /
   `ketty.png` into a Kaggle kernel input, pushes the kernel, waits, and pulls
   back the rendered `scene_*.mp4` files.
2. The heavy lifting lives in a Kaggle notebook you create once.

## Create the Kaggle kernel (once)

1. On kaggle.com, create a new **Notebook**, enable **GPU** (T4) in settings.
2. Install LTX-2 and run image-to-video per scene. Sketch:

```python
# Kaggle notebook (pseudocode)
!pip -q install "diffusers>=0.31" transformers accelerate imageio[ffmpeg]
import json, torch
from pathlib import Path
# from diffusers import LTXImageToVideoPipeline   # LTX-2 pipeline

sb = json.load(open("/kaggle/input/jkmj/storyboard.json"))
refs = {"john": "/kaggle/input/jkmj/john.png", "ketty": "/kaggle/input/jkmj/ketty.png"}
out = Path("/kaggle/working"); out.mkdir(exist_ok=True)

# pipe = LTXImageToVideoPipeline.from_pretrained("Lightricks/LTX-Video",
#         torch_dtype=torch.bfloat16).to("cuda")

for scene in sb["scenes"]:
    ref = refs["ketty"] if "ketty" in scene["visual_prompt"].lower() else refs["john"]
    # frames = pipe(prompt=scene["visual_prompt"], image=load(ref),
    #               num_frames=scene["seconds"]*24, width=1280, height=720).frames[0]
    # export_to_video(frames, f"/kaggle/working/scene_{scene['id']:02d}.mp4", fps=24)
    pass
```

3. Note the kernel slug (`youruser/ltx-render-kernel`) and set it as the
   `KAGGLE_KERNEL_SLUG` GitHub Variable, plus `KAGGLE_USERNAME` / `KAGGLE_KEY`
   secrets.

## Tips
- Render at 720p on the free GPU, then upscale with Real-ESRGAN for crisp 1080p.
- Keep clips short (6-8s) — LTX-2 is most consistent in that window, and the
  assembler stitches them into the full vlog.
- If the kernel is busy or quota is hit, the pipeline auto-falls back to `stub`
  so a daily video still ships.
