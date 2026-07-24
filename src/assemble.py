"""Step 4 — Assemble scene clips + narration + background music into the master
HD vlog (1920x1080).

Pipeline:
  1. Concatenate all scene clips in order.
  2. Mux per-scene narration onto the timeline (falls back to no VO if silent).
  3. Mix in a soft background music / ASMR bed from assets/audio (looped, low vol).
  4. Export output/<date>/vlog_master.mp4.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from config import settings


def _run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n{res.stderr[-800:]}")


def _concat_clips(clips: list[Path], out: Path) -> None:
    listfile = out.parent / "_concat.txt"
    listfile.write_text(
        "".join(f"file '{c.resolve()}'\n" for c in clips), "utf-8"
    )
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25", str(out),
    ])


def _build_voiceover_track(voice_manifest: Path, clips: list[Path], out: Path) -> Path | None:
    """Place each scene's narration at that scene's start time on one audio track."""
    if not voice_manifest.exists():
        return None
    entries = json.loads(voice_manifest.read_text("utf-8"))
    have_audio = [e for e in entries if e.get("audio")]
    if not have_audio:
        return None

    # compute scene start offsets from clip durations
    offsets: dict[int, float] = {}
    t = 0.0
    for i, clip in enumerate(clips, start=1):
        offsets[i] = t
        t += _duration(clip)

    inputs: list[str] = []
    filters: list[str] = []
    idx = 0
    for e in have_audio:
        sid = e["id"]
        delay_ms = int(offsets.get(sid, 0.0) * 1000)
        inputs += ["-i", e["audio"]]
        filters.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms}[a{idx}]")
        idx += 1
    mix = "".join(f"[a{i}]" for i in range(idx)) + f"amix=inputs={idx}:normalize=0[vo]"
    filter_complex = ";".join(filters + [mix])

    vo_path = out
    _run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex, "-map", "[vo]",
        "-c:a", "aac", str(vo_path),
    ])
    return vo_path


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


def _pick_music() -> Path | None:
    if not settings.assets_audio_dir.exists():
        return None
    for ext in ("*.mp3", "*.m4a", "*.wav", "*.ogg"):
        files = sorted(settings.assets_audio_dir.glob(ext))
        if files:
            return files[0]
    return None


def assemble_vlog(storyboard_path: Path) -> Path:
    date_dir = Path(storyboard_path).parent
    clips = [Path(p) for p in json.loads(
        (date_dir / "clips" / "clips_manifest.json").read_text("utf-8")
    )]
    if not clips:
        raise RuntimeError("No clips to assemble. Run generate_video first.")

    silent_video = date_dir / "_video_only.mp4"
    _concat_clips(clips, silent_video)

    # Voiceover track (optional)
    vo = _build_voiceover_track(
        date_dir / "audio" / "voice_manifest.json", clips,
        date_dir / "_voiceover.m4a",
    )
    music = _pick_music()

    master = date_dir / "vlog_master.mp4"
    total = _duration(silent_video)

    if vo and music:
        _run([
            "ffmpeg", "-y", "-i", str(silent_video), "-i", str(vo),
            "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            "[1:a]volume=1.0[v];[2:a]volume=0.18[m];[v][m]amix=inputs=2:duration=first[a]",
            "-map", "0:v", "-map", "[a]", "-t", str(total),
            "-c:v", "copy", "-c:a", "aac", "-shortest", str(master),
        ])
    elif vo:
        _run([
            "ffmpeg", "-y", "-i", str(silent_video), "-i", str(vo),
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
            "-shortest", str(master),
        ])
    elif music:
        _run([
            "ffmpeg", "-y", "-i", str(silent_video),
            "-stream_loop", "-1", "-i", str(music),
            "-map", "0:v", "-map", "1:a", "-t", str(total),
            "-c:v", "copy", "-c:a", "aac", "-af", "volume=0.35",
            "-shortest", str(master),
        ])
    else:
        # no audio available -> add silent track for platform compatibility
        _run([
            "ffmpeg", "-y", "-i", str(silent_video),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
            "-shortest", str(master),
        ])

    print(f"[assemble] master vlog -> {master}  ({total:.1f}s)")
    return master


if __name__ == "__main__":
    import datetime as _dt
    import sys

    sb = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        settings.output_dir / _dt.date.today().isoformat() / "storyboard.json"
    )
    assemble_vlog(sb)
