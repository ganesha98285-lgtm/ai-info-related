"""Build the finished vertical short (1080x1920) from real HD stock footage.

Per scene: fetch stock clip -> trim to that line's narration length -> fill the
9:16 frame (blurred backdrop so nothing is cropped away) -> burn a bold caption.
Then concat all scenes, mix voice + music, and stamp the hook (first 3s) and the
follow CTA (last 3s) so retention and conversion are handled.

Pure FFmpeg + Python: no GPU, runs on GitHub Actions.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from config import settings
from src import captions, stock

W, H, FPS = 1080, 1920, 30
MIN_SCENE, MAX_SCENE = 1.6, 9.0


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
        f"drawtext=textfile={cap_tf}:fontcolor=white:fontsize={92 if big else 76}:"
        f"line_spacing=14:box=1:boxcolor=black@0.55:boxborderw=30:"
        f"x=(w-text_w)/2:y=h*{0.70 if big else 0.74}"
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
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
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
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
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


def build_short(storyboard_path: Path, index: int = 1) -> Path:
    """Build one finished short. Returns the mp4 path."""
    date_dir = Path(storyboard_path).parent
    sb = json.loads(Path(storyboard_path).read_text("utf-8"))
    scenes = sb.get("scenes", [])
    if not scenes:
        raise RuntimeError("storyboard has no scenes")

    work = date_dir / f"work_{index:02d}"
    work.mkdir(parents=True, exist_ok=True)
    stock_dir = date_dir / "stock"
    audio_dir = date_dir / "audio"

    used: set[str] = set()
    clips: list[Path] = []
    durations: dict[int, float] = {}

    for scene in scenes:
        sid = scene["id"]
        vo = audio_dir / f"scene_{sid:02d}.mp3"
        seconds = _duration(vo) + 0.45 if vo.exists() else 3.0
        seconds = max(MIN_SCENE, min(seconds, MAX_SCENE))
        durations[sid] = seconds

        src = stock.fetch_clip(scene.get("stock_keywords") or [], stock_dir, used)
        out = work / f"s_{sid:02d}.mp4"
        print(f"[build] scene {sid} ({scene.get('role','value')}) "
              f"{seconds:.1f}s footage={'yes' if src else 'card'}", flush=True)
        if _scene_clip(src, seconds, scene, work, out):
            clips.append(out)

    if not clips:
        raise RuntimeError("no scene clips were built")

    silent = work / "_silent.mp4"
    if not _concat(clips, silent):
        raise RuntimeError("concat failed")

    total = _duration(silent)
    vo = _voice_track(audio_dir / "voice_manifest.json", durations, work / "_vo.m4a")
    music = _music()

    hook = next((s.get("caption") for s in scenes if s.get("role") == "hook"), "")
    overlay = captions.shorts_hook_cta_vf(work, hook or captions.DEFAULT_HOOK,
                                          int(total), uid=str(index))

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
            "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]
    cmd += ["-c:a", "aac", "-shortest"] if af else []
    cmd += [str(final)]

    if not _run(cmd, "final mux"):
        raise RuntimeError("final mux failed")

    print(f"[build] short ready -> {final} ({total:.1f}s)")
    return final
