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

# Daily themes — built around the activities on the Jon & Katie character sheet
# (cooking, garden walks, fishing, grocery runs, laptop days, travel, cleaning,
# reading their adventure diary) plus cozy seasonal variety.
THEMES = [
    "cooking a tiny breakfast together in the cottage kitchen (ASMR)",
    "a garden morning walk with cute little bubble teas",
    "a fishing trip on a little wooden boat by the lake",
    "a grocery run with the tiny shopping cart",
    "a cozy 'work from home' laptop day with coffee",
    "packing tiny suitcases for a little travel adventure",
    "spring cleaning the cottage together with tiny brooms",
    "cuddling up at night reading 'Our Adventure Diary'",
    "a rainy day baking cookies indoors",
    "planting flowers in the miniature garden",
    "Jon tries to cook and makes a cute little mess",
    "Katie plans a surprise picnic for Jon",
]

# Style + identity lock. Repeating this exact text in every prompt keeps Jon and
# Katie looking identical to their reference sheet across every scene.
STYLE_LOCK = (
    "cute 3D animated pixar-style, soft rounded shapes, big expressive eyes, "
    "warm pastel cozy lighting, miniature cottage setting, ultra adorable, high "
    "detail, clean render, family-friendly"
)

# Exact character descriptions matching the reference sheet — always include so
# accessories (Jon's brown collar + bone tag, Katie's pink bow + heart tag + dress)
# stay consistent.
JON_DESC = (
    "Jon, a cute golden Labrador retriever puppy, warm butter-yellow fluffy fur, "
    "big round glossy dark-brown eyes, wearing a brown collar with a gold "
    "bone-shaped 'Jon' name tag, happy playful expression"
)
KATIE_DESC = (
    "Katie, a fluffy silver-white Persian cat, long luxurious fur, big round "
    "blue-green eyes, wearing a pink bow on her head and a pink heart-shaped "
    "'Katie' name tag, sometimes a cute pink dress, elegant calm expression"
)

SYSTEM_PROMPT = f"""You are the head writer for a wholesome, family-friendly
animated pet-vlog channel called "Jon & Katie" (tagline: Best Friends. Big
Adventures.).

Characters (keep 100% consistent with these exact descriptions):
- JON: {JON_DESC}. Personality: excited, foodie, playful, loyal, a bit clumsy,
  the energetic vlogger who films their day.
- KATIE: {KATIE_DESC}. Personality: elegant, smart, a little sassy, caring — the
  organized planner who loves cooking and shopping.

They live in a cozy miniature cottage and film a daily "day in the life" vlog:
waking up, cooking tiny meals (ASMR), doing an activity, going on a little outing,
and winding down. No violence. Soft narration only (no dialogue words needed).

Return STRICT JSON only, matching this schema:
{{
  "title": "catchy YouTube title (<= 70 chars, cute, US audience)",
  "description": "2-3 sentence description",
  "hashtags": ["#...", ...  up to 8, mix of asmr/cute/animation/petvlog],
  "scenes": [
    {{
      "id": 1,
      "beat": "wake up | breakfast | activity | outing | snack | wind-down",
      "visual_prompt": "detailed image/video prompt for this scene; ALWAYS name
                        Jon and/or Katie using their exact look + accessories",
      "narration": "one warm, short narration sentence",
      "caption": "short on-screen caption (<= 6 words)",
      "seconds": 6
    }}
  ]
}}
Aim for 7-9 scenes, total ~40-70 seconds of scene content (we loop/slow for the
long cut). Every visual_prompt MUST end with the exact style lock text provided.
"""


def _fallback_storyboard(theme: str, today: str) -> dict:
    beats = [
        ("wake up", "Jon and Katie wake up and stretch in their cozy cottage bed."),
        ("breakfast", "Katie sets the tiny table while Jon waits, tail wagging."),
        ("activity", f"Today's plan: {theme}."),
        ("outing", "They head outside into the warm morning sunlight."),
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
                    f"{JON_DESC}; and {KATIE_DESC}. Scene: {beat}, {theme}. "
                    f"Style: {STYLE_LOCK}"
                ),
                "narration": narration,
                "caption": beat.title(),
                "seconds": 7,
            }
        )
    return {
        "title": f"Jon & Katie: {theme.capitalize()} 🐶🐱",
        "description": (
            f"Join Jon the puppy and Katie the cat for {theme}! A cozy, cute "
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
