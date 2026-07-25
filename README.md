# 🤖 AI Tool Drop — Automated Daily AI Shorts

A **100% free, GPU-free** pipeline that builds and publishes daily faceless
YouTube Shorts about **AI tools, tips and hacks** for a **US audience** — and
runs entirely on **GitHub Actions**.

Videos look like *proper* videos because every beat is **real HD stock footage**
(Pexels/Pixabay free APIs), not AI mush and not a slideshow.

## 🧱 The daily flow

```
GitHub Actions (daily cron)
   │
   1. SCRIPT   generate_script.py  Gemini (free) → hook + 4-6 value beats + CTA
   │                               + viral title, SEO description, hashtags
   2. VOICE    generate_voice.py   edge-tts (free) → narration per line
   3. FOOTAGE  stock.py            Pexels / Pixabay (free) → real HD clips
   4. BUILD    build_short.py      FFmpeg → 1080x1920 short: footage + bold
   │                               captions + hook (0-3s) + FOLLOW CTA (last 3s)
   │                               + background music
   5. UPLOAD   upload_youtube.py   YouTube Data API → auto-post
   6. TIMING   scheduler.py        US prime time (+ India night slots)
```

## 🆓 Free stack

| Stage | Tool | Cost |
|-------|------|------|
| Script + SEO | Google Gemini | free tier |
| Voiceover | edge-tts | free, no key |
| HD footage | Pexels + Pixabay APIs | free |
| Editing / render | FFmpeg | free |
| Upload + schedule | YouTube Data API v3 | free |
| Orchestration | GitHub Actions | free (no GPU needed) |

## ⏰ Publishing schedule

6 slots/day are available (`scheduler.py`), tuned for a US-first audience:

- **USA (America/New_York):** 6:00 PM, 8:00 PM, 10:00 PM, 11:30 PM
- **India (Asia/Kolkata):** 9:00 PM, 9:45 PM

`SHORTS_PER_DAY` decides how many are used (default 2).

## 🚀 Setup (see `docs/setup.md`)

1. Add GitHub secrets: `GEMINI_API_KEY`, `PEXELS_API_KEY`, `YOUTUBE_TOKEN_JSON`.
2. **Actions → Daily AI Shorts → Run workflow** (defaults to 1 *unlisted* short
   so you can review it).
3. Happy with it? Leave the cron on — it publishes daily at prime time.

## 📁 Structure

```
config.py                 central config (env vars)
src/generate_script.py    AI-niche script + hook + SEO
src/generate_voice.py     edge-tts narration
src/stock.py              free HD stock footage (Pexels/Pixabay)
src/build_short.py        FFmpeg → finished 9:16 short
src/captions.py           bold captions, hook + CTA overlays
src/scheduler.py          US/India prime-time slots
src/upload_youtube.py     YouTube upload (+ scheduled publish)
src/pipeline.py           runs the whole daily flow
.github/workflows/daily.yml
```

> Note: the earlier Jon & Katie cartoon experiment (LTX/puppet) is kept in
> `src/backends/` and `characters/` for reference, but the active format is the
> AI-tools shorts above — it's the one that is genuinely free, automatic, HD,
> and viable for US growth.
