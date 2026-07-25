# ⚡ Lightning AI — talking characters on a free GPU (no credit card)

Goal: Jon & Katie actually **talking with lip-sync**, generated on a free cloud
GPU, with **no card on file**.

## Cost & capacity (honest)

| Item | Reality |
|------|---------|
| Card required | **No** — phone verification only |
| Free GPU time | ~**20-80 hours/month** depending on the current plan |
| Can it charge you? | **No card = no charge.** When hours run out it just stops |
| Talking clip (5s, S2V-14B) | ~3-8 min of GPU |
| One 30s short (≈6 clips) | ~25-45 min of GPU |
| So per month | ≈ **1-3 talking shorts/day** |

Everything else (script, voices, captions, hooks, upload, scheduling) already
runs free on GitHub Actions — the GPU is only needed for the talking clips.

## Step 1 — make ONE test clip first (do this before any automation)

1. Sign up at [lightning.ai](https://lightning.ai) → verify your phone. No card.
2. Create a **Studio** → in the machine selector pick a **GPU** (T4/L4/A10G).
3. Open the Studio **terminal** (in the browser) and run:

   ```bash
   git clone https://github.com/ganesha98285-lgtm/jab-ketty-met-john
   cd jab-ketty-met-john

   # fast sanity check — motion only, no lip-sync (light 5B model)
   python lightning/talking_test.py --mode i2v

   # the real thing — audio-driven LIP-SYNC (heavy 14B model)
   python lightning/talking_test.py --mode s2v
   ```

4. Download `talking_test_i2v.mp4` / `talking_test_s2v.mp4` from the Lightning
   file browser and **watch it**.

**Then tell me what you saw.** If the quality is good we wire it into the daily
pipeline. If it looks bad, we stop there — no more wasted hours.

## What the test does

- Clones the official [Wan2.2](https://github.com/Wan-Video/Wan2.2) repo.
- `--mode i2v` → **Wan2.2-TI2V-5B**: light model, validates motion + speed.
- `--mode s2v` → **Wan2.2-S2V-14B**: audio-driven talking model (real lip-sync).
- Uses your existing `characters/refs/jon.png` (or `sheet.png`) as the character
  and generates Jon's voice line with free `edge-tts`.
- Runs with `--offload_model --convert_model_dtype --t5_cpu` so it also fits
  smaller GPUs (slower, but it fits).

## Known risks (so there are no surprises)

- **Big download:** S2V-14B weights are tens of GB. First run is slow; the Studio
  keeps them cached for later runs.
- **Animal faces:** these models are trained mostly on humans. On a cartoon
  puppy/cat face the lip-sync may look off — that is the #1 thing to judge in
  the test clip.
- **Untested by me:** I have no GPU/account here, so the first run may need one
  or two fixes. Send me the error text and I'll patch it.

## Step 2 — automation (only after the test looks good)

Once you approve the quality, the daily flow becomes:

```
GitHub Actions (free)            Lightning GPU (free hours)
  script + voices + SEO   ──►    talking clips (lip-sync)
        ▲                              │
        └──── captions, hooks, assembly, YouTube upload ◄──┘
```

I'll add a `lightning/daily_job.py` that runs the whole batch on the GPU box and
uploads straight to YouTube, plus a scheduled trigger — so you don't touch a
terminal daily.
