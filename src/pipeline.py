"""End-to-end daily pipeline for "Jab Katie Met Jon".

Runs the full flow:
  story -> voice -> video clips -> assemble master vlog -> cut shorts -> upload.

Usage:
  python -m src.pipeline --once                 # full run (uses .env config)
  python -m src.pipeline --once --no-upload      # build videos, skip posting
  python -m src.pipeline --theme "a snowy day"   # force a specific theme

In GitHub Actions, `--once` runs on the daily cron. Uploads schedule themselves
to US peak times (YouTube via publishAt; Meta via the cron timing).
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

    targets = [t.strip().lower() for t in settings.upload_targets.split(",") if t.strip()]
    print(f"[pipeline] upload targets = {targets}")

    # 6) upload — YouTube (only platform enabled for now).
    if "youtube" in targets:
        # When scheduling to peak: private + publishAt. Else: publish now with
        # the configured privacy (unlisted is the safe default for testing).
        long_when = scheduler.long_vlog_publish_time() if settings.schedule_to_peak else None
        yt_long = upload_youtube.upload_video(
            master, title, desc, tags,
            publish_at=long_when, privacy=settings.youtube_privacy,
        )
        result["uploads"]["youtube_long"] = yt_long

        short_times = (
            scheduler.shorts_publish_times(len(short_paths))
            if settings.schedule_to_peak else [None] * len(short_paths)
        )
        result["uploads"]["shorts"] = []
        for i, sp in enumerate(short_paths):
            vid = upload_youtube.upload_video(
                sp, f"{title} #shorts", desc, tags + ["#shorts"],
                publish_at=short_times[i], privacy=settings.youtube_privacy,
            )
            result["uploads"]["shorts"].append(vid)

    # Meta (Instagram / Facebook) — disabled until added to UPLOAD_TARGETS.
    if any(t in targets for t in ("meta", "instagram", "facebook")):
        result["uploads"]["meta_caption"] = upload_meta.caption_from(title, tags)

    _write_summary(sb_path.parent, result)
    print("[pipeline] ✅ done")
    return result


def _write_summary(date_dir: Path, result: dict) -> None:
    (date_dir / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), "utf-8"
    )
    print(f"[pipeline] summary -> {date_dir / 'summary.json'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Jab Katie Met Jon daily pipeline")
    ap.add_argument("--once", action="store_true", help="run one full daily cycle")
    ap.add_argument("--theme", default=None, help="force a story theme")
    ap.add_argument("--no-upload", action="store_true", help="build only, no posting")
    ap.add_argument("--shorts", type=int, default=4, help="number of teaser shorts")
    args = ap.parse_args()

    if args.once or True:  # default action is a single run
        run_once(theme=args.theme, do_upload=not args.no_upload, shorts=args.shorts)


if __name__ == "__main__":
    main()
