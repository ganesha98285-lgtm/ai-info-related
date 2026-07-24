"""End-to-end daily pipeline for "Jon & Katie".

Runs the full flow:
  story -> voice -> video clips -> assemble master vlog -> cut shorts -> upload.

Shorts-only for now: we build the master vlog (needed to cut shorts from) but
only publish the SHORTS — 6/day, 4 to USA prime time + 2 to India night. The
long-form vlog is added later once the channel's reach grows (SHORTS_ONLY).

Usage:
  python -m src.pipeline --once                 # full run (uses .env config)
  python -m src.pipeline --once --no-upload      # build videos, skip posting
  python -m src.pipeline --theme "a snowy day"   # force a specific theme

In GitHub Actions, `--once` runs on the daily cron. When SCHEDULE_TO_PEAK=true,
uploads schedule themselves to prime times (YouTube via publishAt).
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


def run_once(theme: str | None = None, do_upload: bool = True,
             shorts: int | None = None) -> dict:
    settings.ensure_dirs()
    shorts = shorts if shorts is not None else settings.shorts_per_day
    print("=" * 60)
    print(f"  {settings.channel_name} — daily pipeline")
    print(f"  mode: {'SHORTS-ONLY' if settings.shorts_only else 'vlog + shorts'} | "
          f"shorts/day: {shorts}")
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

        # Long-form vlog: SKIPPED while shorts-only (added later once reach grows).
        if not settings.shorts_only:
            long_when = scheduler.long_vlog_publish_time() if settings.schedule_to_peak else None
            yt_long = upload_youtube.upload_video(
                master, title, desc, tags,
                publish_at=long_when, privacy=settings.youtube_privacy,
            )
            result["uploads"]["youtube_long"] = yt_long
        else:
            print("[pipeline] shorts-only mode: long vlog built but NOT uploaded "
                  "(long video comes later once reach grows).")

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
    ap = argparse.ArgumentParser(description="Jon & Katie daily pipeline")
    ap.add_argument("--once", action="store_true", help="run one full daily cycle")
    ap.add_argument("--theme", default=None, help="force a story theme")
    ap.add_argument("--no-upload", action="store_true", help="build only, no posting")
    ap.add_argument("--shorts", type=int, default=None,
                    help="number of teaser shorts (default: SHORTS_PER_DAY)")
    args = ap.parse_args()

    if args.once or True:  # default action is a single run
        run_once(theme=args.theme, do_upload=not args.no_upload, shorts=args.shorts)


if __name__ == "__main__":
    main()
