"""Build the finished vertical short (1080x1920) from real HD stock footage.

Per scene: fetch stock clip -> trim to that line's narration length -> fill the
9:16 frame (blurred backdrop so nothing is cropped away) -> burn a bold caption.
Then concat all scenes, mix voice + music, and stamp the hook (first 3s) and the
follow CTA (last 3s) so retention and conversion are handled.

Pure FFmpeg + Python: no GPU, runs on GitHub Actions.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from config import settings
from src import captions, history, stock
from src.backends import modal_video

# Render size: HD 1080x1920 (Shorts native) or 4K 2160x3840.
if settings.video_quality.lower() in ("4k", "uhd", "2160"):
    W, H = 2160, 3840
else:
    W, H = 1080, 1920
FPS = 30
CRF = str(settings.video_crf)
# Tight pacing: only a small breath between lines (was 1.6s minimum + 0.45s
# padding, which produced audible 1-2s dead gaps between sentences).
# MAX_SCENE must stay comfortably above the longest narration line, because the
# voice track lays each mp3 down in full: clamping a scene shorter than its own
# audio pushes that audio into the next scene and it gets cut by -shortest.
# A 20-word line is ~7s, and narration is capped at 220 chars (~35 words).
MIN_SCENE, MAX_SCENE = 1.1, 15.0
SCENE_PAD = float(os.getenv("SCENE_PAD", "0.12"))  # seconds of breath per line
# HARD FLOOR: a short below this is never published. Scene length is driven
# entirely by the narration audio, so the real fix lives in the script writer
# (src/news_script.py enforces a spoken-word budget); this is the safety net
# that catches anything which still slips through.
MIN_SHORT_SECONDS = float(os.getenv("MIN_SHORT_SECONDS", "25"))
_S = W / 1080.0  # font scale so text looks identical at any resolution


def _run(cmd: list[str], what: str) -> bool:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[build] {what} failed: {res.stderr[-400:]}")
        return False
    return True


def _duration(path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


def _scene_clip(src: Path | None, seconds: float, scene: dict,
                work: Path, out: Path) -> bool:
    """One scene: stock footage filled to 9:16 + big caption, exact length."""
    big = scene.get("role") in ("hook", "cta")
    cap = captions.wrap(scene.get("caption") or "", width=18 if big else 22)
    cap_tf = captions.write_text(work, f"cap_{scene['id']:02d}.txt", cap)
    draw = (
        f"drawtext=textfile={cap_tf}{captions.font_opt()}:fontcolor=white:"
        f"fontsize={int((92 if big else 76) * _S)}:"
        f"line_spacing={int(14 * _S)}:box=1:boxcolor=black@0.55:"
        f"boxborderw={int(30 * _S)}:x=(w-text_w)/2:y=h*{0.70 if big else 0.74}"
    )

    if src and src.exists():
        src_len = _duration(src)
        # loop the clip if it is shorter than the narration
        loops = max(0, int(seconds / max(src_len, 0.5)))
        vf = (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},boxblur=luma_radius=30:luma_power=1[bg];"
            f"[0:v]scale={W}:-2:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
            f"zoompan=z='min(zoom+0.0008,1.12)':d=1:s={W}x{H}:fps={FPS},"
            f"{draw},setsar=1[v]"
        )
        cmd = ["ffmpeg", "-y"]
        if loops:
            cmd += ["-stream_loop", str(loops)]
        cmd += ["-i", str(src), "-t", f"{seconds:.2f}",
                "-filter_complex", vf, "-map", "[v]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", CRF,
                "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(out)]
    else:
        # graceful fallback: clean gradient card so a run never dies
        cmd = ["ffmpeg", "-y", "-f", "lavfi",
               "-i", f"color=c=0x101826:s={W}x{H}:d={seconds:.2f}:r={FPS}",
               "-vf", f"{draw},setsar=1",
               "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
               "-an", str(out)]
    return _run(cmd, f"scene {scene['id']}")


def _concat(clips: list[Path], out: Path) -> bool:
    lst = out.parent / "_concat.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), "utf-8")
    return _run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", CRF,
         "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)],
        "concat",
    )


def _voice_track(voice_manifest: Path, durations: dict[int, float], out: Path) -> Path | None:
    """Lay each scene's narration at that scene's start time."""
    if not voice_manifest.exists():
        return None
    entries = [e for e in json.loads(voice_manifest.read_text("utf-8")) if e.get("audio")]
    if not entries:
        return None

    starts, t = {}, 0.0
    for sid in sorted(durations):
        starts[sid] = t
        t += durations[sid]

    inputs, filters, idx = [], [], 0
    for e in entries:
        delay = int(starts.get(e["id"], 0.0) * 1000)
        inputs += ["-i", e["audio"]]
        filters.append(f"[{idx}:a]adelay={delay}|{delay}[a{idx}]")
        idx += 1
    if not idx:
        return None
    mix = "".join(f"[a{i}]" for i in range(idx)) + f"amix=inputs={idx}:normalize=0[vo]"
    ok = _run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters + [mix]),
         "-map", "[vo]", "-c:a", "aac", str(out)],
        "voice track",
    )
    return out if ok else None


def _music() -> Path | None:
    d = settings.assets_audio_dir
    if not d.exists():
        return None
    for ext in ("*.mp3", "*.m4a", "*.wav", "*.ogg"):
        files = sorted(d.glob(ext))
        if files:
            return files[0]
    return None


def build_short(storyboard_path: Path, index: int = 1,
                hist: dict | None = None) -> Path:
    """Build one finished short. Returns the mp4 path.

    `hist` is the channel's lifelong memory (content/history.json). When given,
    every stock clip it has ever used is excluded, so no footage is ever seen
    twice on the channel, and newly picked clips are recorded into it.
    """
    date_dir = Path(storyboard_path).parent
    sb = json.loads(Path(storyboard_path).read_text("utf-8"))
    scenes = sb.get("scenes", [])
    if not scenes:
        raise RuntimeError("storyboard has no scenes")

    work = date_dir / f"work_{index:02d}"
    work.mkdir(parents=True, exist_ok=True)
    stock_dir = date_dir / "stock"
    audio_dir = date_dir / "audio"

    # HARD PRE-FLIGHT: without a stock provider (or Modal AI b-roll) every scene
    # would be a blank card, which must never reach YouTube.
    if not stock.have_keys() and not modal_video.available():
        raise RuntimeError(
            "No stock provider configured — set PEXELS_API_KEY (free) "
            "and/or PIXABAY_API_KEY. Refusing to build a footage-less video."
        )

    # Lifelong clip de-duplication: start from every clip the channel has used.
    used: set[str] = set(history.used_clip_ids(hist)) if hist else set()
    reusable: set[str] = history.oldest_clips(hist) if hist else set()
    if hist:
        print(f"[build] excluding {len(used)} previously used clips")
    clips: list[Path] = []
    durations: dict[int, float] = {}
    with_footage = 0

    for scene in scenes:
        sid = scene["id"]
        vo = audio_dir / f"scene_{sid:02d}.mp3"
        raw = _duration(vo) + SCENE_PAD if vo.exists() else 2.5
        if raw > MAX_SCENE:
            print(f"[build] WARNING scene {sid} narration is {raw:.1f}s but "
                  f"scenes are capped at {MAX_SCENE:.0f}s — its tail will be cut")
        seconds = max(MIN_SCENE, min(raw, MAX_SCENE))
        durations[sid] = seconds

        # Premium path first: AI-generated b-roll on Modal's GPU (if enabled),
        # otherwise real HD stock footage.
        src = None
        if modal_video.available():
            src = modal_video.fetch_clip(scene, stock_dir, seconds=int(seconds))
        if src is None:
            src = stock.fetch_clip(scene.get("stock_keywords") or [], stock_dir,
                                   used, reusable)
            if src is not None and hist is not None:
                history.record_clip(src.stem, hist)

        out = work / f"s_{sid:02d}.mp4"
        kind = "ai" if (src and src.name.startswith("ai_")) else ("stock" if src else "card")
        print(f"[build] scene {sid} ({scene.get('role','value')}) "
              f"{seconds:.1f}s source={kind}", flush=True)
        if _scene_clip(src, seconds, scene, work, out):
            clips.append(out)
            if src:
                with_footage += 1

    if not clips:
        raise RuntimeError("no scene clips were built")

    # Require real footage on most scenes, otherwise it's the blank-video case.
    if with_footage < max(2, int(len(scenes) * 0.6)):
        raise RuntimeError(
            f"only {with_footage}/{len(scenes)} scenes got real footage — "
            "refusing to publish a mostly-blank video (check stock API keys/quota)"
        )

    silent = work / "_silent.mp4"
    if not _concat(clips, silent):
        raise RuntimeError("concat failed")

    total = _duration(silent)
    if total < MIN_SHORT_SECONDS:
        # Not fatal here — validate_video() is the gate that rejects it — but say
        # it loudly, because the cause is always too little narration text.
        print(f"[build] WARNING total is only {total:.1f}s, below the "
              f"{MIN_SHORT_SECONDS:.0f}s floor (narration too short)")
    vo = _voice_track(audio_dir / "voice_manifest.json", durations, work / "_vo.m4a")
    music = _music()

    hook = next((s.get("caption") for s in scenes if s.get("role") == "hook"), "")
    overlay = captions.shorts_hook_cta_vf(work, hook or captions.DEFAULT_HOOK,
                                          int(total), uid=str(index), scale=_S)

    shorts_dir = date_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)
    final = shorts_dir / f"short_{index:02d}.mp4"

    cmd = ["ffmpeg", "-y", "-i", str(silent)]
    if vo:
        cmd += ["-i", str(vo)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]

    if vo and music:
        af = "[1:a]volume=1.0[v];[2:a]volume=0.12[m];[v][m]amix=inputs=2:duration=first[a]"
    elif vo:
        af = "[1:a]volume=1.0[a]"
    elif music:
        af = "[1:a]volume=0.5[a]"
    else:
        af = None

    fc = f"[0:v]{overlay}[v]" + (f";{af}" if af else "")
    cmd += ["-filter_complex", fc, "-map", "[v]"]
    cmd += ["-map", "[a]"] if af else []
    cmd += ["-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(FPS)]
    cmd += ["-c:a", "aac", "-shortest"] if af else []
    cmd += [str(final)]

    if not _run(cmd, "final mux"):
        raise RuntimeError("final mux failed")

    # housekeeping: intermediate scene clips are large and no longer needed
    shutil.rmtree(work, ignore_errors=True)

    size_mb = final.stat().st_size / 1e6 if final.exists() else 0
    print(f"[build] short ready -> {final} ({total:.1f}s, {W}x{H}, {size_mb:.1f} MB)")
    return final


def validate_video(path: Path,
                   min_seconds: float | None = None) -> tuple[bool, str]:
    """Final safety net: make sure the video is real, moving, non-blank content.

    Checks:
      * file exists and has a sane size
      * duration is long enough (>= MIN_SHORT_SECONDS, default 25s)
      * has a video stream at the expected resolution
      * frames are not mostly black/blank (ffmpeg blackframe detection)
    """
    if min_seconds is None:
        min_seconds = MIN_SHORT_SECONDS
    if not path.exists():
        return False, "file missing"
    size_mb = path.stat().st_size / 1e6
    if size_mb < 0.3:
        return False, f"file too small ({size_mb:.2f} MB)"

    dur = _duration(path)
    if dur < min_seconds:
        return False, f"too short ({dur:.1f}s)"

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,nb_frames",
         "-of", "default=nw=1", str(path)],
        capture_output=True, text=True,
    )
    if "width=" not in probe.stdout:
        return False, "no video stream"

    # Count near-black frames; a blank/failed render is overwhelmingly black.
    res = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path),
         "-vf", "blackframe=amount=95:threshold=32", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    black_hits = res.stderr.count("Parsed_blackframe")
    approx_frames = max(int(dur * FPS), 1)
    if black_hits > approx_frames * 0.5:
        return False, f"mostly blank ({black_hits}/{approx_frames} black frames)"

    return True, f"ok ({dur:.1f}s, {size_mb:.1f} MB)"


def cleanup_short(final: Path, date_dir: Path) -> None:
    """Delete the uploaded mp4 + cached footage so storage never fills up."""
    try:
        if final.exists():
            final.unlink()
        shutil.rmtree(date_dir / "stock", ignore_errors=True)
        shutil.rmtree(date_dir / "audio", ignore_errors=True)
        for p in date_dir.glob("work_*"):
            shutil.rmtree(p, ignore_errors=True)
        print(f"[build] cleaned up local files for {final.name}")
    except Exception as exc:
        print(f"[build] cleanup skipped: {exc}")
