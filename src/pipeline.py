"""End-to-end daily pipeline — faceless AI-tools Shorts ("AI Tool Drop").

Flow (all free, CPU-only, runs on GitHub Actions):
  script (Gemini) -> voice (edge-tts) -> real HD stock footage (Pexels/Pixabay)
  -> build vertical short (captions + hook + CTA + music) -> YouTube upload
  -> scheduled to US prime time (+ India night slots)

Usage:
  python -m src.pipeline --once                  # full daily run
  python -m src.pipeline --once --no-upload      # build only
  python -m src.pipeline --shorts 2              # how many shorts this run
  python -m src.pipeline --theme "free ai tools" # force today's angle
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import settings
from src import (
    build_short,
    generate_script,
    generate_voice,
    scheduler,
    upload_youtube,
)


def run_once(theme: str | None = None, do_upload: bool = True,
             shorts: int | None = None) -> dict:
    settings.ensure_dirs()
    count = shorts if shorts is not None else settings.shorts_per_day
    print("=" * 60)
    print(f"  {settings.channel_name} — daily AI shorts pipeline")
    print(f"  shorts this run: {count} | upload: {do_upload}")
    print("=" * 60)

    result: dict = {"shorts": [], "uploads": []}
    times = (scheduler.shorts_publish_times(count)
             if settings.schedule_to_peak else [None] * count)

    for i in range(1, count + 1):
        print(f"\n──── SHORT {i}/{count} ────", flush=True)

        # 1) script
        storyboard = generate_script.generate_storyboard(theme)
        sb_path = generate_script.save_storyboard(storyboard)
        if i > 1:  # keep each short's assets separate
            sb_path = _isolate(sb_path, i, storyboard)

        # 2) voice (one mp3 per line)
        generate_voice.generate_voiceovers(sb_path)

        # 3+4) stock footage + build the finished vertical short
        try:
            final = build_short.build_short(sb_path, index=i)
        except Exception as exc:
            print(f"[pipeline] short {i} failed: {exc}")
            continue
        result["shorts"].append(str(final))

        # 5) upload
        if do_upload:
            title = storyboard.get("title", settings.channel_name)
            if "#shorts" not in title.lower():
                title = f"{title} #shorts"
            vid = upload_youtube.upload_video(
                final, title,
                storyboard.get("description", ""),
                storyboard.get("hashtags", []) + storyboard.get("keywords", []),
                publish_at=times[i - 1],
                privacy=settings.youtube_privacy,
            )
            result["uploads"].append(vid)
        else:
            print("[pipeline] --no-upload set; skipping posting.")

        _write_summary(Path(sb_path).parent, result)

    print(f"\n[pipeline] ✅ done — {len(result['shorts'])} short(s) built")
    return result


def _isolate(sb_path: Path, index: int, storyboard: dict) -> Path:
    """Give short #index its own storyboard/audio folder inside the date dir."""
    sub = sb_path.parent / f"short_{index:02d}"
    sub.mkdir(parents=True, exist_ok=True)
    p = sub / "storyboard.json"
    p.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False), "utf-8")
    return p


def _write_summary(date_dir: Path, result: dict) -> None:
    (date_dir / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), "utf-8"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Tool Drop daily pipeline")
    ap.add_argument("--once", action="store_true", help="run one daily cycle")
    ap.add_argument("--theme", default=None, help="force today's angle")
    ap.add_argument("--no-upload", action="store_true", help="build only")
    ap.add_argument("--shorts", type=int, default=None,
                    help="number of shorts (default: SHORTS_PER_DAY)")
    args = ap.parse_args()
    run_once(theme=args.theme, do_upload=not args.no_upload, shorts=args.shorts)


if __name__ == "__main__":
    main()
