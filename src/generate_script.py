"""Step 1 — Generate today's vlog story with Gemini (free tier).

Produces a structured JSON "storyboard" for one daily vlog:
  - title, description, hashtags (SEO for US audience)
  - a list of scenes, each with: an image/video prompt (style-locked to the
    character bible), a short narration line, and an on-screen caption.

If GEMINI_API_KEY is missing, falls back to a built-in template so the rest of
the pipeline can still be developed/tested offline.
"""
from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

from config import settings

# Daily themes so every day feels fresh but familiar.
THEMES = [
    "a cozy rainy day baking cookies indoors",
    "a sunny morning picnic in the garden",
    "spring cleaning the tiny cottage together",
    "making a tiny pancake breakfast (ASMR)",
    "a little trip to the farmers market",
    "planting flowers in the miniature garden",
    "a beach day building tiny sandcastles",
    "a cozy movie night with popcorn",
    "John tries to cook and makes a cute mess",
    "Ketty plans a surprise birthday for John",
    "a snowy day and warm hot cocoa",
    "a forest walk collecting little treasures",
]

STYLE_LOCK = (
    "cute 3D animated pixar-style, soft rounded shapes, big expressive eyes, "
    "warm pastel cozy lighting, miniature cottage setting, ultra adorable, high "
    "detail, clean render, family-friendly"
)

SYSTEM_PROMPT = """You are the head writer for a wholesome, family-friendly
animated pet-vlog channel called "Jab Ketty Met John".

Characters (keep 100% consistent):
- JOHN: a cute golden Labrador puppy — excited, foodie, clumsy, always hungry.
- KETTY: a fluffy silver-white Persian cat — calm, classy, the organized planner.

They live in a cozy miniature cottage and film a daily "day in the life" vlog:
waking up, cooking tiny meals (ASMR), doing an activity, going on a little outing,
and winding down. No violence. No dialogue words needed (soft narration only).

Return STRICT JSON only, matching this schema:
{
  "title": "catchy YouTube title (<= 70 chars, cute, US audience)",
  "description": "2-3 sentence description",
  "hashtags": ["#...", ...  up to 8, mix of asmr/cute/animation/petvlog],
  "scenes": [
    {
      "id": 1,
      "beat": "wake up | breakfast | activity | outing | snack | wind-down",
      "visual_prompt": "detailed image/video prompt for this scene",
      "narration": "one warm, short narration sentence",
      "caption": "short on-screen caption (<= 6 words)",
      "seconds": 6
    }
  ]
}
Aim for 7-9 scenes, total ~40-70 seconds of scene content (we loop/slow for the
long cut). Every visual_prompt MUST end with the exact style lock text provided.
"""


def _fallback_storyboard(theme: str, today: str) -> dict:
    beats = [
        ("wake up", "John and Ketty wake up and stretch in their cozy bed."),
        ("breakfast", "Ketty pours tiny cereal while John waits, tail wagging."),
        ("activity", f"Today's plan: {theme}."),
        ("outing", "They step outside into the warm morning light."),
        ("snack", "A tiny crunchy snack — the best part of the day (ASMR)."),
        ("wind-down", "Cozy blankets, fairy lights, and a happy little yawn."),
    ]
    scenes = []
    for i, (beat, narration) in enumerate(beats, start=1):
        scenes.append(
            {
                "id": i,
                "beat": beat,
                "visual_prompt": (
                    f"John the golden Labrador puppy and Ketty the silver-white "
                    f"Persian cat, {beat} scene, {theme}. Style: {STYLE_LOCK}"
                ),
                "narration": narration,
                "caption": beat.title(),
                "seconds": 7,
            }
        )
    return {
        "title": f"John & Ketty: {theme.capitalize()} 🐶🐱",
        "description": (
            f"Join John the puppy and Ketty the cat for {theme}! A cozy, cute "
            f"daily vlog full of tiny ASMR moments. New video every day 💛"
        ),
        "hashtags": [
            "#cute", "#asmr", "#petvlog", "#animation",
            "#puppy", "#cat", "#cozy", "#shorts",
        ],
        "scenes": scenes,
        "meta": {"date": today, "theme": theme, "generated_by": "fallback"},
    }


def _gemini_storyboard(theme: str, today: str) -> dict:
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        settings.gemini_model, system_instruction=SYSTEM_PROMPT
    )
    user = (
        f"Write today's vlog. Date: {today}. Theme of the day: {theme}. "
        f"Use this exact style lock at the end of every visual_prompt: {STYLE_LOCK}"
    )
    resp = model.generate_content(
        user,
        generation_config={"response_mime_type": "application/json"},
    )
    data = json.loads(resp.text)
    data.setdefault("meta", {})
    data["meta"].update({"date": today, "theme": theme, "generated_by": "gemini"})
    return data


def generate_storyboard(theme: str | None = None) -> dict:
    """Generate today's storyboard dict (Gemini if key present, else fallback)."""
    today = dt.date.today().isoformat()
    theme = theme or random.choice(THEMES)
    if settings.gemini_api_key:
        try:
            return _gemini_storyboard(theme, today)
        except Exception as exc:  # network/quota/parse issues -> safe fallback
            print(f"[generate_script] Gemini failed ({exc}); using fallback.")
    else:
        print("[generate_script] No GEMINI_API_KEY set; using fallback template.")
    return _fallback_storyboard(theme, today)


def save_storyboard(storyboard: dict) -> Path:
    settings.ensure_dirs()
    today = storyboard.get("meta", {}).get("date", dt.date.today().isoformat())
    out = settings.output_dir / today
    out.mkdir(parents=True, exist_ok=True)
    f = out / "storyboard.json"
    f.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False), "utf-8")
    print(f"[generate_script] Storyboard saved -> {f}")
    return f


if __name__ == "__main__":
    sb = generate_storyboard()
    save_storyboard(sb)
    print(json.dumps(sb, indent=2, ensure_ascii=False))
