# ⚡ Lightning AI — talking Jon & Katie, straight to YouTube

Goal: Jon & Katie actually **talking with lip-sync**, rendered on a Lightning AI
GPU, published to YouTube by the same command. No files to download, no manual
review step — if you don't like the result, delete it in YouTube Studio.

## Credits: what one 30-second short really costs

Lightning shows a **per-hour** rate. We only use a fraction of an hour, so
`cost = rate × time`.

| GPU | Rate/hour | Time for one short | **Cost per short** | Shorts from 15 credits |
|-----|-----------|--------------------|--------------------|------------------------|
| T4 (16 GB) | 0.55 | ~3 h (model doesn't fit well) | ❌ ~1.71 | ~8 |
| L4 (24 GB) | 1.11 | ~42 min | ~0.78 | ~19 |
| A100 (40 GB) | 3.32 | ~19 min | ~1.06 | ~14 |
| **H100 (80 GB)** | 3.82 | **~12 min** | **~0.76** | **~19** |

**H100 wins**: same cost as the cheap options but ~3.5× faster, and it has
80 GB so the 14B model runs without slow CPU offloading.

Two one-time costs to know about:

* Moving the Studio from AWS to Lightning cloud (needed for H100): **~1.01 credits**
* First model download (~40–60 GB): billed GPU time, roughly **1.5–2.5 credits**
  on H100. Cached afterwards — **keep the Studio alive** and later runs skip it.

No card on file means it can never charge you; when credits run out it stops.

## Setup (once)

1. In the Studio, pick **H100**, turn **Interruptible** on, click **Request**
   (confirm the cloud move).
2. Open the **Terminal** and clone the repo:

   ```bash
   git clone https://github.com/ganesha98285-lgtm/jab-ketty-met-john
   cd jab-ketty-met-john
   sudo apt-get install -y ffmpeg      # only if ffmpeg is missing
   ```

3. Give it your YouTube token — the **same JSON** you put in GitHub Secrets as
   `YOUTUBE_TOKEN_JSON`:

   ```bash
   export YOUTUBE_TOKEN_JSON='{"token":"","refresh_token":"...","token_uri":"https://oauth2.googleapis.com/token","client_id":"...","client_secret":"...","scopes":["https://www.googleapis.com/auth/youtube.upload"]}'
   ```

   (Or create the file `secrets/youtube_token.json` with that JSON.)

## Run it — builds and publishes in one command

```bash
python lightning/talking_short.py
```

Flags:

| Flag | Effect |
|------|--------|
| `--scenes 4` | fewer lines → cheaper and faster |
| `--privacy unlisted` | publish quietly instead of public |
| `--steps 20` | fewer diffusion steps → faster, slightly softer |
| `--dry-run` | build the mp4 but skip the upload |

## What it does

1. **Pre-flight** — checks ffmpeg, the YouTube token and the reference images
   **before** touching the GPU, so a setup mistake never burns credits.
2. Picks the day's dialogue (rotates daily), hook first, CTA last.
3. `edge-tts` voices each line — Jon male, Katie female — and trims the silence
   that used to cause 1–2 s dead pauses.
4. **Wan2.2 S2V-14B** animates the speaker's reference image *driven by that
   audio* → real lip-sync, not a slideshow.
5. Each clip is fitted to 1080×1920 (nothing cropped), gets a speech bubble.
6. Clips joined; yellow hook burned on the first 3 s, SUBSCRIBE CTA on the last 3 s.
7. **Quality gate** (size / duration / not-blank) → upload + custom thumbnail.
   If the gate fails, nothing is published.

## Honest limitations

* Audio-driven avatar models are trained mostly on **human** faces. Jon is a
  puppy and Katie is a cat, so mouth movement can look off. That is a model
  limitation, not a settings bug — judge the first upload with your own eyes.
* Interruptible machines are 50–80 % cheaper but can be reclaimed mid-run. If
  that happens, re-run the command (weights stay cached).
* The daily stock-footage shorts pipeline on GitHub Actions still costs **0
  credits** and is unaffected by any of this.

## `talking_test.py` (optional)

A cheaper single-clip probe (`--mode i2v` uses the light 5B model,
`--mode s2v` the heavy lip-sync one). Useful only if you want to sanity-check
quality before spending credits on a full short.
