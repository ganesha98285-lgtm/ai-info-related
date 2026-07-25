"""Turn a confirmed trending story into a Shorts script + full SEO package.

Two rules make this safe and rank-able:

1. FACTS ONLY FROM THE SOURCE. The writer is given the headline and summary and
   is forbidden from adding numbers, names, causes or outcomes that are not in
   them. Sources are credited in the description. Unverifiable phrasing is
   softened by src.safety.clean_claims().

2. SEO IS BUILT, NOT GUESSED. Title, description, tags and hashtags are all
   assembled from the story's own keywords plus the live trending terms, in the
   order YouTube actually reads them (see build_seo).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import re

from config import settings
from src import history, safety

# --------------------------------------------------------------------------- #
# SEO building blocks
# --------------------------------------------------------------------------- #
# Shown ABOVE the title on YouTube, so the first two must be broad + topical.
BASE_HASHTAGS = ["#shorts", "#news"]
TOPIC_HASHTAGS = {
    "crypto": ["#crypto", "#bitcoin", "#ethereum", "#cryptonews"],
    "market": ["#stocks", "#stockmarket", "#investing", "#finance"],
    "tech": ["#tech", "#technology", "#ai", "#technews"],
    "science": ["#science", "#space", "#research"],
    "business": ["#business", "#economy", "#money"],
    "world": ["#worldnews", "#breakingnews", "#global"],
}
REACH_HASHTAGS = ["#viral", "#trending", "#fyp", "#todaynews", "#update",
                  "#explained", "#facts", "#shortsfeed"]

# Hook shapes for a news short. Curiosity first — retention is the whole game.
HOOK_SHAPES = [
    "This is blowing up right now.",
    "Everyone is talking about this today.",
    "Here is what just happened.",
    "You will want to hear this one.",
    "This changed in the last few hours.",
    "Nobody saw this coming today.",
    "This is the story everyone is sharing.",
    "Stay till the end for the part people missed.",
    "Here is the update you actually need.",
    "This just moved the whole market.",
]

CTAS = [
    "Follow for the news that actually matters.",
    "Follow so you hear it here first.",
    "Subscribe, we cover this every single day.",
    "Follow for daily updates in 30 seconds.",
]

# Visual fallbacks per category (Pexels has plenty of all of these).
VISUALS = {
    "crypto": ["bitcoin", "crypto trading screen", "candlestick chart",
               "computer server", "digital money"],
    "market": ["stock market screen", "trading floor", "financial charts",
               "city skyline business", "newspaper business"],
    "tech": ["data center", "robot", "laptop code", "circuit board",
             "smartphone screen"],
    "science": ["laboratory", "telescope night sky", "microscope", "space earth"],
    "business": ["office building", "handshake business", "shipping port",
                 "factory production"],
    "world": ["world map", "city crowd", "airport terminal", "flags",
              "satellite earth"],
}

CATEGORY_WORDS = {
    "crypto": ["bitcoin", "btc", "ethereum", "eth", "crypto", "token", "coin",
               "blockchain", "binance", "solana", "xrp", "stablecoin"],
    "market": ["stocks", "stock", "market", "nasdaq", "s&p", "dow", "shares",
               "index", "rally", "selloff", "earnings", "inflation", "fed",
               "rates", "gold", "oil"],
    "tech": ["ai", "openai", "google", "apple", "microsoft", "nvidia", "chip",
             "app", "software", "startup", "robot", "model", "gpt", "meta"],
    "science": ["nasa", "space", "study", "researchers", "scientists", "mars",
                "telescope", "discovery", "climate"],
    "business": ["company", "ceo", "revenue", "profit", "layoffs", "merger",
                 "acquisition", "ipo", "bank", "economy", "jobs"],
}


# Words that add nothing to search or hashtags (and numbers, which produce
# junk tags like "#000" from "90,000").
WEAK_TAGS = {
    "past", "surges", "hits", "says", "after", "over", "into", "amid", "new",
    "more", "than", "with", "from", "this", "that", "here", "just", "now",
    "today", "week", "year", "report", "reports", "reported", "update", "top",
    "tops", "beats", "jumps", "breaks", "hitting", "another", "first", "next",
    "could", "would", "about", "against", "before", "while", "still",
}


def _useful_tag(word: str) -> bool:
    w = (word or "").strip().lower()
    if len(w) < 4 or w in WEAK_TAGS:
        return False
    return not w.isdigit() and any(c.isalpha() for c in w)


def categorise(text: str) -> str:
    low = (text or "").lower()
    best, hits = "world", 0
    for cat, words in CATEGORY_WORDS.items():
        n = sum(1 for w in words if w in low)
        if n > hits:
            best, hits = cat, n
    return best


def visual_keywords(topic_keywords: list[str], category: str) -> list[str]:
    """Real stock footage exists for generic visuals, not for today's event."""
    base = VISUALS.get(category, VISUALS["world"])
    picks = random.sample(base, min(3, len(base)))
    # A couple of the story's own nouns can still find good b-roll.
    extra = [k for k in (topic_keywords or []) if len(k) > 4][:2]
    return picks + extra


def build_seo(headline: str, summary: str, category: str,
              keywords: list[str], source_urls: list[str],
              trending_terms: list[str] | None = None) -> dict:
    """Title / description / tags / hashtags, in the order YouTube reads them."""
    # TITLE: keyword-first, curiosity, <= ~70 visible chars, then #shorts.
    core = re.sub(r"\s+", " ", headline).strip().rstrip(".")
    if len(core) > 66:
        core = core[:63].rsplit(" ", 1)[0] + "..."
    title = f"{core} #shorts"

    tags = TOPIC_HASHTAGS.get(category, TOPIC_HASHTAGS["world"])
    hashtags = BASE_HASHTAGS + tags[:3]
    for t in (trending_terms or []):
        h = "#" + re.sub(r"[^a-z0-9]", "", t.lower())[:20]
        if _useful_tag(h.lstrip("#")) and h not in hashtags:
            hashtags.append(h)
    hashtags += [h for h in REACH_HASHTAGS if h not in hashtags]
    hashtags = hashtags[:12]

    # SEARCH TAGS: the story's own words + category terms (YouTube reads these).
    search_tags = []
    for w in keywords + CATEGORY_WORDS.get(category, [])[:6]:
        w = w.strip().lower()
        if _useful_tag(w) and w not in search_tags:
            search_tags.append(w)
    search_tags = search_tags[:15]

    # DESCRIPTION: first ~150 chars carry the keywords, then context, then
    # attribution (important for a news channel), then CTA + hashtags.
    first = f"{core}. Here is what is happening and why it matters."
    body = re.sub(r"\s+", " ", summary or "").strip()[:300]
    src = "\n".join(f"Source: {u}" for u in (source_urls or [])[:3])
    desc = "\n\n".join(x for x in [
        first,
        body,
        "Reported from public news sources — details may develop.",
        src,
        random.choice(CTAS),
        " ".join(hashtags),
    ] if x)

    return {"title": title[:100], "description": desc,
            "hashtags": hashtags, "keywords": search_tags}


# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """You write 30-45 second YouTube Shorts news scripts for a
fast, factual channel that covers what is trending right now.

HARD RULES — breaking these gets the channel banned:
- Use ONLY the facts in the headline and summary you are given. Never invent a
  number, name, date, cause, quote or outcome.
- If a detail is unclear, say "reports say" or leave it out.
- No opinions, no predictions, no medical/financial advice, no blame.
- Neutral tone. No outrage bait. Never mention death, injury or violence.

STYLE:
- Scene 1 is a HOOK: max 12 words, curiosity, no clickbait lie.
- Then 3-5 scenes explaining WHAT happened, WHY it matters, WHAT is next.
- Spoken lines 8-18 words, plain spoken English, fast pacing.
- On-screen caption text: 3-6 words, ASCII only, ALL CAPS style.
- stock_keywords: 2-4 GENERIC visual search terms that real stock footage will
  have (e.g. "stock market screen", "data center", "city crowd"). Never expect
  footage of today's specific event.
- Last scene is a short follow/subscribe CTA.

Return STRICT JSON only:
{"scenes":[{"id":1,"role":"hook","narration":"...","caption":"...",
"stock_keywords":["..."]},{"id":2,"role":"value","narration":"...",
"caption":"...","stock_keywords":["..."]},{"id":6,"role":"cta",
"narration":"...","caption":"FOLLOW FOR MORE","stock_keywords":["..."]}]}
"""


def _llm_scenes(topic, category: str) -> list[dict] | None:
    """Ask Gemini, then Groq, for the scene list. None if both unavailable."""
    ask = (f"HEADLINE: {topic.headline}\n"
           f"SUMMARY: {topic.summary or '(no summary available)'}\n"
           f"CATEGORY: {category}\n"
           f"Write the script using only these facts.")

    if settings.gemini_api_key:
        models = [settings.gemini_model, "gemini-2.0-flash-lite",
                  "gemini-1.5-flash"]
        for name in models:
            try:
                import google.generativeai as genai

                genai.configure(api_key=settings.gemini_api_key)
                model = genai.GenerativeModel(
                    name, system_instruction=SYSTEM_PROMPT)
                resp = model.generate_content(
                    ask,
                    generation_config={"response_mime_type": "application/json"},
                )
                scenes = json.loads(resp.text).get("scenes")
                if scenes:
                    print(f"[news] script via {name}")
                    return scenes
            except Exception as exc:
                print(f"[news] {name} failed ({type(exc).__name__})")

    if os.getenv("GROQ_API_KEY", "").strip():
        try:
            import requests

            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
                         "Content-Type": "application/json"},
                json={"model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                      "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                   {"role": "user", "content": ask}],
                      "response_format": {"type": "json_object"},
                      "temperature": 0.7},
                timeout=60,
            )
            r.raise_for_status()
            scenes = json.loads(r.json()["choices"][0]["message"]["content"]).get("scenes")
            if scenes:
                print("[news] script via Groq")
                return scenes
        except Exception as exc:
            print(f"[news] Groq failed ({type(exc).__name__})")
    return None


# Neutral framing lines used when there is no summary to draw on. They add NO
# facts — they only carry the video between beats.
FRAMING = [
    "That is the headline people are reacting to right now.",
    "It is spreading fast across feeds and group chats.",
    "Here is why it is getting so much attention.",
    "Reports are still coming in, so details may change.",
    "We are watching how this develops through the day.",
    "This is the part most people scrolled past.",
]


def _offline_scenes(topic, category: str) -> list[dict]:
    """No LLM available: narrate the source text itself, nothing invented.

    Every line is either the source headline, a sentence from the source summary,
    or a neutral framing line that states no facts at all. Lines that repeat what
    was already said are dropped, so no scene is a duplicate of another.
    """
    head = re.sub(r"\s+", " ", topic.headline).strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", topic.summary or "")
                 if len(s.strip()) > 30]
    # Drop summary sentences that just restate the headline.
    head_words = set(re.findall(r"[a-z0-9]{4,}", head.lower()))
    facts: list[str] = []
    for s in sentences:
        sw = set(re.findall(r"[a-z0-9]{4,}", s.lower()))
        if head_words and sw and len(head_words & sw) / len(head_words | sw) > 0.6:
            continue
        facts.append(s)

    framing = random.sample(FRAMING, len(FRAMING))
    scenes = [
        {"id": 1, "role": "hook", "narration": random.choice(HOOK_SHAPES),
         "caption": "TRENDING NOW",
         "stock_keywords": visual_keywords(topic.keywords, category)},
        {"id": 2, "role": "value", "narration": head[:170],
         "caption": "WHAT HAPPENED",
         "stock_keywords": visual_keywords(topic.keywords, category)},
    ]
    # Prefer real facts from the source; top up with neutral framing if needed.
    body = facts[:3] or []
    while len(body) < 2 and framing:
        body.append(framing.pop())
    for i, line in enumerate(body, start=3):
        scenes.append({"id": i, "role": "value", "narration": line[:170],
                       "caption": "THE DETAILS" if line in facts else "WHY IT MATTERS",
                       "stock_keywords": visual_keywords(topic.keywords, category)})
    scenes.append({"id": len(scenes) + 1, "role": "cta",
                   "narration": random.choice(CTAS),
                   "caption": "FOLLOW FOR MORE",
                   "stock_keywords": ["phone scrolling", "city night"]})
    return scenes


def build_storyboard(topic, trending_terms: list[str] | None = None) -> dict | None:
    """Full storyboard for one story, or None if it fails the safety gate."""
    category = categorise(f"{topic.headline} {topic.summary}")

    ok, why = safety.is_publishable(topic.headline, topic.summary)
    if not ok:
        print(f"[news] SKIP '{topic.headline[:60]}' -> {why}")
        return None

    scenes = _llm_scenes(topic, category) or _offline_scenes(topic, category)

    # Normalise + sanity-check every scene, and re-run safety on the final text.
    clean: list[dict] = []
    for i, sc in enumerate(scenes, start=1):
        line = safety.clean_claims(str(sc.get("narration") or "").strip())
        if not line:
            continue
        clean.append({
            "id": i,
            "role": sc.get("role") or ("hook" if i == 1 else "value"),
            "narration": line[:220],
            "caption": (str(sc.get("caption") or "TRENDING NOW")
                        .upper()[:28]),
            "stock_keywords": (sc.get("stock_keywords")
                               or visual_keywords(topic.keywords, category))[:4],
        })
    if len(clean) < 3:
        print(f"[news] SKIP '{topic.headline[:60]}' -> script too short")
        return None
    clean[-1]["role"] = "cta"

    spoken = " ".join(s["narration"] for s in clean)
    ok, why = safety.is_publishable(topic.headline, spoken)
    if not ok:
        print(f"[news] SKIP after writing '{topic.headline[:60]}' -> {why}")
        return None

    seo = build_seo(topic.headline, topic.summary, category, topic.keywords,
                    topic.urls, trending_terms)
    return {
        **seo,
        "scenes": clean,
        "meta": {"date": dt.date.today().isoformat(),
                 "topic": topic.headline,
                 "category": category,
                 "sources": sorted(set(topic.sources)),
                 "source_urls": topic.urls,
                 "score": topic.score,
                 "generated_by": "news"},
    }


# Categories that are both advertiser-friendly and well paid. Preferred when
# choosing between several safe stories.
PREFERRED = ["crypto", "market", "tech", "business", "science", "world"]


def pick_story(topics: list, hist: dict) -> object | None:
    """Best story that is safe AND not already covered.

    Not simply "the first one": every candidate is safety-checked first, then
    ranked by category value and how many sources confirmed it. Real news is
    heavy on conflict and politics, so most candidates get rejected — this walks
    the whole list instead of giving up after the top few.
    """
    safe: list[tuple[int, int, float, object]] = []
    skipped_unsafe = skipped_seen = 0

    for t in topics:
        if history.story_used(t.headline, t.urls, hist):
            skipped_seen += 1
            continue
        ok, why = safety.is_publishable(t.headline, t.summary)
        if not ok:
            skipped_unsafe += 1
            print(f"[news] unsafe: {t.headline[:58]} -> {why[:52]}")
            continue
        cat = categorise(f"{t.headline} {t.summary}")
        rank = PREFERRED.index(cat) if cat in PREFERRED else len(PREFERRED)
        safe.append((rank, -t.source_count, -t.score, t))

    print(f"[news] candidates: {len(safe)} safe, {skipped_unsafe} unsafe, "
          f"{skipped_seen} already covered")
    if not safe:
        return None
    safe.sort(key=lambda x: (x[0], x[1], x[2]))
    best = safe[0][3]
    print(f"[news] picked [{categorise(best.headline)}] "
          f"{best.source_count} source(s): {best.headline[:60]}")
    return best
