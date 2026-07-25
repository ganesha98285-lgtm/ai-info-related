"""Step 2 — Turn scene narration into a soft voiceover using edge-tts (free).

edge-tts uses Microsoft Edge's online TTS and needs NO API key. In "silent"
narration mode we skip TTS entirely (captions + music/ASMR carry the video).

Outputs one mp3 per scene in output/<date>/audio/ and returns their paths.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import os

from config import settings

# Faster, punchier delivery (edge-tts rate string, e.g. "+10%").
RATE = os.getenv("TTS_RATE", "+10%")


async def _synthesize(text: str, voice: str, out_path: Path) -> None:
    import edge_tts

    # Slightly faster delivery = punchier shorts, better retention.
    communicate = edge_tts.Communicate(text, voice, rate=RATE)
    await communicate.save(str(out_path))


def _trim_silence(path: Path) -> None:
    """Strip the leading/trailing silence edge-tts adds.

    This is what caused the ~1-2s dead pauses between lines in the published
    shorts: every clip carried its own silent head and tail.
    """
    import subprocess

    tmp = path.with_suffix(".trim.mp3")
    af = (
        # remove silence at the start, then reverse-trim the tail
        "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,"
        "areverse,"
        "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,"
        "areverse"
    )
    try:
        res = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(path), "-af", af,
             "-c:a", "libmp3lame", "-q:a", "4", str(tmp)],
            capture_output=True, text=True, timeout=120,
        )
        if res.returncode == 0 and tmp.exists() and tmp.stat().st_size > 1000:
            tmp.replace(path)
        else:
            tmp.unlink(missing_ok=True)
    except Exception as exc:
        print(f"[generate_voice] silence trim skipped ({exc})")


def generate_voiceovers(storyboard_path: Path) -> list[dict]:
    """Create a voiceover mp3 for each scene. Returns list of scene audio meta."""
    storyboard = json.loads(Path(storyboard_path).read_text("utf-8"))
    date_dir = Path(storyboard_path).parent
    audio_dir = date_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    silent = settings.narration_mode.lower() == "silent"

    for scene in storyboard.get("scenes", []):
        sid = scene["id"]
        line = (scene.get("narration") or "").strip()
        entry = {"id": sid, "audio": None, "text": line}
        if silent or not line:
            results.append(entry)
            continue
        out_path = audio_dir / f"scene_{sid:02d}.mp3"
        voice = settings.voice_for(scene.get("speaker"))  # Jon/Katie/narrator voice
        entry["speaker"] = scene.get("speaker")
        try:
            asyncio.run(_synthesize(line, voice, out_path))
            _trim_silence(out_path)
            entry["audio"] = str(out_path)
            print(f"[generate_voice] scene {sid} [{scene.get('speaker','narrator')}/{voice}] -> {out_path.name}")
        except Exception as exc:
            print(f"[generate_voice] scene {sid} TTS failed ({exc}); silent scene.")
        results.append(entry)

    meta_file = audio_dir / "voice_manifest.json"
    meta_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), "utf-8")
    return results


if __name__ == "__main__":
    import sys

    sb = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        settings.output_dir / __import__("datetime").date.today().isoformat()
        / "storyboard.json"
    )
    generate_voiceovers(sb)
