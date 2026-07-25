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

## ⚠️ Important: the $30 needs a payment method

Modal shows `$0 of $30/mo in free credits — add a payment method to unlock the
rest`. **Without a card on file you get $0**, so the GPU path simply won't run
and the pipeline will use stock footage instead. Add a card only if you're happy
with that trade-off (and set a spend limit in Modal → Settings).

Stock footage (Pexels) stays the main engine either way: free, no card, unlimited.

## One-time setup — no terminal needed

1. **Sign up** at [modal.com](https://modal.com) (Google login). In onboarding pick
   **Personal** and **Inference (Image/Video)**.
2. Add a payment method (only if you want the $30 credits to be usable).
3. Dashboard → **Settings → API Tokens → New token** → copy both values.
4. **GitHub → Settings → Secrets → Actions** → add:
   - `MODAL_TOKEN_ID`
   - `MODAL_TOKEN_SECRET`
5. **Actions → "Deploy Modal GPU app" → Run workflow** — this deploys
   `modal_app.py` for you and generates a test clip (downloadable as an
   artifact). No local install required.
6. Turn it on for daily runs: **Variables** → `AI_BROLL` = `true`.

> Alternative if you prefer a terminal: `pip install modal && modal setup &&
> modal deploy modal_app.py`.

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
