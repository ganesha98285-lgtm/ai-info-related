# 🐶🐱 Jon & Katie — Automated Daily Vlog Studio

A **100% free** pipeline that auto-generates a daily animated "day-in-the-life"
vlog for two cute characters — **Jon** (Labrador puppy) & **Katie** (Persian cat)
— cuts teaser Shorts from it, and auto-posts everything to **YouTube, Instagram
and Facebook** at the best US time zones.

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
   3. VIDEO      generate_video.py   │  LTX-2 / Kaggle free GPU (image-to-video,
                                     │                   character-consistent) → HD clips
                                     ▼
   4. ASSEMBLE   assemble.py         │  FFmpeg (free)  → full HD vlog (music+captions)
                                     ▼
   5. SHORTS     make_shorts.py      │  FFmpeg (free)  → 3-4 vertical 30s teasers
                                     ▼
   6. UPLOAD     upload_youtube.py   │  YouTube Data API   ┐
                 upload_meta.py      │  Meta Graph API     ├─ auto-post @ US peak time
                                     │  (IG Reels + FB)    ┘
                                     ▼
                            ✅ Posted everywhere
```

## 🆓 The Free Stack

| Stage | Tool | Cost | Notes |
|-------|------|------|-------|
| Script/story | Google Gemini API | Free tier | daily storyline + scene prompts |
| Character images | Gemini / Imagen | Free tier | one-time reference images |
| Voiceover | edge-tts | 100% free | no API key needed |
| ASMR/music | Freesound / royalty-free | Free | local library in `assets/audio` |
| Video generation | LTX-2 (open source) on Kaggle/Colab free GPU | Free | image-to-video, HD |
| Upscale to HD | Real-ESRGAN | Free | 1080p polish |
| Assembly / editing | FFmpeg | Free | stitch, captions, shorts |
| Upload YouTube | YouTube Data API v3 | Free | OAuth |
| Upload IG/FB | Meta Graph API | Free | business account |
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
│   └── image-prompts.md       # Gemini prompts for reference images
│   └── refs/                  # <- put your chosen reference images here
├── content/
│   └── daily-vlog-format.md   # daily story structure
├── src/
│   ├── generate_script.py
│   ├── generate_voice.py
│   ├── generate_video.py
│   ├── assemble.py
│   ├── make_shorts.py
│   ├── upload_youtube.py
│   ├── upload_meta.py
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
4. Run one day locally: `python -m src.pipeline --once`
5. Push to GitHub, add secrets, and the daily workflow takes over.

> ⚠️ **Honest note:** free GPU time (Kaggle ~30h/week) means we target **1 short
> HD vlog (3-5 min) + 3-4 teaser shorts per day** — not a 30-min video. This is
> the realistic sweet spot for daily free automation and fast channel growth.
