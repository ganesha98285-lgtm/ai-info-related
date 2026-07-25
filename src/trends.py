"""Find what is ACTUALLY trending right now, from free public sources.

No paid APIs and no keys: Google Trends RSS, Google News RSS, Reddit's public
JSON, Wikipedia's most-read feed, and (optionally) YouTube's own trending chart.

The important part is not fetching — it is CONFIRMATION. A single source can be
noise, a bot wave, or a local blip. A story is only accepted when it shows up in
at least `MIN_SOURCES` independent places, which is what separates "really
viral" from "one website wrote about it".

Output: ranked topic clusters, each with a headline, a short summary, the source
names, the source URLs (used for attribution in the description) and visual
keywords for stock-footage search.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

UA = {"User-Agent": "Mozilla/5.0 (compatible; viral-news-bot/1.0)"}
TIMEOUT = 25

GEO = os.getenv("TRENDS_GEO", "US")
LANG = os.getenv("TRENDS_LANG", "en")
MIN_SOURCES = int(os.getenv("MIN_TREND_SOURCES", "2"))

# Subreddits chosen for reach + advertiser-friendly subject matter.
SUBREDDITS = [s.strip() for s in os.getenv(
    "TREND_SUBREDDITS",
    "worldnews,technology,CryptoCurrency,stocks,science,UpliftingNews",
).split(",") if s.strip()]

# Google News topic feeds worth watching (high CPM subjects first).
NEWS_TOPICS = ["BUSINESS", "TECHNOLOGY", "SCIENCE", "WORLD"]

_STOP = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "is", "are",
    "was", "were", "be", "as", "at", "by", "with", "from", "that", "this",
    "it", "its", "his", "her", "their", "after", "over", "into", "amid",
    "says", "say", "said", "new", "up", "down", "out", "about", "how", "why",
    "what", "who", "will", "has", "have", "had", "not", "you", "your", "we",
    "us", "he", "she", "they", "but", "more", "than", "may", "can", "could",
}


def _requests():
    import requests

    return requests


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower())
            if w not in _STOP}


# --------------------------------------------------------------------------- #
@dataclass
class Signal:
    """One trending item from one source."""
    title: str
    source: str
    url: str = ""
    summary: str = ""
    weight: float = 1.0


@dataclass
class Topic:
    """A cluster of signals about the same story, from multiple sources."""
    headline: str
    summary: str = ""
    sources: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    score: float = 0.0

    @property
    def source_count(self) -> int:
        return len(set(self.sources))


# ------------------------------- fetchers ---------------------------------- #
def _get(url: str) -> str | None:
    try:
        r = _requests().get(url, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"[trends] {url.split('/')[2]} -> HTTP {r.status_code}")
            return None
        return r.text
    except Exception as exc:
        print(f"[trends] fetch failed ({type(exc).__name__}) {url.split('/')[2]}")
        return None


def google_trends() -> list[Signal]:
    """Today's trending searches for the target country."""
    xml = _get(f"https://trends.google.com/trending/rss?geo={GEO}")
    if not xml:
        return []
    out: list[Signal] = []
    try:
        root = ET.fromstring(xml)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            # traffic looks like "20,000+" — a rough popularity hint
            traffic = 1.0
            for child in item:
                if child.tag.endswith("approx_traffic") and child.text:
                    digits = re.sub(r"[^0-9]", "", child.text)
                    if digits:
                        traffic = 1.0 + min(len(digits) / 6.0, 1.5)
            news_title, news_url = "", ""
            for child in item.iter():
                if child.tag.endswith("news_item_title") and not news_title:
                    news_title = (child.text or "").strip()
                if child.tag.endswith("news_item_url") and not news_url:
                    news_url = (child.text or "").strip()
            out.append(Signal(title=news_title or title, source="google-trends",
                              url=news_url, summary=title, weight=traffic))
    except ET.ParseError:
        print("[trends] google-trends: bad XML")
    return out


def google_news() -> list[Signal]:
    """Breaking headlines, plus the high-value topic feeds."""
    out: list[Signal] = []
    feeds = [f"https://news.google.com/rss?hl={LANG}-{GEO}&gl={GEO}"
             f"&ceid={GEO}:{LANG}"]
    feeds += [f"https://news.google.com/rss/headlines/section/topic/{t}"
              f"?hl={LANG}-{GEO}&gl={GEO}&ceid={GEO}:{LANG}" for t in NEWS_TOPICS]
    for feed in feeds:
        xml = _get(feed)
        if not xml:
            continue
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            continue
        for item in list(root.iter("item"))[:12]:
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            out.append(Signal(
                title=re.sub(r"\s+-\s+[^-]+$", "", title),   # strip " - Publisher"
                source="google-news",
                url=(item.findtext("link") or "").strip(),
                summary=re.sub(r"<[^>]+>", " ",
                               item.findtext("description") or "")[:400],
            ))
    return out


def reddit() -> list[Signal]:
    out: list[Signal] = []
    for sub in SUBREDDITS:
        raw = _get(f"https://www.reddit.com/r/{sub}/hot.json?limit=15")
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            title = (d.get("title") or "").strip()
            if not title or d.get("stickied") or d.get("over_18"):
                continue
            ups = int(d.get("ups") or 0)
            if ups < 500:            # ignore small posts
                continue
            out.append(Signal(
                title=title, source=f"reddit/{sub}",
                url=f"https://reddit.com{d.get('permalink', '')}",
                summary=(d.get("selftext") or "")[:400],
                weight=1.0 + min(ups / 20000.0, 1.5),
            ))
    return out


def wikipedia_mostread() -> list[Signal]:
    """What people are actually looking up — a strong 'real interest' signal."""
    day = dt.date.today() - dt.timedelta(days=1)   # yesterday's feed is complete
    raw = _get(f"https://api.wikimedia.org/feed/v1/wikipedia/{LANG}/featured/"
               f"{day.year}/{day.month:02d}/{day.day:02d}")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out: list[Signal] = []
    for art in (data.get("mostread") or {}).get("articles", [])[:20]:
        title = (art.get("normalizedtitle") or "").strip()
        if not title or title.lower().startswith("main page"):
            continue
        out.append(Signal(
            title=title, source="wikipedia",
            url=(art.get("content_urls", {}).get("desktop", {}) or {}).get("page", ""),
            summary=(art.get("extract") or "")[:400],
            weight=1.2,
        ))
    return out


def youtube_trending() -> list[Signal]:
    """YouTube's own trending chart — costs 1 quota unit, so effectively free."""
    try:
        from src import upload_youtube

        yt = upload_youtube._service()
        resp = yt.videos().list(part="snippet", chart="mostPopular",
                                regionCode=GEO, maxResults=20).execute()
    except Exception as exc:
        print(f"[trends] youtube chart unavailable ({type(exc).__name__})")
        return []
    out: list[Signal] = []
    for item in resp.get("items", []):
        sn = item.get("snippet", {})
        title = (sn.get("title") or "").strip()
        if title:
            out.append(Signal(title=title, source="youtube-trending",
                              url=f"https://youtu.be/{item.get('id')}",
                              summary=(sn.get("description") or "")[:300],
                              weight=1.3))
    return out


# ------------------------------ clustering --------------------------------- #
def _cluster(signals: list[Signal]) -> list[Topic]:
    """Group signals that talk about the same story (shared keywords)."""
    buckets: list[tuple[set[str], list[Signal]]] = []
    for sig in signals:
        w = _words(sig.title)
        if len(w) < 2:
            continue
        for keys, group in buckets:
            shared = len(w & keys)
            if shared >= 2 or (shared == 1 and len(w) <= 3):
                group.append(sig)
                keys |= w
                break
        else:
            buckets.append((set(w), [sig]))

    topics: list[Topic] = []
    for keys, group in buckets:
        # Prefer the longest, most descriptive headline in the cluster.
        best = max(group, key=lambda s: (len(s.title), s.weight))
        summary = next((s.summary for s in group if len(s.summary or "") > 60),
                       best.summary or "")
        srcs = [s.source for s in group]
        # Score: how many DIFFERENT sources, then how strong each was.
        score = len(set(srcs)) * 10 + sum(s.weight for s in group)
        topics.append(Topic(
            headline=best.title.strip()[:200],
            summary=re.sub(r"\s+", " ", summary).strip()[:500],
            sources=srcs,
            urls=[s.url for s in group if s.url][:4],
            keywords=sorted(keys & _words(best.title))[:8],
            score=score,
        ))
    topics.sort(key=lambda t: t.score, reverse=True)
    return topics


def top_topics(limit: int = 10, min_sources: int | None = None) -> list[Topic]:
    """Ranked, multi-source-confirmed trending stories."""
    need = MIN_SOURCES if min_sources is None else min_sources
    signals: list[Signal] = []
    for name, fn in (("google-trends", google_trends),
                     ("google-news", google_news),
                     ("reddit", reddit),
                     ("wikipedia", wikipedia_mostread),
                     ("youtube", youtube_trending)):
        got = fn()
        print(f"[trends] {name}: {len(got)} signals")
        signals += got

    clustered = _cluster(signals)
    confirmed = [t for t in clustered if t.source_count >= need]
    if not confirmed and clustered:
        print(f"[trends] nothing hit {need} sources; falling back to the "
              f"strongest single-source stories")
        confirmed = clustered
    print(f"[trends] {len(clustered)} clusters, {len(confirmed)} confirmed "
          f"(>= {need} sources)")
    return confirmed[:limit]


if __name__ == "__main__":
    for i, t in enumerate(top_topics(8), 1):
        print(f"\n{i}. [{t.score:.0f} | {t.source_count} sources] {t.headline}")
        print(f"   sources: {', '.join(sorted(set(t.sources)))}")
        print(f"   keywords: {', '.join(t.keywords)}")
