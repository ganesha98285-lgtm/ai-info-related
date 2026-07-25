"""Free HD stock-footage fetcher (Pexels, with Pixabay fallback).

This is what makes the shorts look like a PROPER video instead of a slideshow:
every beat is real 1080p+ footage, picked by keywords from the script.

Both APIs are free (just need a free key):
  * Pexels  -> https://www.pexels.com/api/   (PEXELS_API_KEY)
  * Pixabay -> https://pixabay.com/api/docs/ (PIXABAY_API_KEY)

Licensing: both allow free commercial use without attribution, but YouTube
monetization needs YOUR script/voice/edit on top (which this pipeline does).
"""
from __future__ import annotations

import hashlib
import random
from pathlib import Path

from config import settings


def _requests():
    """Imported lazily so the module loads even before deps are installed."""
    import requests

    return requests

TIMEOUT = 45
UA = {"User-Agent": "ai-shorts-pipeline/1.0"}


# ─────────────────────────────────── Pexels ──────────────────────────────────
def _pexels_search(query: str, per_page: int = 12) -> list[dict]:
    if not settings.pexels_api_key:
        return []
    try:
        r = _requests().get(
            "https://api.pexels.com/videos/search",
            params={
                "query": query,
                "per_page": per_page,
                "orientation": "portrait",  # best for 9:16 shorts
                "size": "medium",
            },
            headers={"Authorization": settings.pexels_api_key, **UA},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            print(f"[stock] pexels {r.status_code}: {r.text[:120]}")
            return []
        return r.json().get("videos", []) or []
    except Exception as exc:
        print(f"[stock] pexels failed ({exc})")
        return []


def _pexels_best_file(video: dict) -> str | None:
    """Pick the highest-quality file that is still <= 1920 tall-ish (HD)."""
    files = [f for f in video.get("video_files", []) if f.get("link")]
    if not files:
        return None
    hd = [f for f in files if (f.get("height") or 0) >= 1080]
    pool = hd or files
    pool.sort(key=lambda f: (f.get("height") or 0))
    return pool[len(pool) // 2 if hd else -1]["link"]


# ────────────────────────────────── Pixabay ──────────────────────────────────
def _pixabay_search(query: str, per_page: int = 12) -> list[dict]:
    if not settings.pixabay_api_key:
        return []
    try:
        r = _requests().get(
            "https://pixabay.com/api/videos/",
            params={
                "key": settings.pixabay_api_key,
                "q": query,
                "per_page": max(3, per_page),
                "video_type": "all",
            },
            headers=UA,
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return []
        return r.json().get("hits", []) or []
    except Exception as exc:
        print(f"[stock] pixabay failed ({exc})")
        return []


def _pixabay_best_file(hit: dict) -> str | None:
    vids = hit.get("videos") or {}
    for key in ("large", "medium", "small"):
        if vids.get(key, {}).get("url"):
            return vids[key]["url"]
    return None


# ─────────────────────────────────── public ──────────────────────────────────
def _download(url: str, dest: Path) -> bool:
    try:
        with _requests().get(url, stream=True, timeout=180, headers=UA) as r:
            if r.status_code != 200:
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    if chunk:
                        f.write(chunk)
        return dest.exists() and dest.stat().st_size > 40_000
    except Exception as exc:
        print(f"[stock] download failed ({exc})")
        return False


def _candidates(queries: list[str]) -> list[tuple[str, str, str]]:
    """(clip_id, download_url, query) for every result across all queries."""
    out: list[tuple[str, str, str]] = []
    for q in queries:
        # Pexels first (better quality + portrait filter), then Pixabay.
        for video in _pexels_search(q):
            link = _pexels_best_file(video)
            if link:
                out.append((f"px{video.get('id')}", link, q))
        for hit in _pixabay_search(q):
            link = _pixabay_best_file(hit)
            if link:
                out.append((f"pb{hit.get('id')}", link, q))
    return out


def fetch_clip(keywords: list[str], out_dir: Path, used: set[str],
               reusable: set[str] | None = None) -> Path | None:
    """Download one HD stock clip matching any of the keywords.

    `used` = every clip id the CHANNEL has ever used (seeded from
    content/history.json) plus the ones picked earlier in this video, so no shot
    is ever repeated while fresh supply exists. New picks are added to it.

    `reusable` = clip ids last used long enough ago that reusing one is the least
    bad option when a keyword pool is genuinely exhausted. Any such reuse is
    logged loudly rather than hidden.
    """
    queries = [k for k in (keywords or []) if k] or ["technology"]
    random.shuffle(queries)
    cands = _candidates(queries)

    # Pass 1 — strictly never-used clips.
    for cid, link, q in cands:
        if cid in used:
            continue
        dest = out_dir / f"{cid}.mp4"
        if _download(link, dest):
            used.add(cid)
            print(f"[stock] '{q}' -> {'pexels' if cid[:2] == 'px' else 'pixabay'} {cid}")
            return dest

    # Pass 2 — nothing new left for these keywords: reuse the oldest clip.
    for cid, link, q in cands:
        if reusable and cid in reusable:
            dest = out_dir / f"{cid}.mp4"
            if _download(link, dest):
                used.add(cid)
                print(f"[stock] ⚠ keyword pool exhausted for '{q}' — reusing "
                      f"long-unused clip {cid}. Broaden stock_keywords to avoid this.")
                return dest

    print(f"[stock] no unused clip found for {queries[:3]}")
    return None


def cache_key(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


def have_keys() -> bool:
    """True if at least one stock provider is configured."""
    return bool(settings.pexels_api_key or settings.pixabay_api_key)
