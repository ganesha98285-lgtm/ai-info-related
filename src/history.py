"""Lifelong memory for the channel — nothing is ever published twice.

Everything the channel has ever used is recorded in `content/history.json`,
which the daily workflow commits back to the repo. That makes the memory
permanent across runs (GitHub Actions caches expire; a committed file does not).

What is tracked, and how a repeat is blocked:

| Thing        | How duplicates are caught                                   |
|--------------|-------------------------------------------------------------|
| topic/title  | fuzzy similarity vs every past title (>=0.72 = duplicate)   |
| hook line    | fuzzy similarity vs every past hook                          |
| idea/tip     | fuzzy similarity vs every past spoken value line             |
| stock clip   | exact clip id (px123 / pb456) — never reused while supply lasts |
| thumbnail    | layout+palette combo, plus a different source frame each time |

It also records performance (views/likes per video) so the script writer can be
told what worked — learning WITHOUT repeating: "match this style, new idea".

Honest limitation: free stock libraries are finite. Clips are kept unique for as
long as supply allows; if a keyword pool is genuinely exhausted the oldest clip
may be reused, and that is logged loudly rather than hidden.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from config import settings

HISTORY_FILE = Path(
    __import__("os").getenv("HISTORY_FILE", "")
    or settings.content_dir / "history.json"
)

# Similarity above this counts as "already done".
TOPIC_THRESHOLD = 0.72
HOOK_THRESHOLD = 0.70
IDEA_THRESHOLD = 0.78

_STOP = {"the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "is",
         "are", "you", "your", "with", "that", "this", "it", "my", "me"}


@lru_cache(maxsize=100_000)
def _norm(text: str) -> str:
    """Lowercase, strip punctuation and filler words for fair comparison."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return " ".join(w for w in words if w not in _STOP)


@lru_cache(maxsize=100_000)
def _tokens(text: str) -> frozenset:
    return frozenset(_norm(text).split())


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _overlap(a: frozenset, b: frozenset) -> float:
    """Cheap Jaccard pre-filter so we only run the costly matcher when needed."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _blank() -> dict:
    return {"version": 3, "titles": [], "hooks": [], "ideas": [],
            "idea_keys": [], "hook_keys": [], "clips": {}, "thumb_styles": {},
            "uploads": []}


def load() -> dict:
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text("utf-8"))
            for k, v in _blank().items():
                data.setdefault(k, v)
            return data
        except json.JSONDecodeError as exc:
            print(f"[history] corrupt history file ({exc}); starting fresh")
    return _blank()


def save(data: dict) -> Path:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False),
                            "utf-8")
    return HISTORY_FILE


def stats(data: dict | None = None) -> str:
    d = data or load()
    return (f"{len(d['titles'])} titles, {len(d['hooks'])} hooks, "
            f"{len(d['ideas'])} ideas, {len(d['clips'])} clips used")


# --------------------------------------------------------------------------- #
# duplicate detection
# --------------------------------------------------------------------------- #
def is_duplicate(text: str, pool: list[str], threshold: float) -> str | None:
    """Return the matching past entry if `text` is too close to something used.

    Two-stage for speed: a set-overlap pre-filter rejects most candidates in
    microseconds, and only the plausible ones go through SequenceMatcher. This
    keeps the check fast even after thousands of published videos.
    """
    n = _norm(text)
    if not n:
        return None
    toks = _tokens(text)
    # Roughly the minimum word overlap a real duplicate must have.
    min_overlap = max(0.25, threshold - 0.30)
    for past in pool:
        if _overlap(toks, _tokens(past)) < min_overlap:
            continue
        if _similar(n, _norm(past)) >= threshold:
            return past
    return None


def topic_used(title: str, data: dict) -> str | None:
    return is_duplicate(title, data["titles"], TOPIC_THRESHOLD)


def hook_used(hook: str, data: dict) -> str | None:
    return is_duplicate(hook, data["hooks"], HOOK_THRESHOLD)


def idea_used(line: str, data: dict) -> str | None:
    return is_duplicate(line, data["ideas"], IDEA_THRESHOLD)


def key_used(key: str, data: dict) -> bool:
    """Exact-match check for a composed idea key like 'ChatGPT|summarise_doc'.

    Used by the offline writer: the same technique applied to a DIFFERENT tool is
    a legitimately different video, so those are compared as exact pairs instead
    of fuzzily (which would wrongly flag them as the same sentence).
    """
    return key in set(data.get("idea_keys", []))


def record_keys(keys: list[str], data: dict) -> None:
    data.setdefault("idea_keys", []).extend(k for k in keys if k)


# Strictness levels. Level 0 is the ideal; the writer walks down this ladder
# only if it cannot produce anything better, because publishing every day is a
# hard requirement. Title, hook and thumbnail are NEVER allowed to repeat at any
# level — only an internal tip line may repeat inside an otherwise-new video.
LEVELS = [
    (0, 0.70, "strict: new title, new hook, 70% new ideas"),
    (1, 0.40, "relaxed: new title, new hook, 40% new ideas"),
    (2, 0.00, "minimum: new title + new hook (tips may repeat)"),
]


def novelty_report(storyboard: dict, data: dict,
                   level: int = 0) -> tuple[bool, str]:
    """Is this storyboard new enough at the given strictness level?

    Two comparison modes, because they are different situations:

    * An LLM-written script can be genuinely original, so its title, hook and
      ideas are compared FUZZILY — a reworded repeat is rejected.
    * The offline writer composes from templates, so unique WORDING cannot last
      forever. There, uniqueness is enforced on the exact (tool, template) pair:
      the same technique or hook shape applied to a different tool is a different
      video. Wording patterns may echo, which is why this path is only a backstop
      for days when the LLM is unavailable.
    """
    meta = storyboard.get("meta", {})
    offline = meta.get("generated_by") == "fallback"
    title = storyboard.get("title", "")
    scenes = storyboard.get("scenes", [])
    hook = next((s.get("narration") for s in scenes
                 if s.get("role") == "hook"), "")
    values = [s.get("narration", "") for s in scenes
              if s.get("role") not in ("hook", "cta")]

    # Non-negotiable in both modes and at every level: a title never repeats.
    dup = topic_used(title, data)
    if dup:
        return False, f"title already used ('{dup[:50]}')"

    if offline:
        hk = meta.get("hook_key")
        if hk and hk in set(data.get("hook_keys", [])):
            return False, "this tool + hook combination was already used"
        # _fresh_tips already guarantees the (tool, technique) pairs are new.
        return True, "offline: new title + new tool/hook pair"

    dup = hook_used(hook, data)
    if dup:
        return False, f"hook already used ('{dup[:50]}')"

    required = next((r for lvl, r, _ in LEVELS if lvl == level), 0.0)
    if values and required > 0:
        fresh = [v for v in values if not idea_used(v, data)]
        if len(fresh) < max(1, int(len(values) * required)):
            return False, (f"only {len(fresh)}/{len(values)} ideas are new "
                           f"(need {int(required * 100)}%)")
    return True, next((d for lvl, _, d in LEVELS if lvl == level), "ok")


# --------------------------------------------------------------------------- #
# recording
# --------------------------------------------------------------------------- #
def record_storyboard(storyboard: dict, data: dict) -> None:
    scenes = storyboard.get("scenes", [])
    title = storyboard.get("title", "")
    if title:
        data["titles"].append(title)
    for s in scenes:
        role, line = s.get("role"), s.get("narration", "")
        if not line:
            continue
        if role == "hook":
            data["hooks"].append(line)
        elif role != "cta":
            data["ideas"].append(line)
    meta = storyboard.get("meta", {})
    record_keys(meta.get("idea_keys", []), data)
    if hk := meta.get("hook_key"):
        data.setdefault("hook_keys", []).append(hk)


def used_clip_ids(data: dict) -> set[str]:
    return set(data["clips"].keys())


def record_clip(clip_id: str, data: dict) -> None:
    data["clips"][clip_id] = dt.date.today().isoformat()


def oldest_clips(data: dict, keep_recent_days: int = 365) -> set[str]:
    """Clip ids last used longer ago than `keep_recent_days` (reuse of last resort)."""
    cutoff = dt.date.today() - dt.timedelta(days=keep_recent_days)
    old = set()
    for cid, when in data["clips"].items():
        try:
            if dt.date.fromisoformat(when) < cutoff:
                old.add(cid)
        except ValueError:
            continue
    return old


def next_thumb_style(data: dict, n_layouts: int, n_palettes: int) -> tuple[int, int]:
    """Least-used layout+palette combo, so no two thumbnails look the same."""
    best, best_count = (0, 0), None
    for layout in range(n_layouts):
        for palette in range(n_palettes):
            key = f"{layout}-{palette}"
            count = data["thumb_styles"].get(key, 0)
            if best_count is None or count < best_count:
                best, best_count = (layout, palette), count
    key = f"{best[0]}-{best[1]}"
    data["thumb_styles"][key] = data["thumb_styles"].get(key, 0) + 1
    return best


def record_upload(video_id: str, storyboard: dict, data: dict) -> None:
    scenes = storyboard.get("scenes", [])
    data["uploads"].append({
        "video_id": video_id,
        "title": storyboard.get("title", ""),
        "hook": next((s.get("narration") for s in scenes
                      if s.get("role") == "hook"), ""),
        "date": dt.date.today().isoformat(),
        "views": 0,
        "likes": 0,
    })


# --------------------------------------------------------------------------- #
# learning
# --------------------------------------------------------------------------- #
def refresh_stats(data: dict) -> None:
    """Pull view counts for past uploads so we can learn what worked.

    Cheap on quota: videos.list costs 1 unit per call (50 ids per call), versus
    1600 for an upload.
    """
    ids = [u["video_id"] for u in data["uploads"] if u.get("video_id")]
    if not ids:
        return
    try:
        from src import upload_youtube

        fetched = upload_youtube.get_stats(ids[-200:])
    except Exception as exc:
        print(f"[history] could not refresh stats ({exc}); learning skipped")
        return
    if not fetched:
        return
    for u in data["uploads"]:
        s = fetched.get(u.get("video_id"))
        if s:
            u["views"], u["likes"] = s.get("views", 0), s.get("likes", 0)
    print(f"[history] refreshed stats for {len(fetched)} videos")


def top_performers(data: dict, n: int = 5) -> list[dict]:
    """Best-performing past videos (views per day since publish)."""
    today = dt.date.today()
    scored = []
    for u in data["uploads"]:
        if not u.get("views"):
            continue
        try:
            age = max(1, (today - dt.date.fromisoformat(u["date"])).days)
        except ValueError:
            age = 1
        scored.append((u["views"] / age, u))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [u for _, u in scored[:n]]


def learning_brief(data: dict, n: int = 5) -> str:
    """Human-readable note for the script writer: what worked, without copying."""
    best = top_performers(data, n)
    if not best:
        return ""
    lines = [f'- "{u["title"][:70]}" (hook: "{u["hook"][:60]}") — {u["views"]} views'
             for u in best]
    return ("These past videos performed best on this channel:\n"
            + "\n".join(lines)
            + "\nMatch their STYLE and structure (hook shape, pacing, "
              "specificity) but the topic, hook and every tip MUST be brand new.")


def avoid_brief(data: dict, titles: int = 60, hooks: int = 40) -> str:
    """The 'never do this again' list handed to the script writer."""
    t = data["titles"][-titles:]
    h = data["hooks"][-hooks:]
    if not t and not h:
        return ""
    out = []
    if t:
        out.append("ALREADY PUBLISHED TITLES (do not repeat or reword these):\n"
                   + "\n".join(f"- {x}" for x in t))
    if h:
        out.append("ALREADY USED HOOKS (write a completely different one):\n"
                   + "\n".join(f"- {x}" for x in h))
    return "\n\n".join(out)


if __name__ == "__main__":
    print(f"[history] {HISTORY_FILE}")
    print(f"[history] {stats()}")
