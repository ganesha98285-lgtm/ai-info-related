"""End-to-end daily pipeline for "Jon & Katie".

Runs the full flow:
  story -> voice -> video clips -> assemble master vlog -> cut shorts -> upload.

Usage:
  python -m src.pipeline --once                 # full run (uses .env config)
  python -m src.pipeline --once --no-upload      # build videos, skip posting
  python -m src.pipeline --theme "a snowy day"   # force a specific theme

In GitHub Actions, `--once` runs on the daily cron. By default this is
YouTube-only and publishes with YOUTUBE_PRIVACY (unlisted for safe testing).
Set SCHEDULE_TO_PEAK=true to instead schedule uploads to US peak times, and add
"meta" to UPLOAD_TARGETS once IG/FB is configured.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import settings
from src import (
    assemble,
    generate_script,
    generate_video,
    generate_voice,
    make_shorts,
    scheduler,
    upload_meta,
    upload_youtube,
)


def run_once(theme: str | None = None, do_upload: bool = True, shorts: int = 4) -> dict:
    settings.ensure_dirs()
    print("=" * 60)
    print(f"  {settings.channel_name} — daily pipeline")
    print("=" * 60)

    # 1) story
    storyboard = generate_script.generate_storyboard(theme)
    sb_path = generate_script.save_storyboard(storyboard)

    # 2) voice
    generate_voice.generate_voiceovers(sb_path)

    # 3) video clips
    generate_video.generate_clips(sb_path)

    # 4) assemble master vlog
    master = assemble.assemble_vlog(sb_path)

    # 5) shorts
    short_paths = make_shorts.make_shorts(sb_path, count=shorts)

    result = {
        "storyboard": str(sb_path),
        "master": str(master),
        "shorts": [str(s) for s in short_paths],
        "uploads": {},
    }

    if not do_upload:
        print("[pipeline] --no-upload set; skipping posting.")
        _write_summary(sb_path.parent, result)
        return result

    title = storyboard.get("title", settings.channel_name)
    desc = storyboard.get("description", "")
    tags = storyboard.get("hashtags", [])

    targets = settings.upload_target_list()
    print(f"[pipeline] upload targets = {targets} | "
          f"schedule_to_peak={settings.schedule_to_peak} | "
          f"youtube_privacy={settings.youtube_privacy}")

    # 6) upload — YouTube (default, and the only target for the first test).
    if "youtube" in targets:
        peak = settings.schedule_to_peak
        long_when = scheduler.long_vlog_publish_time() if peak else None
        yt_long = upload_youtube.upload_video(
            master, title, desc, tags,
            publish_at=long_when, made_for_kids=False,
            privacy=settings.youtube_privacy,
        )
        result["uploads"]["youtube_long"] = yt_long

        short_times = scheduler.shorts_publish_times(len(short_paths)) if peak else None
        result["uploads"]["shorts"] = []
        for i, sp in enumerate(short_paths):
            vid = upload_youtube.upload_video(
                sp, f"{title} #shorts", desc, tags + ["#shorts"],
                publish_at=(short_times[i] if short_times else None),
                made_for_kids=False, privacy=settings.youtube_privacy,
            )
            result["uploads"]["shorts"].append(vid)
    else:
        print("[pipeline] 'youtube' not in UPLOAD_TARGETS; skipping YouTube.")

    # Meta (IG/FB) — OFF by default. Enable later by adding "meta" to
    # UPLOAD_TARGETS. Needs a PUBLIC url for each short (see upload_meta.py).
    if "meta" in targets:
        caption = upload_meta.caption_from(title, tags)
        result["uploads"]["meta_caption"] = caption
        print("[pipeline] Meta enabled — ensure public video URLs are configured.")
    else:
        print("[pipeline] Meta disabled (YouTube-only). Add 'meta' to UPLOAD_TARGETS later.")

    _write_summary(sb_path.parent, result)
    print("[pipeline] ✅ done")
    return result


def _write_summary(date_dir: Path, result: dict) -> None:
    (date_dir / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), "utf-8"
    )
    print(f"[pipeline] summary -> {date_dir / 'summary.json'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Jon & Katie daily pipeline")
    ap.add_argument("--once", action="store_true", help="run one full daily cycle")
    ap.add_argument("--theme", default=None, help="force a story theme")
    ap.add_argument("--no-upload", action="store_true", help="build only, no posting")
    ap.add_argument("--shorts", type=int, default=4, help="number of teaser shorts")
    args = ap.parse_args()

    if args.once or True:  # default action is a single run
        run_once(theme=args.theme, do_upload=not args.no_upload, shorts=args.shorts)


if __name__ == "__main__":
    main()
