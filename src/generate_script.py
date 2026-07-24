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

# Daily themes — mirror the activities from the character reference sheet so
# every day feels fresh but familiar to the audience.
THEMES = [
    "cooking a tiny meal together in the cozy kitchen",
    "a dressed-up garden stroll with bubble tea",
    "a fishing trip on a little wooden boat",
    "grocery shopping with a tiny cart",
    "a cozy work-from-home day on the laptop",
    "a travel day with sunglasses and little suitcases",
    "cleaning and tidying up the cottage together",
    "a cozy night reading their 'Our Adventure Diary' in bed",
    "baking cookies on a rainy day",
    "a picnic in the flower garden",
    "planting flowers in the little garden",
    "a beach day building tiny sandcastles",
]

STYLE_LOCK = (
    "ultra-cute fluffy 3D animated render, soft plush fur, big sparkly expressive "
    "eyes, adorable chubby proportions, warm cozy cottage lighting, cinematic soft "
    "focus, hyper-detailed, wholesome, family-friendly"
)

# Fixed character look — appended so both stay recognizable in every scene.
CHAR_LOCK = (
    "Jon is a golden Labrador puppy wearing a brown collar with a bone 'Jon' tag; "
    "Katie is a fluffy silver-white Persian cat with a pink bow and a heart 'Katie' "
    "tag, often in a cute pink dress."
)

SYSTEM_PROMPT = f"""You are the head writer for a wholesome, family-friendly
animated pet-vlog brand called "Jon & Katie — Best Friends. Big Adventures."

Characters (keep 100% consistent):
- JON: a cute golden Labrador puppy, male. Playful, funny, loyal, foodie. Loves
  vlogging & exploring — he's the energetic host who holds the camera.
- KATIE: a fluffy silver-white Persian cat, female, with a pink bow. Elegant,
  smart, sassy, caring. Loves cooking & shopping — the classy planner.

They live in a cozy cottage and film a daily "day in the life" vlog: waking up,
cooking tiny meals (ASMR), an activity/outing, and winding down. No violence.
Soft narration only (no dialogue words needed).

Return STRICT JSON only, matching this schema:
{{
  "title": "catchy YouTube title (<= 70 chars, cute, US audience)",
  "description": "2-3 sentence description",
  "hashtags": ["#...", up to 8, mix of asmr/cute/animation/petvlog],
  "scenes": [
    {{
      "id": 1,
      "activity": "one of: cooking | garden | fishing | grocery | laptop | travel | cleaning | diary",
      "beat": "wake up | breakfast | activity | outing | snack | wind-down",
      "visual_prompt": "detailed scene prompt",
      "narration": "one warm, short narration sentence",
      "caption": "short on-screen caption (<= 6 words)",
      "seconds": 6
    }}
  ]
}}
Aim for 7-9 scenes; prefer using the 8 activities above as the scene set so they
match the character art. Every visual_prompt MUST end with this exact text:
"{CHAR_LOCK} Style: {STYLE_LOCK}"
"""


def _fallback_storyboard(theme: str, today: str) -> dict:
    # 8 beats mapped 1:1 to the 8 activity panels on the character sheet, so the
    # day plays as a cute "day in the life" montage of Jon & Katie.
    beats = [
        ("cooking", "wake up", "Katie cooks a tiny breakfast while Jon waits, tail wagging.", "Cooking together"),
        ("garden", "activity", "A morning garden stroll with cute little bubble teas.", "Garden walk"),
        ("fishing", "outing", "Off on a fishing trip in their little wooden boat.", "Fishing trip"),
        ("grocery", "outing", "Shopping for treats with the tiny grocery cart.", "Grocery run"),
        ("laptop", "activity", "A cozy work-from-home moment with warm coffee.", "Work from home"),
        ("travel", "outing", "Sunglasses on, tiny suitcases packed — adventure time!", "Travel day"),
        ("cleaning", "activity", "Tidying up the cozy cottage together, squeaky clean.", "Cleaning day"),
        ("diary", "wind-down", "Cuddled up at night, writing their adventure diary.", "Goodnight 💤"),
    ]
    scenes = []
    for i, (activity, beat, narration, caption) in enumerate(beats, start=1):
        scenes.append(
            {
                "id": i,
                "activity": activity,
                "beat": beat,
                "visual_prompt": (
                    f"Jon the golden Labrador puppy and Katie the silver-white "
                    f"Persian cat, {activity} scene. {CHAR_LOCK} Style: {STYLE_LOCK}"
                ),
                "narration": narration,
                "caption": caption,
                "seconds": 7,
            }
        )
    return {
        "title": "Jon & Katie: A Cozy Day in the Life 🐶🐱",
        "description": (
            f"Spend a cozy day with Jon the puppy and Katie the cat — {theme}, "
            f"and lots of tiny ASMR moments. Best friends, big adventures 💛 New "
            f"video every day!"
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
        f"End every visual_prompt with exactly: {CHAR_LOCK} Style: {STYLE_LOCK}"
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
