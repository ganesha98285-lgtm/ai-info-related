"""Step 1 — Generate today's vlog story with Gemini (free tier).

Produces a structured JSON "storyboard" optimized for RETENTION + VIRALITY:
  - a scroll-stopping HOOK as the first scene
  - Jon & Katie talking to each other (dialogue, two distinct voices)
  - a strong LIKE / SHARE / SUBSCRIBE call-to-action at the end
  - SEO title, keyword-rich description, and trending hashtags

If GEMINI_API_KEY is missing, falls back to a built-in template so the rest of
the pipeline still runs offline.
"""
from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

from config import settings

# Daily themes — mirror the 8 activities on the character reference sheet.
THEMES = [
    "cooking a tiny meal together in the cozy kitchen",
    "a dressed-up garden stroll with bubble tea",
    "a fishing trip on a little wooden boat",
    "grocery shopping with a tiny cart",
    "a cozy work-from-home day on the laptop",
    "a travel day with sunglasses and little suitcases",
    "cleaning and tidying up the cottage together",
    "a cozy night reading their 'Our Adventure Diary' in bed",
]

# Scroll-stopping opening hooks (first 2 seconds decide if people stay).
HOOKS = [
    "Wait till you see what Katie made this morning!",
    "You won't believe what happened on our tiny boat...",
    "POV: your best friends are a puppy and a cat.",
    "This is the cutest morning routine on the internet.",
    "Nobody is ready for how cute today gets.",
    "Stop scrolling - you need to see this.",
]

# Viral title templates (emojis render fine in YouTube titles).
TITLE_TEMPLATES = [
    "Jon & Katie's Cutest Day EVER 🐶🐱 (you'll smile!)",
    "A Puppy & a Cat Vlog Their Day 🐶🐱 SO CUTE",
    "Best Friends Jon & Katie: Daily Adventure 🐾✨",
    "You Won't Believe How Cute This Vlog Is 🐶🐱💛",
]

STYLE_LOCK = (
    "ultra-cute fluffy 3D animated render, soft plush fur, big sparkly expressive "
    "eyes, adorable chubby proportions, warm cozy cottage lighting, cinematic soft "
    "focus, hyper-detailed, wholesome, family-friendly"
)

CHAR_LOCK = (
    "Jon is a golden Labrador puppy wearing a brown collar with a bone 'Jon' tag; "
    "Katie is a fluffy silver-white Persian cat with a pink bow and a heart 'Katie' "
    "tag, often in a cute pink dress."
)

SYSTEM_PROMPT = f"""You are the head writer + YouTube growth strategist for a
wholesome animated pet-vlog brand: "Jon & Katie — Best Friends. Big Adventures."

Characters (keep 100% consistent):
- JON: golden Labrador puppy, male. Playful, funny, foodie, energetic host.
- KATIE: fluffy silver-white Persian cat, female, pink bow. Elegant, smart, sassy, caring.

Make it BINGE-WORTHY and SHAREABLE:
- Scene 1 MUST be a strong HOOK (scroll-stopping line, sets curiosity).
- Jon and Katie TALK TO EACH OTHER (short, cute back-and-forth dialogue).
- The LAST scene MUST be a call-to-action (ask to LIKE, SHARE & SUBSCRIBE).
- Keep it wholesome, English, family-friendly. No violence.

Return STRICT JSON only:
{{
  "title": "viral, curiosity-driven YouTube title (<= 90 chars, 1-2 emojis)",
  "description": "2-3 sentences, keyword-rich, ends with a subscribe CTA",
  "hashtags": ["#...", 8-12 trending tags: shorts/cute/asmr/animation/petvlog/puppy/cat/fyp/viral"],
  "keywords": ["seo phrase", up to 12, what people would search],
  "scenes": [
    {{
      "id": 1,
      "activity": "cooking|garden|fishing|grocery|laptop|travel|cleaning|diary",
      "speaker": "Jon | Katie | Narrator",
      "narration": "the spoken line (short, natural, cute)",
      "caption": "on-screen text (<= 8 words, ASCII only)",
      "hook": true,
      "cta": false,
      "visual_prompt": "detailed scene prompt",
      "seconds": 5
    }}
  ]
}}
9 scenes total: scene 1 = hook, last scene = subscribe CTA. Every visual_prompt
MUST end with: "{CHAR_LOCK} Style: {STYLE_LOCK}"
"""


def _fallback_storyboard(theme: str, today: str) -> dict:
    hook = random.choice(HOOKS)
    # (activity, speaker, spoken line, short caption, hook?, cta?)
    rows = [
        ("cooking", "Jon", hook, "Wait for it...", True, False),
        ("cooking", "Katie", "Good morning! Tiny pancakes coming right up.", "Breakfast time", False, False),
        ("garden", "Jon", "Bubble tea walk in the garden? Best idea ever!", "Garden walk", False, False),
        ("fishing", "Katie", "Hold on tight, Jon - we are going fishing!", "Fishing trip", False, False),
        ("grocery", "Jon", "Two tiny carts and so many treats... uh oh.", "Grocery run", False, False),
        ("laptop", "Katie", "Work mode on. Jon, stop chewing the mouse!", "Work from home", False, False),
        ("travel", "Jon", "Sunglasses on, suitcase packed - adventure time!", "Travel day", False, False),
        ("cleaning", "Katie", "A clean cottage is a cozy cottage.", "Tidy up", False, False),
        ("diary", "Jon", "Loved our day? LIKE and SUBSCRIBE for daily adventures!", "Like & Subscribe!", False, True),
    ]
    scenes = []
    for i, (activity, speaker, line, caption, is_hook, is_cta) in enumerate(rows, start=1):
        scenes.append({
            "id": i,
            "activity": activity,
            "speaker": speaker,
            "narration": line,
            "caption": caption,
            "hook": is_hook,
            "cta": is_cta,
            "visual_prompt": (
                f"Jon the golden Labrador puppy and Katie the silver-white Persian "
                f"cat, {activity} scene. {CHAR_LOCK} Style: {STYLE_LOCK}"
            ),
            "seconds": 5,
        })
    return {
        "title": random.choice(TITLE_TEMPLATES),
        "description": (
            "Jon the puppy and Katie the cat vlog their cozy daily adventure - "
            f"{theme}, cute ASMR moments, and lots of giggles. Watch till the end! "
            "Subscribe for a new cute vlog every day. 🐶🐱💛"
        ),
        "hashtags": [
            "#shorts", "#cute", "#puppy", "#cat", "#animation", "#asmr",
            "#petvlog", "#fyp", "#viral", "#cartoon", "#cozy", "#foryou",
        ],
        "keywords": [
            "cute animated puppy and cat vlog", "daily animal vlog cartoon",
            "cute cat and dog story", "asmr animated vlog", "wholesome pet cartoon",
            "puppy and cat best friends", "cute animated shorts",
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
        f"Scene 1 must be a strong hook; last scene must be a subscribe CTA. "
        f"End every visual_prompt with exactly: {CHAR_LOCK} Style: {STYLE_LOCK}"
    )
    resp = model.generate_content(
        user, generation_config={"response_mime_type": "application/json"}
    )
    data = json.loads(resp.text)
    data.setdefault("meta", {})
    data["meta"].update({"date": today, "theme": theme, "generated_by": "gemini"})
    return data


def generate_storyboard(theme: str | None = None) -> dict:
    today = dt.date.today().isoformat()
    theme = theme or random.choice(THEMES)
    if settings.gemini_api_key:
        try:
            return _gemini_storyboard(theme, today)
        except Exception as exc:
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
