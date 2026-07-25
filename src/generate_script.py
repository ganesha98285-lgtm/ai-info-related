"""Step 1 — Write today's AI-tools short, optimized for US retention + SEO.

Output JSON ("storyboard") drives the whole pipeline:
  * scene 1 = scroll-stopping HOOK (first 2s decide everything)
  * 4-6 value beats (a tool / tip / hack, one clear idea each)
  * final scene = follow/subscribe CTA
  * each scene carries `stock_keywords` used to pull real HD footage
  * SEO: viral title, keyword-rich description, hashtags, search keywords

Falls back to a strong built-in template if GEMINI_API_KEY is missing/limited,
so the daily run never fails.
"""
from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

from config import settings

# Rotating angles so every day feels new (all high-interest in the US).
TOPICS = [
    "3 AI tools that save you hours every week",
    "ChatGPT prompts that feel like cheating",
    "free AI tools nobody is talking about",
    "AI tools for students that actually work",
    "how to make money with AI tools",
    "AI tools that replace boring office work",
    "AI video and image tools you should try",
    "AI tools for content creators",
    "automate your day with these AI tools",
    "AI tools that write emails for you",
    "hidden ChatGPT features you are not using",
    "AI tools for small business owners",
]

# Scroll-stopping hooks (spoken). Rotated daily so the feed never repeats.
HOOKS = [
    "Stop scrolling - this AI tool is insane.",
    "You are using ChatGPT wrong. Here is the fix.",
    "This free AI tool does 3 hours of work in 3 minutes.",
    "Nobody talks about this AI tool, and it is free.",
    "3 AI tools you will wish you knew sooner.",
    "This AI hack saved me 10 hours this week.",
    "Delete these 3 apps. AI does it better now.",
    "If you still type this by hand, watch closely.",
    "This is the AI tool companies do not want you to find.",
    "I tried 50 AI tools. These are the only 3 worth it.",
    "Your boss will think you worked all night.",
    "Free AI tools that feel illegal to know.",
]

# Short ON-SCREEN hook text (big yellow, first 3 seconds).
HOOK_CAPTIONS = [
    "WATCH THIS", "DO NOT SCROLL", "SAVE THIS", "FREE AI TOOL",
    "THIS IS INSANE", "TRY THIS TODAY", "AI HACK",
]

# Hashtag pool: a fixed core (search intent) + rotating extras (reach).
CORE_TAGS = ["#shorts", "#ai", "#aitools", "#chatgpt"]
EXTRA_TAGS = [
    "#artificialintelligence", "#aitips", "#productivity", "#tech",
    "#automation", "#aiforbeginners", "#techtips", "#futuretech",
    "#chatgpttips", "#workhacks", "#sidehustle", "#viral", "#fyp",
    "#aitools2026", "#learnai", "#promptengineering",
]

CTAS = [
    "Follow for a new AI tool every day.",
    "Save this and follow for daily AI tips.",
    "Follow so you never miss the next AI drop.",
]

SYSTEM_PROMPT = """You are a top YouTube Shorts scriptwriter for a faceless
US-focused channel about AI tools, tips and hacks (channel: "AI Tool Drop").

Goals, in order: RETENTION -> SHARES -> SEARCH (SEO).
Rules:
- Scene 1 is a HOOK: max 12 words, creates instant curiosity or a bold claim.
- Then 4-6 value scenes: ONE concrete tool/tip each, specific and useful.
  Name real, well-known tools. No fluff, no "in this video".
- Last scene is a short CTA (follow/subscribe).
- Spoken lines must be punchy and natural, 8-18 words (fast pacing).
- On-screen text: 3-6 words, ASCII only, ALL-CAPS style keywords.
- stock_keywords: 2-4 SIMPLE visual search terms for real stock footage
  (e.g. "laptop typing", "robot", "city night", "phone screen"). Visual nouns only.
- Total spoken time must fit ~35-50 seconds.

Return STRICT JSON only:
{
  "title": "viral title <= 90 chars, curiosity + keyword, 1 emoji max",
  "description": "3-4 lines, keyword rich, ends with subscribe CTA + hashtags",
  "hashtags": ["#shorts", ... 8-12 relevant tags],
  "keywords": ["seo search phrase", ... up to 12],
  "scenes": [
    {"id":1,"role":"hook","narration":"spoken line","caption":"ON SCREEN TEXT",
     "stock_keywords":["laptop typing","ai robot"]},
    {"id":2,"role":"value","narration":"...","caption":"...","stock_keywords":["..."]},
    {"id":7,"role":"cta","narration":"Follow for daily AI tools.","caption":"FOLLOW FOR MORE","stock_keywords":["phone scrolling"]}
  ]
}
"""


def _fallback_storyboard(topic: str, today: str) -> dict:
    hook = random.choice(HOOKS)
    beats = [
        ("value", "Perplexity answers with live sources, so you can trust it.",
         "RESEARCH IN SECONDS", ["laptop typing", "search engine"]),
        ("value", "Use ElevenLabs to turn any script into a real sounding voice.",
         "AI VOICE, FREE", ["microphone studio", "sound waves"]),
        ("value", "Gamma builds a full slide deck from one sentence.",
         "SLIDES IN 1 CLICK", ["presentation meeting", "office laptop"]),
        ("value", "Ask ChatGPT to act as your editor, then paste your text.",
         "BETTER PROMPTS", ["typing keyboard", "ai robot"]),
        ("value", "CapCut auto captions your videos in seconds.",
         "AUTO CAPTIONS", ["video editing", "phone filming"]),
    ]
    random.shuffle(beats)
    beats = beats[:4]

    scenes = [{
        "id": 1, "role": "hook", "narration": hook,
        "caption": random.choice(HOOK_CAPTIONS),
        "stock_keywords": ["ai robot", "laptop typing", "technology"],
    }]
    for i, (role, line, cap, kw) in enumerate(beats, start=2):
        scenes.append({"id": i, "role": role, "narration": line,
                       "caption": cap, "stock_keywords": kw})
    scenes.append({
        "id": len(scenes) + 1, "role": "cta", "narration": random.choice(CTAS),
        "caption": "FOLLOW FOR MORE", "stock_keywords": ["phone scrolling", "city night"],
    })

    return {
        "title": f"{topic.title()} 🤖",
        "description": (
            f"{topic.capitalize()} - fast, practical AI tips you can use today.\n"
            "New AI tools, prompts and hacks every single day.\n"
            "Subscribe so you never miss the next AI drop.\n"
            "#ai #aitools #chatgpt #shorts #productivity"
        ),
        "hashtags": CORE_TAGS + random.sample(EXTRA_TAGS, 7),
        "keywords": [
            "best ai tools", "free ai tools", "chatgpt tips", "ai tools 2026",
            "ai productivity tools", "ai for beginners", "ai hacks",
            "make money with ai", "ai tools you need",
        ],
        "scenes": scenes,
        "meta": {"date": today, "topic": topic, "generated_by": "fallback"},
    }


def _gemini_storyboard(topic: str, today: str) -> dict:
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        settings.gemini_model, system_instruction=SYSTEM_PROMPT
    )
    resp = model.generate_content(
        f"Today's angle: {topic}. Date: {today}. Audience: United States. "
        f"Make the hook impossible to scroll past.",
        generation_config={"response_mime_type": "application/json"},
    )
    data = json.loads(resp.text)
    data.setdefault("meta", {})
    data["meta"].update({"date": today, "topic": topic, "generated_by": "gemini"})
    return data


def generate_storyboard(theme: str | None = None) -> dict:
    today = dt.date.today().isoformat()
    topic = theme or random.choice(TOPICS)
    if settings.gemini_api_key:
        try:
            sb = _gemini_storyboard(topic, today)
            if sb.get("scenes"):
                return sb
        except Exception as exc:
            print(f"[generate_script] Gemini failed ({exc}); using fallback.")
    else:
        print("[generate_script] No GEMINI_API_KEY set; using fallback template.")
    return _fallback_storyboard(topic, today)


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
