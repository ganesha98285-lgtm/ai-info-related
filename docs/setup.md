# 🛠️ Setup Guide — Jon & Katie (100% free, YouTube-first)

Follow once, then it runs itself daily via GitHub Actions. The first test is
**YouTube-only** and uploads **unlisted** so you can review before going public.
Instagram/Facebook can be attached later.

## 0. Try it locally first (zero keys needed)

```bash
pip install -r requirements.txt
sudo apt-get install -y ffmpeg      # or: brew install ffmpeg
python -m src.pipeline --once --no-upload
```

With `VIDEO_BACKEND=stub` (the default) this builds a full master vlog + shorts
using placeholder animation from your reference images — proving the whole
pipeline end-to-end for free. Output lands in `output/<date>/`.

## 1. Character reference images (one time)

1. Open `characters/image-prompts.md`, paste the JON and KATIE prompts into
   Gemini / Imagen, generate, and pick your favourites.
2. Save them as `characters/refs/jon.png` and `characters/refs/katie.png`.

## 2. Free API keys (YouTube-only to start)

| Secret | Where to get it (free) |
|--------|------------------------|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `YOUTUBE_CLIENT_SECRET_JSON` | Google Cloud → enable *YouTube Data API v3* → OAuth client (Desktop) |
| `YOUTUBE_TOKEN_JSON` | run `python -m src.upload_youtube` locally once to authorize; copy `secrets/youtube_token.json` |

> Instagram/Facebook (`META_*`) and Kaggle (`KAGGLE_*`) are NOT needed for the
> first YouTube test — add them later.

Add these under **GitHub repo → Settings → Secrets and variables → Actions**.
Non-secret tuning goes under **Variables**:

| Variable | Test value | Meaning |
|----------|-----------|---------|
| `VIDEO_BACKEND` | `stub` | cute Ken-Burns animation (upgrade to `kaggle` later) |
| `UPLOAD_TARGETS` | `youtube` | YouTube only (add `meta` later for IG/FB) |
| `YOUTUBE_PRIVACY` | `unlisted` | review via link before making public |
| `SCHEDULE_TO_PEAK` | `false` | publish immediately for testing (set `true` for US peak scheduling) |
| `TTS_VOICE` | `en-US-AriaNeural` | narration voice |
| `NARRATION_MODE` | `narrate` | or `silent` |
| `TARGET_TIMEZONE` | `America/New_York` | used when SCHEDULE_TO_PEAK=true |

## 3. Run the first test

Repo → **Actions** tab → **"Daily Vlog — Jon & Katie"** → **Run workflow**.
It builds the video and uploads it **unlisted** to your channel — open the link
from the run logs / your YouTube Studio to review it.

Once happy, set `YOUTUBE_PRIVACY=public` (and optionally `SCHEDULE_TO_PEAK=true`)
and it will publish daily on the 12:00 UTC cron.

## 4. Quality ladder (free)

- **Start:** `VIDEO_BACKEND=stub` — cute Ken-Burns animation of your characters.
- **Upgrade (free HD):** `VIDEO_BACKEND=kaggle` — real LTX-2 image-to-video on
  Kaggle's free GPU. See `docs/kaggle.md`.

> Honest note: free GPU time (~30h/week) is best spent on **1 short HD vlog +
> 3-4 teaser shorts per day**. That's the daily target this repo is tuned for.
