# 🛠️ Setup — AI Tool Drop (100% free, no GPU)

Everything runs on GitHub Actions. One-time setup, then it's hands-off.

## 1. Channel

- Name: **AI Tool Drop** (handle `@aitooldrop`)
- Description: `Daily AI tools, tips & hacks that save you hours. New short every day 🤖`
- Channel keywords: `ai tools, ai tips, chatgpt tips, ai for beginners, best ai apps, ai productivity`

## 2. Free keys → GitHub **Secrets**
(repo → Settings → Secrets and variables → Actions → *Secrets*)

| Secret | Where to get it (free) |
|--------|------------------------|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `PEXELS_API_KEY` | https://www.pexels.com/api/ (instant, free) |
| `PIXABAY_API_KEY` | https://pixabay.com/api/docs/ (optional fallback) |
| `YOUTUBE_TOKEN_JSON` | see below |

`YOUTUBE_TOKEN_JSON` format (values from your Google Cloud **Web** OAuth client
+ the refresh token from the OAuth Playground):

```json
{
  "token": "",
  "refresh_token": "1//0...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "....apps.googleusercontent.com",
  "client_secret": "GOCSPX-...",
  "scopes": ["https://www.googleapis.com/auth/youtube.upload"]
}
```

## 3. Optional tuning → GitHub **Variables**

| Variable | Default | Meaning |
|----------|---------|---------|
| `SHORTS_PER_DAY` | `2` | shorts published per day |
| `YOUTUBE_PRIVACY` | `public` | `unlisted` while testing |
| `SCHEDULE_TO_PEAK` | `true` | schedule to prime-time slots |
| `TTS_VOICE` | `en-US-GuyNeural` | try `en-US-AriaNeural`, `en-US-JennyNeural` |
| `CHANNEL_NAME` | `AI Tool Drop` | shown in logs/titles |
| `BRAND_HANDLE` | `@aitooldrop` | watermark burned into the video |

## 4. First run (safe test)

**Actions → “Daily AI Shorts — AI Tool Drop” → Run workflow** — defaults to
**1 short, unlisted, published immediately**, so you can review it in YouTube
Studio. The built mp4 is also attached to the run as an artifact.

## 5. Go live

Nothing to do — the daily cron (11:00 UTC) then builds and publishes
`SHORTS_PER_DAY` shorts at the prime-time slots. To publish publicly, set
Variable `YOUTUBE_PRIVACY=public`.

## 6. Optional polish

- Drop 1-2 royalty-free music tracks into `assets/audio/` (mp3) — they're mixed
  in automatically at low volume.
- Force a topic for a run with the `theme` input, e.g. `free ai tools for students`.

## Notes on monetization

Stock footage is combined with your **own script, voice, captions and edit**,
which is what YouTube expects for original content. Avoid publishing raw,
unedited stock compilations.
