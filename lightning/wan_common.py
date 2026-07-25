"""Shared machinery for the Lightning AI talking-video scripts.

Handles everything that is not content: pre-flight checks, model setup, GPU
detection, Wan2.2 S2V animation, 9:16 fitting, captions, joining, the quality
gate, and publishing to YouTube.

Content-specific scripts (who is talking, and about what) live next to this file
and import from here.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WAN_REPO = "https://github.com/Wan-Video/Wan2.2.git"
WAN_DIR = ROOT / "Wan2.2"
S2V_REPO_ID = "Wan-AI/Wan2.2-S2V-14B"
S2V_CKPT = ROOT / "Wan2.2-S2V-14B"
S2V_SIZE = "1024*704"

W, H = 1080, 1920
CRF = os.getenv("VIDEO_CRF", "18")

# Lightning interruptible credits/hour, used only for the cost estimate print.
RATE_PER_HOUR = float(os.getenv("GPU_RATE_PER_HOUR", "2.07"))


# --------------------------------------------------------------------------- #
# tiny shell helpers
# --------------------------------------------------------------------------- #
def sh(cmd: str, check: bool = True) -> int:
    print(f"\n$ {cmd}", flush=True)
    return subprocess.run(cmd, shell=True, check=check).returncode


def run(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def have(binary: str) -> bool:
    return run(["bash", "-lc", f"command -v {binary}"]).returncode == 0


def duration(path: Path) -> float:
    res = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    try:
        return float(res.stdout.strip().splitlines()[0])
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
# pre-flight — runs BEFORE any GPU work so a setup mistake costs 0 credits
# --------------------------------------------------------------------------- #
def preflight(ref_spec: dict[str, tuple[str, ...]],
              dry_run: bool) -> dict[str, Path]:
    print("\n=== PRE-FLIGHT ===", flush=True)
    problems: list[str] = []

    for b in ("ffmpeg", "ffprobe"):
        if not have(b):
            problems.append(f"{b} not found -> sudo apt-get install -y ffmpeg")

    refs: dict[str, Path] = {}
    for who, candidates in ref_spec.items():
        for c in candidates:
            p = ROOT / "characters" / "refs" / c
            if p.exists():
                refs[who] = p
                break
        else:
            problems.append(
                f"No reference image for {who}. Add characters/refs/"
                f"{candidates[0]} (a close-up head-and-shoulders shot facing "
                f"the camera) to the repo."
            )

    if not dry_run:
        token_file = ROOT / "secrets" / "youtube_token.json"
        raw = os.getenv("YOUTUBE_TOKEN_JSON", "").strip()
        if raw:
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(raw, encoding="utf-8")
        if not token_file.exists():
            problems.append(
                "No YouTube token. Run:\n"
                "      export YOUTUBE_TOKEN_JSON='<the JSON from GitHub secrets>'"
            )
        else:
            try:
                data = json.loads(token_file.read_text("utf-8"))
                missing = [k for k in ("refresh_token", "client_id",
                                       "client_secret") if not data.get(k)]
                if missing:
                    problems.append("youtube_token.json missing: "
                                    + ", ".join(missing))
            except json.JSONDecodeError as exc:
                problems.append(f"youtube_token.json is not valid JSON ({exc})")

    if problems:
        print("\n[ABORT] Fix these first — no GPU time was used:", flush=True)
        for p in problems:
            print(f"  - {p}", flush=True)
        sys.exit(1)

    for k, v in refs.items():
        print(f"[ok] {k} reference -> {v.relative_to(ROOT)}")
        if "_face" not in v.name:
            print("     ^ not a close-up head shot; a face shot syncs better")
    print("[ok] ffmpeg present")
    if not dry_run:
        print("[ok] YouTube token looks complete")
    return refs


# --------------------------------------------------------------------------- #
# GPU + model
# --------------------------------------------------------------------------- #
def gpu_vram_gb() -> float:
    try:
        import torch

        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"[gpu] {name} — {gb:.0f} GB")
            if gb < 22:
                print("[gpu] WARNING: this GPU is too small for the 14B model. "
                      "Switch the Studio machine to RTX 6000 (96 GB), A100 or "
                      "L4 (24 GB) — on a T4 this will crawl or fail.")
            return gb
    except Exception:
        pass
    print("[gpu] no CUDA GPU detected (fine for --download-only)")
    return 0.0


def ensure_model() -> None:
    if not WAN_DIR.exists():
        sh(f"git clone --depth 1 {WAN_REPO} {WAN_DIR}")
    sh(f"pip install -q -r {WAN_DIR}/requirements.txt", check=False)
    sh("pip install -q 'huggingface_hub[cli]' edge-tts google-generativeai "
       "google-api-python-client google-auth-oauthlib google-auth-httplib2 "
       "pytz python-dotenv Pillow", check=False)

    if S2V_CKPT.exists() and any(S2V_CKPT.iterdir()):
        print(f"[ok] weights cached: {S2V_CKPT.name}")
        return
    print("[..] downloading S2V-14B weights (~40-60 GB — slowest, costliest step)")
    if sh(f"hf download {S2V_REPO_ID} --local-dir {S2V_CKPT}", check=False) != 0:
        sh(f"huggingface-cli download {S2V_REPO_ID} --local-dir {S2V_CKPT}")
    if not (S2V_CKPT.exists() and any(S2V_CKPT.iterdir())):
        sys.exit("[ABORT] model weights failed to download")


# --------------------------------------------------------------------------- #
# voice
# --------------------------------------------------------------------------- #
def make_voice(scene: dict, out: Path, voice: str) -> Path:
    """edge-tts for one line, with the leading/trailing silence trimmed off."""
    import edge_tts

    from src import generate_voice as gv

    async def _go() -> None:
        await edge_tts.Communicate(
            scene["narration"], voice, rate=os.getenv("TTS_RATE", "+8%"),
        ).save(str(out))

    asyncio.run(_go())
    gv._trim_silence(out)
    print(f"[voice] scene {scene['id']} [{scene.get('speaker', 'host')}] "
          f"{duration(out):.1f}s")
    return out


# --------------------------------------------------------------------------- #
# animation + assembly
# --------------------------------------------------------------------------- #
def animate(scene: dict, prompt: str, ref: Path, audio: Path, out: Path,
            vram_gb: float, steps: int | None = None,
            size: str | None = None) -> bool:
    """Wan2.2 S2V: reference image + audio -> lip-synced clip."""
    # >=40 GB (RTX 6000 / A100 / H100): everything stays on the GPU -> fast.
    # 24 GB (L4): offload to CPU and run T5 on CPU so the 14B model still fits.
    big = vram_gb >= 40
    cmd = (
        f"cd {WAN_DIR} && python generate.py "
        f"--task s2v-14B --size {size or S2V_SIZE} --ckpt_dir {S2V_CKPT} "
        f"--offload_model {'False' if big else 'True'} --convert_model_dtype "
        f"{'' if big else '--t5_cpu '}"
        f'--prompt "{prompt}" '
        f"--image {ref} --audio {audio} --save_file {out}"
    )
    if steps:
        cmd += f" --sample_steps {steps}"
    rc = sh(cmd, check=False)
    ok = rc == 0 and out.exists() and out.stat().st_size > 50_000
    print(f"[animate] scene {scene['id']} -> {'OK' if ok else 'FAILED'}")
    if not ok and not big:
        print("     hint: a 24 GB GPU can run out of memory. Retry with "
              "--size 704*544")
    return ok


def fit_and_caption(clip: Path, scene: dict, audio: Path, work: Path,
                    out: Path) -> bool:
    """9:16 fit (nothing cropped away) + on-screen caption + this line's audio."""
    from src import captions

    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,{captions.dialogue_vf(scene, work)}"
    )
    res = run(["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-i", str(audio),
               "-vf", vf, "-map", "0:v:0", "-map", "1:a:0", "-shortest",
               "-r", "25", "-c:v", "libx264", "-preset", "medium", "-crf", CRF,
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", str(out)],
              timeout=900)
    if res.returncode != 0:
        print(f"[fit] scene {scene['id']} failed: {res.stderr[-300:]}")
        return False
    return True


def join(parts: list[Path], hook: str, work: Path, out: Path) -> bool:
    """Concat the clips, then burn the hook (first 3s) and CTA (last 3s)."""
    from src import captions

    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    joined = work / "joined.mp4"
    res = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
               "-i", str(listing), "-c", "copy", str(joined)], timeout=900)
    if res.returncode != 0:  # mismatched params -> re-encode
        res = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                   "-i", str(listing), "-c:v", "libx264", "-crf", CRF,
                   "-pix_fmt", "yuv420p", "-c:a", "aac", str(joined)],
                  timeout=1800)
    if res.returncode != 0 or not joined.exists():
        print(f"[join] failed: {res.stderr[-300:]}")
        return False

    vf = captions.shorts_hook_cta_vf(work, hook, int(duration(joined)),
                                     uid="final")
    res = run(["ffmpeg", "-y", "-v", "error", "-i", str(joined), "-vf", vf,
               "-c:v", "libx264", "-preset", "medium", "-crf", CRF,
               "-pix_fmt", "yuv420p", "-c:a", "copy", str(out)], timeout=1800)
    if res.returncode != 0 or not out.exists():
        print(f"[join] hook/CTA overlay failed: {res.stderr[-300:]}")
        return False
    return True


def quality_gate(video: Path) -> bool:
    """Never publish a broken, tiny or blank video."""
    if not video.exists():
        print("[gate] no output file")
        return False
    mb = video.stat().st_size / 1e6
    secs = duration(video)
    if mb < 0.3 or secs < 5:
        print(f"[gate] REJECTED — too small/short ({mb:.1f} MB, {secs:.1f}s)")
        return False
    res = run(["ffmpeg", "-v", "info", "-i", str(video),
               "-vf", "blackdetect=d=2:pic_th=0.98", "-f", "null", "-"],
              timeout=600)
    black = sum(1 for ln in (res.stderr or "").splitlines() if "black_start" in ln)
    if black >= 2:
        print(f"[gate] REJECTED — looks mostly blank ({black} black spans)")
        return False
    print(f"[gate] ok — {secs:.1f}s, {mb:.1f} MB")
    return True


# --------------------------------------------------------------------------- #
# publish
# --------------------------------------------------------------------------- #
def publish(video: Path, title: str, description: str, tags: list[str],
            hook: str, work: Path, privacy: str) -> str | None:
    from src import thumbnail, upload_youtube

    vid = upload_youtube.upload_video(video, title, description, tags,
                                      privacy=privacy)
    if vid and vid != "QUOTA_EXCEEDED":
        thumb = thumbnail.make_thumbnail(video, hook, work / "thumb.jpg")
        if thumb:
            upload_youtube.set_thumbnail(vid, thumb)
        print(f"\n🎬 LIVE -> https://youtube.com/watch?v={vid}")
    return vid


# --------------------------------------------------------------------------- #
def build_and_publish(scenes: list[dict], prompt_for, refs: dict[str, Path],
                      voice_for, work: Path, meta: dict, args) -> None:
    """Shared render loop: voice -> animate -> fit -> join -> gate -> publish."""
    import datetime as dt

    started = dt.datetime.now()
    vram = gpu_vram_gb()
    ensure_model()

    parts: list[Path] = []
    for scene in scenes:
        audio = make_voice(scene, work / f"line_{scene['id']:02d}.mp3",
                           voice_for(scene))
        raw = work / f"raw_{scene['id']:02d}.mp4"
        ref = refs[scene.get("speaker", "host")]
        if not animate(scene, prompt_for(scene), ref, audio, raw, vram,
                       args.steps, args.size):
            print(f"[skip] scene {scene['id']} could not be animated")
            continue
        fitted = work / f"scene_{scene['id']:02d}.mp4"
        if fit_and_caption(raw, scene, audio, work, fitted):
            parts.append(fitted)
            raw.unlink(missing_ok=True)

    if len(parts) < 2:
        sys.exit("[ABORT] fewer than 2 usable clips — nothing published. "
                 "Send me the error above and I'll fix it.")

    final = work / "short.mp4"
    if not join(parts, meta["hook"], work, final):
        sys.exit("[ABORT] could not assemble the short")
    if not quality_gate(final):
        sys.exit("[ABORT] quality gate failed — nothing published, on purpose")

    mins = (dt.datetime.now() - started).total_seconds() / 60
    print(f"\n=== BUILT in {mins:.0f} min -> {final} ===")
    print(f"    approx GPU cost: {mins / 60 * RATE_PER_HOUR:.2f} credits")

    if args.dry_run:
        print("[dry-run] upload skipped.")
        return
    publish(final, meta["title"], meta["description"], meta["tags"],
            meta["hook"], work, args.privacy)
