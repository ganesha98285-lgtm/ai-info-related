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
    history,
    scheduler,
    stock,
    thumbnail,
    upload_youtube,
)
from src.backends import modal_video


def run_once(theme: str | None = None, do_upload: bool = True,
             shorts: int | None = None) -> dict:
    settings.ensure_dirs()
    count = shorts if shorts is not None else settings.shorts_per_day
    print("=" * 60)
    print(f"  {settings.channel_name} — daily AI shorts pipeline")
    print(f"  shorts this run: {count} | upload: {do_upload}")
    print("=" * 60)

    # PRE-FLIGHT: refuse to run at all if we can't fetch real footage.
    if not stock.have_keys() and not modal_video.available():
        raise SystemExit(
            "\n[pipeline] ABORT: no footage source configured.\n"
            "  Set the GitHub secret PEXELS_API_KEY (free: pexels.com/api)\n"
            "  and/or PIXABAY_API_KEY. Without it every video would be blank,\n"
            "  so nothing will be built or uploaded.\n"
        )

    # LIFELONG MEMORY: everything ever published, so nothing repeats.
    hist = history.load()
    print(f"[pipeline] memory: {history.stats(hist)}")
    # LEARNING: refresh view counts so the writer knows which style performed
    # best (style is reused, ideas never are).
    if do_upload:
        history.refresh_stats(hist)
        if best := history.top_performers(hist, 3):
            print("[pipeline] top performers so far:")
            for u in best:
                print(f"          {u['views']:>7} views — {u['title'][:60]}")

    result: dict = {"shorts": [], "uploads": []}
    failures = 0
    times = (scheduler.shorts_publish_times(count)
             if settings.schedule_to_peak else [None] * count)

    for i in range(1, count + 1):
        print(f"\n──── SHORT {i}/{count} ────", flush=True)

        # 1) script — checked against the whole channel history before use
        storyboard = generate_script.generate_storyboard(theme, data=hist)
        history.record_storyboard(storyboard, hist)  # claim it immediately
        sb_path = generate_script.save_storyboard(storyboard)
        if i > 1:  # keep each short's assets separate
            sb_path = _isolate(sb_path, i, storyboard)

        # 2) voice (one mp3 per line)
        generate_voice.generate_voiceovers(sb_path)

        # 3+4) stock footage + build the finished vertical short
        try:
            final = build_short.build_short(sb_path, index=i, hist=hist)
        except Exception as exc:
            print(f"[pipeline] short {i} failed: {exc}")
            failures += 1
            continue
        result["shorts"].append(str(final))

        # 4b) QUALITY GATE — never publish a blank/broken video
        ok, why = build_short.validate_video(final)
        print(f"[pipeline] quality check: {why}")
        if not ok:
            print(f"[pipeline] ❌ short {i} rejected ({why}); not uploading.")
            failures += 1
            continue

        # 5) upload (scheduled to the US evening → late-night windows)
        if do_upload:
            title = storyboard.get("title", settings.channel_name)
            if "#shorts" not in title.lower():
                title = f"{title} #shorts"
            when = times[i - 1]
            vid = upload_youtube.upload_video(
                final, title,
                storyboard.get("description", ""),
                storyboard.get("hashtags", []) + storyboard.get("keywords", []),
                publish_at=when,
                privacy=settings.youtube_privacy,
            )
            if vid == "QUOTA_EXCEEDED":
                print("[pipeline] stopping early: YouTube daily quota reached.")
                break
            result["uploads"].append(vid)

            # Viral thumbnail from a real frame + the hook text. The layout and
            # palette come from the least-used combination, so no two thumbnails
            # on the channel look alike.
            if vid:
                history.record_upload(vid, storyboard, hist)
                hook_caption = next(
                    (s.get("caption") for s in storyboard.get("scenes", [])
                     if s.get("role") == "hook"),
                    storyboard.get("title", ""),
                )
                style = history.next_thumb_style(
                    hist, len(thumbnail.LAYOUTS), len(thumbnail.PALETTES)
                )
                thumb = thumbnail.make_thumbnail(
                    final, hook_caption,
                    Path(sb_path).parent / f"thumb_{i:02d}.jpg", style=style,
                )
                if thumb:
                    upload_youtube.set_thumbnail(vid, thumb)
            if when:
                print(f"[pipeline] scheduled for {when.strftime('%a %I:%M %p %Z')}")

            # 6) housekeeping — remove the uploaded video + cached footage
            if vid and settings.cleanup_after_upload:
                build_short.cleanup_short(final, Path(sb_path).parent)
        else:
            print("[pipeline] --no-upload set; skipping posting.")

        # Persist memory after every short so a crash never loses what was used.
        history.save(hist)
        _write_summary(Path(sb_path).parent, result)

    # Channel banner (generated once per run; upload it in YouTube Studio).
    try:
        banner = thumbnail.make_banner(settings.output_dir / "channel_banner.jpg")
        if banner:
            result["banner"] = str(banner)
    except Exception as exc:
        print(f"[pipeline] banner generation skipped ({exc})")

    hist_file = history.save(hist)
    print(f"[pipeline] memory saved -> {hist_file} ({history.stats(hist)})")

    built = len(result["shorts"])
    print(f"\n[pipeline] done — {built} built, {failures} rejected/failed")
    if built == 0:
        raise SystemExit(
            "[pipeline] ABORT: no valid short was produced (nothing uploaded)."
        )
    print("[pipeline] ✅ success")
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
