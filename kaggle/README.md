# 🎬 Real HD motion video on Kaggle's FREE GPU (LTX-Video)

GitHub Actions has **no GPU**, so the real image-to-video generation runs on
**Kaggle's free GPU** (T4, ~30 GPU-hours/week). This turns each scene image into
an actual **motion clip** (not a slideshow) using the open-source **LTX-Video**
model, then assembles shorts and uploads them to YouTube.

> Honest note: this produces real animated **motion + camera moves**. It does
> **not** do reliable two-character **lip-synced dialogue** — no free (or even
> paid) tool does that consistently yet.

## One-time setup (all free)

1. **Create a Kaggle account** at kaggle.com and **verify your phone**
   (Settings → Phone verification). Phone verification is required to enable
   the free GPU + internet in notebooks.

2. **New Notebook** → in the right-hand **Settings** panel:
   - **Accelerator:** `GPU T4 x2` (or P100)
   - **Internet:** `On`

3. **Add your keys as Secrets** (Add-ons → Secrets → Add secret):
   - `GEMINI_API_KEY` = your Gemini key
   - `YOUTUBE_TOKEN_JSON` = the exact JSON you put in the GitHub `YOUTUBE_TOKEN_JSON`
     secret (contains refresh_token + client_id + client_secret)

4. **Paste** the contents of `kaggle/notebook.py` into the first cell.

5. **Run All.** First run downloads the model (a few minutes), then generates a
   real motion clip per scene, builds the short(s), and uploads to YouTube.

## Go daily (hands-off)

- In the notebook, click **Schedule a run** (Kaggle lets you run a notebook
  automatically, e.g. once a day). That makes the whole thing daily + free.
- Once the first 1-short test looks good, edit the notebook config:
  - `SHORTS_PER_DAY = "6"`
  - `SCHEDULE_TO_PEAK = "true"`  (schedules 4 USA + 2 India-night slots)

## Speed / quota tips

- Each ~4-second clip takes roughly 1-3 min on a T4. 8 scenes ≈ 15-25 min/run,
  which fits comfortably in the weekly free quota for one video per day.
- Lower `num_inference_steps` in `src/backends/ltx_generate.py` for faster (but
  slightly lower quality) clips; raise it for more polish.
- Resolution is set to 768×512 for speed; you can raise it if you have time/quota.
