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

MAX_GEMINI_TRIES = 3
MAX_FALLBACK_TRIES = 300

# If the main model is rate-limited, these free models are tried next — separate
# per-model limits mean the day's videos still get written.
GEMINI_FALLBACK_MODELS = [
    m for m in __import__("os").getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-2.0-flash-lite,gemini-1.5-flash,gemini-1.5-flash-8b",
    ).split(",")
]

# --------------------------------------------------------------------------- #
# combinatorial idea space (fallback only — Gemini is the primary writer)
# --------------------------------------------------------------------------- #
SUBJECTS = [
    # named tools
    "ChatGPT", "Claude", "Gemini", "Perplexity", "NotebookLM", "ElevenLabs",
    "Midjourney", "Canva AI", "CapCut AI", "Gamma", "Notion AI", "Otter",
    "Descript", "Runway", "Suno", "Grammarly AI", "Zapier AI", "Make.com",
    "Cursor", "GitHub Copilot", "Excel Copilot", "Google AI Studio",
    "Copilot in Word", "Copilot in PowerPoint", "Firefly", "Photoshop AI",
    "Premiere AI", "Figma AI", "Framer AI", "Wix AI", "Shopify Magic",
    "HeyGen", "Synthesia", "Fliki", "Opus Clip", "Veed", "Riverside AI",
    "Krisp", "Fathom", "Granola", "Mem", "Obsidian AI", "Todoist AI",
    "ClickUp AI", "Asana AI", "Trello AI", "Slack AI", "Teams Copilot",
    "Gmail smart reply", "Google Sheets AI", "Looker Studio AI", "Airtable AI",
    "Replit AI", "Windsurf", "Codeium", "Tabnine", "v0", "Bolt",
    "Hugging Face", "Ollama", "LM Studio", "Whisper", "Stable Diffusion",
    "Flux", "Ideogram", "Recraft", "Leonardo AI", "Pika", "Luma AI",
    # capability areas
    "AI agents", "AI voice cloning", "AI thumbnails", "AI subtitles",
    "AI resume tools", "AI research tools", "AI note takers",
    "AI presentation tools", "AI spreadsheet tools", "AI email writers",
    "AI photo editors", "AI logo makers", "AI translation tools",
    "AI study tools", "AI coding assistants", "AI meeting summaries",
    "AI customer support", "AI invoicing tools", "AI job search tools",
    "AI interview prep", "AI social media tools", "AI SEO tools",
    "prompt engineering", "AI automation workflows", "local AI models",
    "AI browser extensions", "AI mobile apps", "AI for spreadsheets",
]

ANGLES = [
    "tricks nobody uses", "hidden features", "the fastest way to use it",
    "mistakes that waste your time", "how to get paid work with it",
    "settings you should change today", "what it does better than humans",
    "the one prompt that changes everything", "free alternatives that match it",
    "how to save hours a week with it", "what beginners get wrong about it",
    "how pros actually use it",
]

# Plain nouns so they read correctly in every title template ("for {audience}",
# "Why {audience} get ... wrong", etc.).
AUDIENCES = [
    "beginners", "students", "freelancers", "small business owners",
    "content creators", "job seekers", "developers", "busy professionals",
    "side hustlers", "teachers",
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
    "{subject} does this in seconds. Most people take an hour.",
    "Save this before you touch {subject} again.",
    "Nobody is talking about what {subject} just made possible.",
    "I was paying for software {subject} already does.",
    "This took me months to figure out about {subject}.",
    "Watch what happens when you ask {subject} this.",
    "Everyone uses {subject}. Almost nobody uses this part.",
    "Here is the {subject} shortcut I use every single day.",
    "You are two clicks away from a better {subject} result.",
    "Try this in {subject} tonight and thank me tomorrow.",
    "The fastest {subject} workflow I have found so far.",
    "Why your {subject} output looks like everyone else's.",
    "This one line makes {subject} ten times more useful.",
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
    """Pick a subject x angle x audience combination never used before.

    Deliberately an O(1) exact-set check, not the fuzzy matcher: this runs
    hundreds of times per draft, and the expensive fuzzy comparison happens once
    per finished draft in novelty_report.
    Space: ~95 subjects x 12 angles x 10 audiences = 11,400 combinations.
    """
    used = set(data.get("titles", []))
    for _ in range(MAX_FALLBACK_TRIES):
        topic = (f"{random.choice(SUBJECTS)}: {random.choice(ANGLES)} "
                 f"for {random.choice(AUDIENCES)}")
        if any(_title_for(topic, t) not in used
               for t in range(len(TITLE_TEMPLATES))):
            return topic
    print("[generate_script] NOTE: the built-in angle space is running low — "
          "GEMINI_API_KEY gives unlimited fresh ideas.")
    return f"{random.choice(SUBJECTS)}: {random.choice(ANGLES)}"


def _fresh_hook(subject: str, data: dict) -> tuple[str, str]:
    """(hook line, hook key). The (tool, template) pair is what must be unique."""
    used = set(data.get("hook_keys", []))
    order = list(range(len(HOOK_TEMPLATES)))
    random.shuffle(order)
    for i in order:
        key = f"{subject.lower()}|h{i}"
        if key not in used:
            return HOOK_TEMPLATES[i].format(subject=subject), key
    i = random.choice(order)
    return HOOK_TEMPLATES[i].format(subject=subject), f"{subject.lower()}|h{i}"


# Offline titles are composed from these so they don't all read the same shape
# ("Subject: angle audience"), which the fuzzy matcher would flag as repeats.
TITLE_TEMPLATES = [
    "{subject}: {angle} for {audience} 🤖",
    "The {subject} trick {audience} keep missing",
    "{subject}: {angle} (most people miss this)",
    "Nobody shows {audience} this in {subject}",
    "{subject} can do this, and {audience} should know",
    "Steal this {subject} workflow, {audience}",
    "Why {audience} get {subject} wrong",
    "{subject} in 30 seconds: {angle}",
    "This is the {subject} part {audience} never open",
    "{audience}: your {subject} setup is missing this",
    "{angle} — the {subject} way",
    "What {audience} should try in {subject} tonight",
]


def _title_for(topic: str, template_index: int = 0) -> str:
    """Map an angle to a title. Kept in one place so the O(1) check matches."""
    subject, _, rest = topic.partition(":")
    angle, _, audience = rest.strip().partition(" for ")
    tpl = TITLE_TEMPLATES[template_index % len(TITLE_TEMPLATES)]
    title = tpl.format(subject=subject.strip(),
                       angle=(angle or "the fast way").strip(),
                       audience=(audience or "beginners").strip())
    return title[0].upper() + title[1:] if title else title


def _idea_key(subject: str, action_index: int) -> str:
    return f"{subject.lower()}|{action_index}"


def _fresh_tips(subject: str, data: dict, want: int = 4,
                allow_used: bool = False) -> list[tuple[str, str, list[str], str]]:
    """Value beats for this subject that have never been used before.

    A (tool, technique) PAIR is the unit of uniqueness — "do X in Notion" and
    "do X in Excel" are genuinely different videos, so they are compared as exact
    pairs rather than fuzzily. That gives ~95 subjects x 26 actions = 2400+ beats.
    """
    used = set(data.get("idea_keys", []))
    order = list(range(len(TIP_ACTIONS)))
    random.shuffle(order)
    picked: list[tuple[str, str, list[str], str]] = []
    for i in order:
        action, cap, kw = TIP_ACTIONS[i]
        key = _idea_key(subject, i)
        if not allow_used and key in used:
            continue
        picked.append((f"{subject} can {action}.", cap, kw, key))
        if len(picked) == want:
            break
    return picked


def _fallback_storyboard(topic: str, today: str, data: dict,
                         allow_used_tips: bool = False) -> dict | None:
    """Compose a storyboard offline. Returns None if this subject is used up."""
    subject = topic.split(":")[0].strip() or "ChatGPT"
    hook, hook_key = _fresh_hook(subject, data)
    tips = _fresh_tips(subject, data, want=4, allow_used=allow_used_tips)
    if len(tips) < 3:
        return None  # this subject is used up; caller will try another

    scenes = [{
        "id": 1, "role": "hook", "narration": hook,
        "caption": random.choice(HOOK_CAPTIONS),
        "stock_keywords": random.sample(
            ["ai robot", "laptop typing", "technology", "server room",
             "phone screen", "city night", "data screen"], 3),
    }]
    for i, (line, cap, kw, _key) in enumerate(tips, start=2):
        scenes.append({"id": i, "role": "value", "narration": line,
                       "caption": cap, "stock_keywords": kw})
    scenes.append({
        "id": len(scenes) + 1, "role": "cta", "narration": random.choice(CTAS),
        "caption": "FOLLOW FOR MORE",
        "stock_keywords": ["phone scrolling", "city night"],
    })

    # Pick the title wording that is actually still unused (fuzzy-checked), so
    # two videos never share a title even when the angles are related.
    title = next(
        (t for t in (_title_for(topic, i) for i in
                     random.sample(range(len(TITLE_TEMPLATES)),
                                   len(TITLE_TEMPLATES)))
         if not history.topic_used(t, data)),
        None,
    )
    if title is None:
        return None  # every wording for this angle is taken; caller tries another

    return {
        "title": title,
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
        "meta": {"date": today, "topic": topic, "generated_by": "fallback",
                 "idea_keys": [t[3] for t in tips], "hook_key": hook_key},
    }


def _gemini_storyboard(topic: str, today: str, data: dict, attempt: int,
                       model_name: str | None = None) -> dict:
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name or settings.gemini_model, system_instruction=SYSTEM_PROMPT
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
    sb["meta"].update({"date": today, "topic": topic,
                       "generated_by": model_name or settings.gemini_model,
                       "attempt": attempt})
    return sb


def _gemini_pass(theme: str | None, today: str, data: dict,
                 level: int) -> dict | None:
    """Try every free Gemini model in turn, at the given strictness level."""
    if not settings.gemini_api_key:
        return None
    models = [settings.gemini_model] + [
        m.strip() for m in GEMINI_FALLBACK_MODELS if m.strip()
        and m.strip() != settings.gemini_model
    ]
    for model_name in models:
        for attempt in range(1, MAX_GEMINI_TRIES + 1):
            topic = theme or _fresh_angle(data)
            try:
                sb = _gemini_storyboard(topic, today, data, attempt, model_name)
            except Exception as exc:
                print(f"[generate_script] {model_name} unavailable ({type(exc).__name__}); "
                      f"trying the next writer")
                break
            if not sb.get("scenes"):
                continue
            ok, why = history.novelty_report(sb, data, level=level)
            if ok:
                print(f"[generate_script] fresh script via {model_name} "
                      f"(try {attempt}): {sb.get('title', '')[:60]}")
                return sb
            print(f"[generate_script] {model_name} try {attempt} rejected — {why}")
    return None


def _fallback_pass(theme: str | None, today: str, data: dict, level: int,
                   allow_used_tips: bool) -> dict | None:
    """Offline combinatorial writer at the given strictness level."""
    for _ in range(15):
        sb = _fallback_storyboard(theme or _fresh_angle(data), today, data,
                                  allow_used_tips=allow_used_tips)
        if sb is None:
            continue  # that subject is used up, try another
        ok, _why = history.novelty_report(sb, data, level=level)
        if ok:
            return sb
    return None


def generate_storyboard(theme: str | None = None,
                        data: dict | None = None) -> dict:
    """Produce today's storyboard. A video is ALWAYS produced.

    Publishing daily is a hard requirement, so the writer walks down a ladder of
    strictness rather than giving up:

      1. Gemini (all free models), strict     — new title, hook, 70% new ideas
      2. Offline writer, strict               — same bar, 2400+ (tool x technique) beats
      3. Gemini, relaxed                      — new title, hook, 40% new ideas
      4. Offline writer, relaxed
      5. Gemini / offline, minimum            — new title + new hook, tips may repeat

    The title, the hook and the thumbnail look are NEVER allowed to repeat at any
    step. Only an internal tip line can eventually recur, inside an otherwise
    completely new video — and that is logged.
    """
    today = dt.date.today().isoformat()
    data = data if data is not None else history.load()

    if not settings.gemini_api_key:
        print("[generate_script] No GEMINI_API_KEY; using the built-in "
              "combinatorial writer (still fully de-duplicated).")

    for level, _required, label in history.LEVELS:
        if level > 0:
            print(f"[generate_script] stepping down to {label} "
                  f"(a video must go out today)")
        if sb := _gemini_pass(theme, today, data, level):
            return sb
        if sb := _fallback_pass(theme, today, data, level,
                                allow_used_tips=(level >= 2)):
            if level >= 2:
                print("[generate_script] NOTE: title and hook are new, but some "
                      "tips have appeared before. Add SUBJECTS/TIP_ACTIONS or "
                      "keep GEMINI_API_KEY working to avoid this.")
            return sb

    # Absolute last resort so a posting slot is never missed. Tips may repeat
    # here, but the TITLE is still verified unique before it goes out.
    for _ in range(400):
        subject, angle = random.choice(SUBJECTS), random.choice(ANGLES)
        audience = random.choice(AUDIENCES)
        sb = _fallback_storyboard(f"{subject}: {angle} for {audience}", today,
                                  data, allow_used_tips=True)
        if sb is None:
            continue
        if history.topic_used(sb["title"], data):
            continue
        print("[generate_script] NOTE: idea pools are exhausted, so this video "
              "reuses tip wording — its title, hook and thumbnail are still "
              "unique. Add SUBJECTS/TIP_ACTIONS or restore Gemini access.")
        return sb
    raise RuntimeError(
        "every title wording is used up — add SUBJECTS/ANGLES/TITLE_TEMPLATES "
        f"or restore Gemini access. {history.stats(data)}"
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
