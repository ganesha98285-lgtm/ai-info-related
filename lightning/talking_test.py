"""STEP 1 — one cheap test clip on a free Lightning AI GPU (no credit card).

Run this INSIDE a Lightning AI Studio terminal (browser — nothing installed on
your laptop):

    git clone https://github.com/ganesha98285-lgtm/jab-ketty-met-john
    cd jab-ketty-met-john
    python lightning/talking_test.py --mode i2v      # fast, motion only
    python lightning/talking_test.py --mode s2v      # slower, LIP-SYNC

Why two modes:
  * i2v  = Wan2.2 **TI2V-5B** (light, ~5B). Validates motion quality + speed
           cheaply. Character moves, camera moves — but no lip-sync.
  * s2v  = Wan2.2 **S2V-14B** (heavy, audio-driven). This is the real
           "characters talking with lip-sync" model.

Look at the produced mp4 BEFORE we automate anything, so we never waste hours
again on output you don't like.

Honest notes:
  * s2v-14B downloads ~40-60 GB of weights and wants a 24 GB+ GPU. On a smaller
    free GPU it still runs with the offload flags below, just slower.
  * These models are trained mostly on humans. On cartoon ANIMAL faces (Jon the
    puppy, Katie the cat) lip-sync can look off. That's exactly what this test
    is for — judge it with your own eyes first.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/Wan-Video/Wan2.2.git"
WAN_DIR = Path("Wan2.2")
MODELS = {
    "i2v": ("Wan-AI/Wan2.2-TI2V-5B", "ti2v-5B", "1280*704"),
    "s2v": ("Wan-AI/Wan2.2-S2V-14B", "s2v-14B", "1024*704"),
}

PROMPT = (
    "A cute 3D animated golden Labrador puppy with a brown collar talks to the "
    "camera in a cozy cottage kitchen, warm soft lighting, gentle head movement, "
    "expressive eyes, cinematic, highly detailed, pixar-like animation style"
)
LINE = "Hey friends! Today Katie and I are making tiny pancakes. You have to see this."


def sh(cmd: str, check: bool = True) -> int:
    print(f"\n$ {cmd}", flush=True)
    return subprocess.run(cmd, shell=True, check=check).returncode


def ensure_repo() -> None:
    if not WAN_DIR.exists():
        sh(f"git clone {REPO} {WAN_DIR}")
    sh(f"pip install -q -r {WAN_DIR}/requirements.txt", check=False)
    sh("pip install -q 'huggingface_hub[cli]' edge-tts", check=False)


def ensure_model(repo_id: str, local_dir: Path) -> None:
    if local_dir.exists() and any(local_dir.iterdir()):
        print(f"[ok] weights already present: {local_dir}")
        return
    print(f"[..] downloading {repo_id} (this is the slow part)")
    sh(f"hf download {repo_id} --local-dir {local_dir}", check=False)
    if not (local_dir.exists() and any(local_dir.iterdir())):
        sh(f"huggingface-cli download {repo_id} --local-dir {local_dir}")


def make_audio(out: Path) -> Path:
    """Jon's voice line via edge-tts (free, no key)."""
    if out.exists():
        return out
    sh(f'edge-tts --voice en-US-GuyNeural --text "{LINE}" --write-media {out}',
       check=False)
    if not out.exists():
        raise SystemExit("could not synthesize audio with edge-tts")
    return out


def pick_reference() -> Path:
    """Use the Jon reference image if present, else the sliced sheet panel."""
    for p in (Path("characters/sprites/jon_closed.png"),
              Path("characters/refs/jon.png"),
              Path("characters/refs/sheet.png")):
        if p.exists():
            print(f"[ok] reference image: {p}")
            return p
    raise SystemExit(
        "No reference image found. Add characters/refs/jon.png "
        "(or sheet.png) to the repo first."
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["i2v", "s2v"], default="i2v")
    ap.add_argument("--steps", type=int, default=None, help="fewer = faster")
    args = ap.parse_args()

    repo_id, task, size = MODELS[args.mode]
    ckpt = Path(repo_id.split("/")[-1])

    ensure_repo()
    ensure_model(repo_id, ckpt)

    ref = pick_reference().resolve()
    out = Path(f"talking_test_{args.mode}.mp4").resolve()

    cmd = (
        f"cd {WAN_DIR} && python generate.py "
        f"--task {task} --size {size} --ckpt_dir ../{ckpt} "
        f"--offload_model True --convert_model_dtype --t5_cpu "
        f'--prompt "{PROMPT}" --image {ref} --save_file {out}'
    )
    if args.mode == "s2v":
        audio = make_audio(Path("jon_line.mp3")).resolve()
        cmd += f" --audio {audio}"
    if args.steps:
        cmd += f" --sample_steps {args.steps}"

    rc = sh(cmd, check=False)
    if rc == 0 and out.exists():
        mb = out.stat().st_size / 1e6
        print(f"\n✅ DONE -> {out} ({mb:.1f} MB)")
        print("Download it from the Lightning file browser and watch it.")
    else:
        print("\n❌ generation failed — copy the error above and send it to me.")
        sys.exit(1)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
