"""Step 1 — Write today's AI short, guaranteed to be something never posted before.

Output JSON ("storyboard") drives the whole pipeline:
  * scene 1 = scroll-stopping HOOK (first 2s decide everything)
  * 4-6 value beats (one concrete tool/tip each)
  * final scene = follow/subscribe CTA
  * each scene carries `stock_keywords` used to pull real HD footage
  * SEO: viral title, keyword-rich description, hashtags, search keywords

NO-REPEAT GUARANTEE
-------------------
Every title, hook and tip the channel has ever published is stored in
`content/history.json` (see src/history.py). Before a storyboard is accepted it
must pass a novelty check (fuzzy-matched against that whole history):
  * the title must not resemble any past title
  * the hook must not resemble any past hook
  * at least 70% of the value lines must be ideas never used before

Gemini gets the "already published" list plus a note about which past videos
performed best — so it LEARNS the winning style while being forced to bring a new
idea. If Gemini is unavailable, a combinatorial fallback composes a fresh angle
from thousands of subject x angle x audience combinations, skipping used ones.
"""
from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

from config import settings
from src import history

MAX_GEMINI_TRIES = 4
MAX_FALLBACK_TRIES = 300

# --------------------------------------------------------------------------- #
# combinatorial idea space (fallback only — Gemini is the primary writer)
# --------------------------------------------------------------------------- #
SUBJECTS = [
    "ChatGPT", "Claude", "Gemini", "Perplexity", "NotebookLM", "ElevenLabs",
    "Midjourney", "Canva AI", "CapCut AI", "Gamma", "Notion AI", "Otter",
    "Descript", "Runway", "Suno", "Grammarly AI", "Zapier AI", "Make.com",
    "Cursor", "GitHub Copilot", "Excel Copilot", "Google AI Studio",
    "AI agents", "AI voice cloning", "AI thumbnails", "AI subtitles",
    "AI resume tools", "AI research tools", "AI note takers",
    "AI presentation tools", "AI spreadsheet tools", "AI email writers",
    "AI photo editors", "AI logo makers", "AI translation tools",
    "AI study tools", "AI coding assistants", "AI meeting summaries",
    "prompt engineering", "AI automation workflows",
]

ANGLES = [
    "tricks nobody uses", "hidden features", "the fastest way to use it",
    "mistakes that waste your time", "how to get paid work with it",
    "settings you should change today", "what it does better than humans",
    "the one prompt that changes everything", "free alternatives that match it",
    "how to save hours a week with it", "what beginners get wrong about it",
    "how pros actually use it",
]

AUDIENCES = [
    "for beginners", "for students", "for freelancers", "for small business",
    "for content creators", "for job seekers", "for developers",
    "for busy professionals", "for side hustles", "for teachers",
]

HOOK_TEMPLATES = [
    "You are using {subject} wrong, and it is costing you hours.",
    "Nobody told you {subject} could do this.",
    "This {subject} trick feels illegal to know.",
    "Stop scrolling if you use {subject} every day.",
    "I found the fastest way to use {subject}.",
    "{subject} just made half my workflow pointless.",
    "Most people never open this part of {subject}.",
    "One setting in {subject} changed everything for me.",
    "If you still do this by hand, watch closely.",
    "This is the {subject} feature power users hide.",
    "I tested {subject} for a week. Here is what stuck.",
    "Your competitors are already doing this with {subject}.",
    "Three minutes with {subject} replaced three hours of work.",
    "The {subject} tip I wish I knew a year ago.",
    "Here is what {subject} can do that you are not using.",
    "This changes how you should think about {subject}.",
    "Do not open {subject} again until you see this.",
    "The reason your {subject} results feel generic.",
]

# Value beats are composed as (subject x action), giving ~40 x 26 = 1000+
# distinct ideas without Gemini. Gemini remains the primary writer because its
# idea space is effectively unlimited; this is the offline safety net.
TIP_ACTIONS = [
    ("act as an expert and question you before answering",
     "BETTER PROMPTS", ["typing keyboard", "laptop closeup"]),
    ("turn rough notes into one clean summary",
     "NOTES TO SUMMARY", ["notebook writing", "office desk"]),
    ("copy the style of an example you paste in",
     "SHOW AN EXAMPLE", ["laptop screen", "person working"]),
    ("rewrite the same result three different ways",
     "THREE VERSIONS", ["typing hands", "computer screen"]),
    ("rewrite anything for a specific reader",
     "NAME THE READER", ["reading phone", "coffee desk"]),
    ("find the weak points in your own work",
     "SELF REVIEW", ["thinking person", "laptop night"]),
    ("turn any answer into a reusable checklist",
     "REUSE IT", ["checklist paper", "planner desk"]),
    ("save a prompt so the next job takes seconds",
     "SAVE THE PROMPT", ["phone notes", "keyboard typing"]),
    ("review its own last answer and improve it",
     "ITERATE ONCE", ["laptop typing", "office window"]),
    ("plan the steps first, then execute them",
     "STEPS FIRST", ["stairs walking", "planning board"]),
    ("summarise a long document into five bullets",
     "LONG TO SHORT", ["stack of papers", "reading desk"]),
    ("pull the action items out of a meeting",
     "ACTION ITEMS", ["meeting room", "notebook pen"]),
    ("write the first draft so you only edit",
     "DRAFT IT FOR YOU", ["writing laptop", "coffee morning"]),
    ("explain something complex in plain language",
     "EXPLAIN SIMPLY", ["teacher board", "student studying"]),
    ("build a table comparing your options",
     "COMPARE FAST", ["spreadsheet screen", "data charts"]),
    ("translate your text and keep the tone",
     "KEEP THE TONE", ["world map", "phone translate"]),
    ("clean up messy data in one instruction",
     "FIX THE DATA", ["data screen", "server room"]),
    ("generate ten title options in one go",
     "TEN TITLES", ["brainstorm notes", "laptop desk"]),
    ("outline a whole project in a minute",
     "FULL OUTLINE", ["planning wall", "sticky notes"]),
    ("catch the mistake you always miss",
     "CATCH MISTAKES", ["magnifying glass", "proofreading"]),
    ("turn one idea into a week of content",
     "ONE TO SEVEN", ["calendar planning", "content desk"]),
    ("answer using only the file you upload",
     "USE MY FILE", ["documents folder", "laptop upload"]),
    ("shorten anything without losing the point",
     "CUT THE FLUFF", ["scissors paper", "editing screen"]),
    ("write the follow up message for you",
     "FOLLOW UP DONE", ["phone messaging", "email screen"]),
    ("check your work against the brief",
     "MATCH THE BRIEF", ["checklist tick", "office review"]),
    ("do the boring formatting automatically",
     "NO MORE FORMATTING", ["keyboard closeup", "screen code"]),
]

HOOK_CAPTIONS = [
    "WATCH THIS", "DO NOT SCROLL", "SAVE THIS", "TRY THIS TODAY",
    "THIS IS INSANE", "AI HACK", "NEW TRICK", "60 SECOND FIX",
    "MOST MISS THIS", "USE THIS TONIGHT",
]

CORE_TAGS = ["#shorts", "#ai", "#aitools", "#chatgpt"]
EXTRA_TAGS = [
    "#artificialintelligence", "#aitips", "#productivity", "#tech",
    "#automation", "#aiforbeginners", "#techtips", "#futuretech",
    "#chatgpttips", "#workhacks", "#sidehustle", "#viral", "#fyp",
    "#aitools2026", "#learnai", "#promptengineering", "#aiagents",
    "#digitalskills", "#studytips", "#freelancing",
]

CTAS = [
    "Follow for a new AI tool every day.",
    "Save this and follow for daily AI tips.",
    "Follow so you never miss the next AI drop.",
    "Follow if you want tomorrow's tool too.",
    "Subscribe, one new AI trick every single day.",
]

SYSTEM_PROMPT = """You are a top YouTube Shorts scriptwriter for a faceless
US-focused channel about AI tools, tips and hacks (channel: "AI Tool Drop").

Goals, in order: RETENTION -> SHARES -> SEARCH (SEO).

ABSOLUTE RULE: originality. The channel must never publish the same idea, hook
or title twice. You will be given the list of everything already published — your
output must be a genuinely different subject and angle, not a reworded version.

Rules:
- Scene 1 is a HOOK: max 12 words, instant curiosity or a bold claim.
- Then 4-6 value scenes: ONE concrete tool/tip each, specific and useful.
  Name real, well-known tools. No fluff, no "in this video".
- Last scene is a short CTA (follow/subscribe).
- Spoken lines punchy and natural, 8-18 words (fast pacing).
- On-screen text: 3-6 words, ASCII only, ALL-CAPS style keywords.
- stock_keywords: 2-4 SIMPLE visual search terms for real stock footage
  (e.g. "laptop typing", "robot", "city night"). Visual nouns only. Vary them
  between videos so the footage never looks recycled.
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


# --------------------------------------------------------------------------- #
def _fresh_angle(data: dict) -> str:
    """Pick a subject x angle x audience combination never used before."""
    for _ in range(MAX_FALLBACK_TRIES):
        subject = random.choice(SUBJECTS)
        angle = random.choice(ANGLES)
        audience = random.choice(AUDIENCES)
        topic = f"{subject}: {angle} {audience}"
        if not history.topic_used(topic, data):
            return topic
    print("[generate_script] WARNING: the built-in angle space is running low — "
          "set GEMINI_API_KEY for unlimited fresh ideas.")
    return f"{random.choice(SUBJECTS)}: {random.choice(ANGLES)}"


def _fresh_hook(subject: str, data: dict) -> str:
    templates = HOOK_TEMPLATES[:]
    random.shuffle(templates)
    for t in templates:
        hook = t.format(subject=subject)
        if not history.hook_used(hook, data):
            return hook
    return random.choice(templates).format(subject=subject)


def _fresh_tips(subject: str, data: dict,
                want: int = 4) -> list[tuple[str, str, list[str]]]:
    """Value beats (subject + action) whose wording has never been used before."""
    pool = TIP_ACTIONS[:]
    random.shuffle(pool)
    picked: list[tuple[str, str, list[str]]] = []
    seen_now: list[str] = []
    for action, cap, kw in pool:
        line = f"{subject} can {action}."
        if history.idea_used(line, data):
            continue
        if history.is_duplicate(line, seen_now, history.IDEA_THRESHOLD):
            continue
        picked.append((line, cap, kw))
        seen_now.append(line)
        if len(picked) == want:
            break
    return picked


def _fallback_storyboard(topic: str, today: str, data: dict) -> dict | None:
    """Compose a storyboard offline. Returns None if it cannot be made unique."""
    subject = topic.split(":")[0].strip() or "ChatGPT"
    hook = _fresh_hook(subject, data)
    tips = _fresh_tips(subject, data, want=4)
    if len(tips) < 3:
        return None  # this subject is used up; caller will try another

    scenes = [{
        "id": 1, "role": "hook", "narration": hook,
        "caption": random.choice(HOOK_CAPTIONS),
        "stock_keywords": random.sample(
            ["ai robot", "laptop typing", "technology", "server room",
             "phone screen", "city night", "data screen"], 3),
    }]
    for i, (line, cap, kw) in enumerate(tips, start=2):
        scenes.append({"id": i, "role": "value", "narration": line,
                       "caption": cap, "stock_keywords": kw})
    scenes.append({
        "id": len(scenes) + 1, "role": "cta", "narration": random.choice(CTAS),
        "caption": "FOLLOW FOR MORE",
        "stock_keywords": ["phone scrolling", "city night"],
    })

    return {
        "title": f"{topic[:80]} 🤖",
        "description": (
            f"{topic.capitalize()} — practical AI tips you can use today.\n"
            "New AI tools, prompts and hacks every single day.\n"
            "Subscribe so you never miss the next AI drop.\n"
            "#ai #aitools #chatgpt #shorts #productivity"
        ),
        "hashtags": CORE_TAGS + random.sample(EXTRA_TAGS, 7),
        "keywords": [
            f"{subject.lower()} tips", "best ai tools", "free ai tools",
            "ai tools 2026", "ai productivity", "ai for beginners", "ai hacks",
        ],
        "scenes": scenes,
        "meta": {"date": today, "topic": topic, "generated_by": "fallback"},
    }


def _gemini_storyboard(topic: str, today: str, data: dict, attempt: int) -> dict:
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        settings.gemini_model, system_instruction=SYSTEM_PROMPT
    )
    parts = [
        f"Date: {today}. Audience: United States.",
        f"Suggested fresh angle (you may improve it, but stay this specific): {topic}",
    ]
    if brief := history.avoid_brief(data):
        parts.append(brief)
    if learn := history.learning_brief(data):
        parts.append(learn)
    if attempt > 1:
        parts.append(f"Attempt {attempt}: your previous draft was too close to "
                     f"something already published. Change the SUBJECT itself, "
                     f"not just the wording.")
    parts.append("Make the hook impossible to scroll past.")

    resp = model.generate_content(
        "\n\n".join(parts),
        generation_config={"response_mime_type": "application/json",
                           "temperature": 1.0 + 0.1 * attempt},
    )
    sb = json.loads(resp.text)
    sb.setdefault("meta", {})
    sb["meta"].update({"date": today, "topic": topic, "generated_by": "gemini",
                       "attempt": attempt})
    return sb


def generate_storyboard(theme: str | None = None,
                        data: dict | None = None) -> dict:
    """Build a storyboard that is guaranteed new against the channel history."""
    today = dt.date.today().isoformat()
    data = data if data is not None else history.load()

    if settings.gemini_api_key:
        for attempt in range(1, MAX_GEMINI_TRIES + 1):
            topic = theme or _fresh_angle(data)
            try:
                sb = _gemini_storyboard(topic, today, data, attempt)
            except Exception as exc:
                print(f"[generate_script] Gemini failed ({exc}); using fallback.")
                break
            if not sb.get("scenes"):
                continue
            ok, why = history.novelty_report(sb, data)
            if ok:
                print(f"[generate_script] fresh script (attempt {attempt}): "
                      f"{sb.get('title', '')[:70]}")
                return sb
            print(f"[generate_script] attempt {attempt} rejected — {why}")
    else:
        print("[generate_script] No GEMINI_API_KEY; using the built-in "
              "combinatorial writer (still de-duplicated).")

    # Fallback: keep composing until the novelty check passes.
    last_reason = "no draft produced"
    for _ in range(40):
        sb = _fallback_storyboard(theme or _fresh_angle(data), today, data)
        if sb is None:
            last_reason = "subject's ideas are all used up"
            continue
        ok, last_reason = history.novelty_report(sb, data)
        if ok:
            return sb

    # Never publish a repeat. Skipping this short is better than repeating.
    raise RuntimeError(
        f"could not produce a NEW script ({last_reason}). Nothing was published. "
        f"Fix: set GEMINI_API_KEY for unlimited fresh ideas, or add more entries "
        f"to SUBJECTS / TIP_ACTIONS in src/generate_script.py. "
        f"History so far: {history.stats(data)}"
    )


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
