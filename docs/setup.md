# 🛠️ Setup Guide — Jab Katie Met Jon (100% free)

Follow once, then it runs itself daily via GitHub Actions.

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

## 2. Free API keys

| Secret | Where to get it (free) |
|--------|------------------------|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `YOUTUBE_CLIENT_SECRET_JSON` | Google Cloud → enable *YouTube Data API v3* → OAuth client (Desktop) |
| `YOUTUBE_TOKEN_JSON` | run `python -m src.upload_youtube` locally once to authorize; copy `secrets/youtube_token.json` |
| `META_ACCESS_TOKEN`, `META_IG_USER_ID`, `META_FB_PAGE_ID` | Meta Business + Graph API (IG must be Business/Creator linked to a FB Page) |
| `KAGGLE_USERNAME`, `KAGGLE_KEY` | kaggle.com → Account → Create API Token (only for the `kaggle` HD backend) |

Add these under **GitHub repo → Settings → Secrets and variables → Actions**.
Non-secret tuning (voice, timezone, backend) go under **Variables**:
`TTS_VOICE`, `NARRATION_MODE`, `VIDEO_BACKEND`, `TARGET_TIMEZONE`, `KAGGLE_KERNEL_SLUG`.

## 3. Turn on the daily automation

The workflow `.github/workflows/daily.yml` runs every day at 12:00 UTC and can
be triggered manually from the **Actions** tab (with an optional theme).

## 4. Quality ladder (free)

- **Start:** `VIDEO_BACKEND=stub` — cute Ken-Burns animation of your characters.
- **Upgrade (free HD):** `VIDEO_BACKEND=kaggle` — real LTX-2 image-to-video on
  Kaggle's free GPU. See `docs/kaggle.md`.

> Honest note: free GPU time (~30h/week) is best spent on **1 short HD vlog +
> 3-4 teaser shorts per day**. That's the daily target this repo is tuned for.
