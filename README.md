# 🐶🐱 Jon & Katie — Automated Daily Vlog Studio

> **Best Friends. Big Adventures.**

A **100% free** pipeline that auto-generates a daily animated "day-in-the-life"
vlog for two cute characters — **Jon** (Labrador puppy 🐶) & **Katie** (Persian
cat 🐱) — cuts teaser Shorts from it, and auto-posts to **YouTube** (Instagram &
Facebook can be added later) at the best US time zones.

> 🎬 **First run is YouTube-only and uploads *unlisted*** so you can review each
> video before it goes public. Flip two settings to go public + auto-scheduled.

## 🧱 Architecture (the daily flow)

```
                 ┌─────────────────────────────────────────┐
                 │  GitHub Actions (daily cron, US time)     │
                 └───────────────────┬─────────────────────┘
                                     │
   1. STORY      generate_script.py  │  Gemini (free)  → today's vlog script,
                                     │                   scene prompts, captions
                                     ▼
   2. VOICE      generate_voice.py   │  edge-tts (free) → soft narration audio
                                     ▼
   3. VIDEO      generate_video.py   │  stub Ken-Burns (free) OR LTX-2 on Kaggle
                                     │                   free GPU → HD clips
                                     ▼
   4. ASSEMBLE   assemble.py         │  FFmpeg (free)  → full HD vlog (music+captions)
                                     ▼
   5. SHORTS     make_shorts.py      │  FFmpeg (free)  → 3-4 vertical 30s teasers
                                     │                   (no crop — blurred fit)
                                     ▼
   6. UPLOAD     upload_youtube.py   │  YouTube Data API → auto-post (unlisted test
                 (upload_meta.py)    │  or public @ US peak). Meta = optional later
                                     ▼
                            ✅ Posted to YouTube
```

## 🆓 The Free Stack

| Stage | Tool | Cost | Notes |
|-------|------|------|-------|
| Script/story | Google Gemini API | Free tier | daily storyline + scene prompts |
| Character images | Gemini / Imagen | Free tier | one-time reference images |
| Voiceover | edge-tts | 100% free | no API key needed |
| ASMR/music | Freesound / royalty-free | Free | local library in `assets/audio` |
| Video generation | stub (FFmpeg) or LTX-2 on Kaggle/Colab free GPU | Free | image-to-video, HD |
| Assembly / editing | FFmpeg | Free | stitch, captions, shorts |
| Upload YouTube | YouTube Data API v3 | Free | OAuth |
| Upload IG/FB (optional) | Meta Graph API | Free | business account, add later |
| Orchestration | GitHub Actions | Free | daily cron |

## 📁 Project Structure

```
jab-ketty-met-john/
├── README.md
├── requirements.txt
├── .env.example
├── config.py                 # central config (reads env vars)
├── characters/
│   ├── character-bible.md     # single source of truth for both characters
│   ├── image-prompts.md       # Gemini prompts for reference images
│   └── refs/                  # <- put jon.png and katie.png here
├── content/
│   └── daily-vlog-format.md   # daily story structure
├── src/
│   ├── generate_script.py
│   ├── generate_voice.py
│   ├── generate_video.py
│   ├── assemble.py
│   ├── make_shorts.py
│   ├── upload_youtube.py
│   ├── upload_meta.py         # optional IG/FB (off by default)
│   ├── scheduler.py           # US peak-time logic
│   └── pipeline.py            # runs the whole daily flow
├── assets/
│   └── audio/                 # royalty-free music + ASMR sfx
├── output/                    # generated videos land here
└── .github/workflows/daily.yml
```

## 🚀 Quick start

1. Generate the two reference images (see `characters/image-prompts.md`) and drop
   them in `characters/refs/` as `jon.png` and `katie.png`.
2. Copy `.env.example` → `.env` and fill in your free API keys.
3. `pip install -r requirements.txt`
4. Run one day locally: `python -m src.pipeline --once --no-upload`
5. Push to GitHub, add secrets, and run the workflow (see `docs/setup.md`).

> ⚠️ **Honest note:** free GPU time (Kaggle ~30h/week) means we target **1 short
> HD vlog (3-5 min) + 3-4 teaser shorts per day** — not a 30-min video. This is
> the realistic sweet spot for daily free automation and fast channel growth.
> The default `stub` backend animates your reference images (moving photo / Ken
> Burns), not full cartoon motion — upgrade to the `kaggle` LTX-2 backend for
> real image-to-video HD. See `docs/setup.md` and `docs/kaggle.md`.
