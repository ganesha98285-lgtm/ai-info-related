# ⚡ Optional: AI b-roll on Modal's free GPU credits

Stock footage is the reliable daily engine. If you also want **AI-generated
cinematic b-roll**, Modal gives **$30 of free compute every month** (renews
monthly, no card required) with real GPUs and a proper API — so it can be driven
straight from GitHub Actions, unlike notebook services.

## Cost reality (so credits last)

| GPU | Rate | 3s clip | Shorts/day inside free credits |
|-----|------|---------|-------------------------------|
| L4 | ~$0.80/hr | ~$0.01-0.02 | **~2-3 fully AI shorts/day** |

Beyond that the pipeline just uses stock footage, so nothing breaks.

## One-time setup (10 min)

1. **Sign up** at [modal.com](https://modal.com) (free, Google login).
2. On your laptop:
   ```bash
   pip install modal
   modal setup                 # opens browser, links the account
   modal deploy modal_app.py   # deploys the GPU video generator
   ```
   Test it:
   ```bash
   modal run modal_app.py      # writes modal_test_clip.mp4
   ```
3. Create an API token: Modal dashboard → **Settings → API Tokens → New token**.
4. Add to **GitHub → Settings → Secrets → Actions**:
   - `MODAL_TOKEN_ID`
   - `MODAL_TOKEN_SECRET`
5. Turn it on: **Variables** → `AI_BROLL` = `true`.

## How it behaves

- For every scene the pipeline first asks Modal for an AI clip.
- If Modal is off, out of credits, or errors → it silently uses **stock footage**.
- Blank videos are impossible: a short is rejected before upload unless most
  scenes have real footage and the final file passes a blank-frame check.

## Tuning

`modal_app.py` → `generate_clip()`:
- `steps` (default 30): higher = better, slower, more credits.
- `width/height` (default 704x1280): vertical; must stay divisible by 32.
- `gpu="L4"`: change to `"A10G"` or `"A100"` for faster/better (costs more).
