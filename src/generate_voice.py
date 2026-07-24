"""Step 2 — Turn scene narration into a soft voiceover using edge-tts (free).

edge-tts uses Microsoft Edge's online TTS and needs NO API key. In "silent"
narration mode we skip TTS entirely (captions + music/ASMR carry the video).

Outputs one mp3 per scene in output/<date>/audio/ and returns their paths.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from config import settings


async def _synthesize(text: str, voice: str, out_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


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
        try:
            asyncio.run(_synthesize(line, settings.tts_voice, out_path))
            entry["audio"] = str(out_path)
            print(f"[generate_voice] scene {sid} -> {out_path.name}")
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
