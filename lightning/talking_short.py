"""END-TO-END on a Lightning AI GPU: talking Jon & Katie short -> straight to YouTube.

No test files to download, no manual steps. One command builds the short and
publishes it. If you don't like it, delete it in YouTube Studio.

    git clone https://github.com/ganesha98285-lgtm/jab-ketty-met-john
    cd jab-ketty-met-john
    export YOUTUBE_TOKEN_JSON='<paste the same JSON you put in GitHub secrets>'
    python lightning/talking_short.py                 # 6 lines, ~30s, public

Useful flags:
    --scenes 4          fewer lines = cheaper/faster
    --privacy unlisted  publish quietly instead of public
    --steps 20          fewer diffusion steps = faster (slightly softer)
    --dry-run           build the mp4 but skip the YouTube upload

What it does, in order:
  1. PRE-FLIGHT: verifies ffmpeg, the YouTube token and the reference images
     BEFORE touching the GPU, so no GPU minutes are ever wasted on a setup bug.
  2. Writes the day's dialogue (Jon <-> Katie), hook first, CTA last.
  3. edge-tts voices each line (Jon = male, Katie = female) and trims silence.
  4. Wan2.2 S2V-14B animates the speaker's reference image driven by that audio
     => real lip-sync, not a slideshow.
  5. Each clip is fitted to 1080x1920, gets a speech bubble, and keeps its audio.
  6. Clips are joined, a yellow hook (first 3s) + SUBSCRIBE CTA (last 3s) burned on.
  7. Quality gate (size / duration / not-black) then upload + custom thumbnail.

Honest notes:
  * First run downloads ~40-60 GB of model weights. That download is billed GPU
    time, so it is the single most expensive part. It is cached afterwards, so
    keep this Studio alive.
  * These audio-driven models are trained mostly on HUMAN faces. Jon is a puppy
    and Katie is a cat, so the mouth movement may look off. That is a model
    limitation, not a settings bug.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

# Brand handle must be set before src.captions is imported (it reads it at import).
os.environ.setdefault("BRAND_HANDLE", "@JonAndKatie")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WAN_REPO = "https://github.com/Wan-Video/Wan2.2.git"
WAN_DIR = ROOT / "Wan2.2"
S2V_REPO_ID = "Wan-AI/Wan2.2-S2V-14B"
S2V_CKPT = ROOT / "Wan2.2-S2V-14B"
S2V_SIZE = "1024*704"

W, H = 1080, 1920
CRF = os.getenv("VIDEO_CRF", "18")

STYLE = (
    "cute 3D animated pixar-style, soft rounded shapes, big expressive eyes, "
    "warm pastel cozy cottage lighting, ultra adorable, highly detailed, clean render"
)


# --------------------------------------------------------------------------- #
# dialogue
# --------------------------------------------------------------------------- #
DAYS = [
    # (activity, [(speaker, line), ...])
    ("cooking in a cozy cottage kitchen", [
        ("Jon", "Wait till you see what Katie is cooking today."),
        ("Katie", "Good morning! Today we are making the tiniest pancakes ever."),
        ("Jon", "They are smaller than my paw. I am not even joking."),
        ("Katie", "Flip them gently, Jon. Gently!"),
        ("Jon", "Okay that one landed on my nose. Worth it."),
        ("Katie", "Follow us for a new little adventure every single day."),
    ]),
    ("a sunny garden walk with bubble tea", [
        ("Jon", "You will not believe where we are going today."),
        ("Katie", "The garden is finally blooming, so we dressed up for it."),
        ("Jon", "And we got bubble tea. Two straws, one very excited puppy."),
        ("Katie", "Jon, that is my cup."),
        ("Jon", "Was your cup. Past tense."),
        ("Katie", "Subscribe so you never miss our little days."),
    ]),
    ("fishing from a tiny wooden boat on a calm lake", [
        ("Jon", "Stay for the end, something actually bit the line."),
        ("Katie", "We are on the lake before sunrise. Very peaceful."),
        ("Jon", "I have never been this quiet in my whole life."),
        ("Katie", "Jon, the rod is moving. The rod is moving!"),
        ("Jon", "I panicked and hugged the fish. We released it. Friends now."),
        ("Katie", "Like this if you want part two tomorrow."),
    ]),
    ("grocery shopping in a tiny cozy market", [
        ("Jon", "Katie gave me a shopping list. This will go badly."),
        ("Katie", "Three things, Jon. Milk, carrots, and bread."),
        ("Jon", "I came back with snacks. All snacks."),
        ("Katie", "Where is the bread?"),
        ("Jon", "I ate the bread on the way home. Full transparency."),
        ("Katie", "Follow us, we post a new day every day."),
    ]),
    ("a cozy rainy evening reading the adventure diary", [
        ("Jon", "It is raining, so we are reading our adventure diary."),
        ("Katie", "Page one. The day Jon met me."),
        ("Jon", "I remember. You hissed at me for nine minutes."),
        ("Katie", "You were very loud and very wet."),
        ("Jon", "And now we share a blanket. Character growth."),
        ("Katie", "Subscribe and grow up with us."),
    ]),
]


def todays_dialogue(n_scenes: int) -> tuple[str, list[dict]]:
    """Pick the day's set (rotates automatically) and build scene dicts."""
    idx = dt.date.today().toordinal() % len(DAYS)
    activity, lines = DAYS[idx]
    lines = lines[:max(2, n_scenes)]
    scenes: list[dict] = []
    for i, (speaker, line) in enumerate(lines, start=1):
        scenes.append({
            "id": i,
            "speaker": speaker,
            "narration": line,
            "hook": i == 1,
            "cta": i == len(lines),
            "activity": activity,
        })
    return activity, scenes


def visual_prompt(scene: dict) -> str:
    who = (
        "a cute golden Labrador puppy named Jon wearing a brown collar with a "
        "bone name tag"
        if scene["speaker"] == "Jon"
        else "a cute fluffy white Persian cat named Katie wearing a pink bow and "
             "a pink dress"
    )
    return (
        f"{who} talking to the camera while {scene['activity']}, gentle head "
        f"movement, expressive eyes, natural mouth movement, cinematic, {STYLE}"
    )


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def sh(cmd: str, check: bool = True) -> int:
    print(f"\n$ {cmd}", flush=True)
    return subprocess.run(cmd, shell=True, check=check).returncode


def run(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def have(binary: str) -> bool:
    return run(["bash", "-lc", f"command -v {binary}"]).returncode == 0


def probe(path: Path, entry: str) -> str:
    res = run(["ffprobe", "-v", "error", "-show_entries", entry,
               "-of", "default=nw=1:nk=1", str(path)])
    return res.stdout.strip().splitlines()[0] if res.stdout.strip() else ""


def duration(path: Path) -> float:
    try:
        return float(probe(path, "format=duration"))
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
# pre-flight (runs BEFORE any GPU work)
# --------------------------------------------------------------------------- #
def preflight(dry_run: bool) -> dict[str, Path]:
    print("\n=== PRE-FLIGHT ===", flush=True)
    problems: list[str] = []

    for b in ("ffmpeg", "ffprobe"):
        if not have(b):
            problems.append(f"{b} not found. Install it: `sudo apt-get install -y ffmpeg`")

    refs: dict[str, Path] = {}
    for name, candidates in {
        "Jon": ("jon.png", "john.png"),
        "Katie": ("katie.png", "katty.png"),
    }.items():
        for c in candidates:
            p = ROOT / "characters" / "refs" / c
            if p.exists():
                refs[name] = p
                break
        else:
            problems.append(
                f"No reference image for {name}. Add characters/refs/"
                f"{candidates[0]} to the repo."
            )

    if not dry_run:
        token_file = ROOT / "secrets" / "youtube_token.json"
        raw = os.getenv("YOUTUBE_TOKEN_JSON", "").strip()
        if raw:
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(raw, encoding="utf-8")
        if not token_file.exists():
            problems.append(
                "No YouTube token. Either run:\n"
                "      export YOUTUBE_TOKEN_JSON='<the JSON from GitHub secrets>'\n"
                "    or create the file secrets/youtube_token.json with that JSON."
            )
        else:
            try:
                data = json.loads(token_file.read_text("utf-8"))
                missing = [k for k in ("refresh_token", "client_id", "client_secret")
                           if not data.get(k)]
                if missing:
                    problems.append(
                        "youtube_token.json is missing: " + ", ".join(missing)
                    )
            except json.JSONDecodeError as exc:
                problems.append(f"youtube_token.json is not valid JSON ({exc})")

    if problems:
        print("\n[ABORT] Fix these first (no GPU time was used):", flush=True)
        for p in problems:
            print(f"  - {p}", flush=True)
        sys.exit(1)

    for k, v in refs.items():
        print(f"[ok] {k} reference -> {v.relative_to(ROOT)}")
    print("[ok] ffmpeg present")
    if not dry_run:
        print("[ok] YouTube token looks complete")
    return refs


# --------------------------------------------------------------------------- #
# model setup
# --------------------------------------------------------------------------- #
def gpu_vram_gb() -> float:
    try:
        import torch

        if torch.cuda.is_available():
            gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"[gpu] {torch.cuda.get_device_name(0)} — {gb:.0f} GB")
            return gb
    except Exception:
        pass
    print("[gpu] could not detect a CUDA GPU")
    return 0.0


def ensure_model() -> None:
    if not WAN_DIR.exists():
        sh(f"git clone --depth 1 {WAN_REPO} {WAN_DIR}")
    sh(f"pip install -q -r {WAN_DIR}/requirements.txt", check=False)
    sh("pip install -q 'huggingface_hub[cli]' edge-tts "
       "google-api-python-client google-auth-oauthlib google-auth-httplib2 "
       "pytz python-dotenv Pillow", check=False)

    if S2V_CKPT.exists() and any(S2V_CKPT.iterdir()):
        print(f"[ok] weights cached: {S2V_CKPT.name}")
        return
    print("[..] downloading S2V-14B weights (~40-60 GB — the slow, costly part)")
    if sh(f"hf download {S2V_REPO_ID} --local-dir {S2V_CKPT}", check=False) != 0:
        sh(f"huggingface-cli download {S2V_REPO_ID} --local-dir {S2V_CKPT}")
    if not (S2V_CKPT.exists() and any(S2V_CKPT.iterdir())):
        sys.exit("[ABORT] model weights failed to download")


# --------------------------------------------------------------------------- #
# audio
# --------------------------------------------------------------------------- #
VOICES = {"Jon": "en-US-GuyNeural", "Katie": "en-US-JennyNeural"}


def make_voice(scene: dict, out: Path) -> Path:
    import edge_tts

    from src import generate_voice as gv

    async def _go() -> None:
        await edge_tts.Communicate(
            scene["narration"], VOICES.get(scene["speaker"], "en-US-AriaNeural"),
            rate=os.getenv("TTS_RATE", "+8%"),
        ).save(str(out))

    asyncio.run(_go())
    gv._trim_silence(out)  # kills the dead 1-2s pauses between lines
    print(f"[voice] scene {scene['id']} [{scene['speaker']}] {duration(out):.1f}s")
    return out


# --------------------------------------------------------------------------- #
# video
# --------------------------------------------------------------------------- #
def animate(scene: dict, ref: Path, audio: Path, out: Path,
            vram_gb: float, steps: int | None) -> bool:
    """Wan2.2 S2V: reference image + audio -> lip-synced clip."""
    big = vram_gb >= 40  # H100 / A100-80: keep everything on the GPU (much faster)
    cmd = (
        f"cd {WAN_DIR} && python generate.py "
        f"--task s2v-14B --size {S2V_SIZE} --ckpt_dir {S2V_CKPT} "
        f"--offload_model {'False' if big else 'True'} --convert_model_dtype "
        f"{'' if big else '--t5_cpu '}"
        f'--prompt "{visual_prompt(scene)}" '
        f"--image {ref} --audio {audio} --save_file {out}"
    )
    if steps:
        cmd += f" --sample_steps {steps}"
    rc = sh(cmd, check=False)
    ok = rc == 0 and out.exists() and out.stat().st_size > 50_000
    print(f"[animate] scene {scene['id']} -> {'OK' if ok else 'FAILED'}")
    return ok


def fit_and_caption(clip: Path, scene: dict, audio: Path, work: Path,
                    out: Path) -> bool:
    """9:16 fit (nothing cropped away) + speech bubble + this line's audio."""
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
    from src import captions

    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    joined = work / "joined.mp4"
    res = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
               "-i", str(listing), "-c", "copy", str(joined)], timeout=900)
    if res.returncode != 0:  # different params between clips -> re-encode
        res = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                   "-i", str(listing), "-c:v", "libx264", "-crf", CRF,
                   "-pix_fmt", "yuv420p", "-c:a", "aac", str(joined)], timeout=1800)
    if res.returncode != 0 or not joined.exists():
        print(f"[join] failed: {res.stderr[-300:]}")
        return False

    total = duration(joined)
    vf = captions.shorts_hook_cta_vf(work, hook, int(total), uid="final")
    res = run(["ffmpeg", "-y", "-v", "error", "-i", str(joined), "-vf", vf,
               "-c:v", "libx264", "-preset", "medium", "-crf", CRF,
               "-pix_fmt", "yuv420p", "-c:a", "copy", str(out)], timeout=1800)
    if res.returncode != 0 or not out.exists():
        print(f"[join] hook/CTA overlay failed: {res.stderr[-300:]}")
        return False
    return True


def quality_gate(video: Path) -> bool:
    """Never publish a broken or blank video."""
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
        print(f"[gate] REJECTED — video looks mostly blank ({black} black spans)")
        return False
    print(f"[gate] ok — {secs:.1f}s, {mb:.1f} MB")
    return True


# --------------------------------------------------------------------------- #
# publish
# --------------------------------------------------------------------------- #
HASHTAGS = ["#shorts", "#cute", "#puppy", "#cat", "#animation",
            "#dogsofyoutube", "#catsofyoutube", "#cozy", "#wholesome"]


def publish(video: Path, activity: str, hook: str, work: Path,
            privacy: str) -> str | None:
    from src import thumbnail, upload_youtube

    title = f"Jon & Katie: {activity} 🐶🐱 #shorts"
    desc = (
        f"{hook}\n\nJon the puppy and Katie the cat share their little day - "
        f"{activity}. New short every day!\n\n"
        "Subscribe for daily cozy adventures 💛\n\n" + " ".join(HASHTAGS)
    )
    vid = upload_youtube.upload_video(video, title, desc, HASHTAGS,
                                      privacy=privacy)
    if vid and vid != "QUOTA_EXCEEDED":
        thumb = thumbnail.make_thumbnail(video, hook, work / "thumb.jpg")
        if thumb:
            upload_youtube.set_thumbnail(vid, thumb)
        print(f"\n🎬 LIVE -> https://youtube.com/watch?v={vid}")
    return vid


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", type=int, default=6)
    ap.add_argument("--privacy", default=os.getenv("YOUTUBE_PRIVACY", "public"),
                    choices=["public", "unlisted", "private"])
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="build the mp4 but do not upload")
    args = ap.parse_args()

    started = dt.datetime.now()
    refs = preflight(args.dry_run)

    activity, scenes = todays_dialogue(args.scenes)
    hook = scenes[0]["narration"]
    work = ROOT / "output" / dt.date.today().isoformat() / "talking"
    work.mkdir(parents=True, exist_ok=True)
    print(f"\n=== TODAY: {activity} — {len(scenes)} lines ===")

    vram = gpu_vram_gb()
    ensure_model()

    parts: list[Path] = []
    for scene in scenes:
        audio = make_voice(scene, work / f"line_{scene['id']:02d}.mp3")
        raw = work / f"raw_{scene['id']:02d}.mp4"
        if not animate(scene, refs[scene["speaker"]], audio, raw, vram, args.steps):
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
    if not join(parts, hook, work, final):
        sys.exit("[ABORT] could not assemble the short")
    if not quality_gate(final):
        sys.exit("[ABORT] quality gate failed — nothing published (this is on "
                 "purpose, so no bad video ever reaches your channel)")

    mins = (dt.datetime.now() - started).total_seconds() / 60
    print(f"\n=== BUILT in {mins:.0f} min -> {final} ===")
    print(f"    (approx H100 cost: {mins / 60 * 3.82:.2f} credits)")

    if args.dry_run:
        print("[dry-run] upload skipped. File is above; download it if you want.")
        return
    publish(final, activity, hook, work, args.privacy)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
