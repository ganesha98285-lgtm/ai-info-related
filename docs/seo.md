# SEO + algorithm setup — Viral News channel

Everything on the video side is automated. This file covers the **channel-level**
settings you must set once by hand, plus the reasoning behind the automated
choices so nothing looks arbitrary.

## 1. Channel settings (do this once, in YouTube Studio)

| Field | What to set | Why |
|---|---|---|
| Channel name | `Viral Wire` (or `World Viral` / `Daily Viral News`) | Keyword "viral/news" in the name helps channel search |
| Handle | `@viralwire` (must match the name) | Handle is indexed; mismatched handles waste the signal |
| Description | *(below)* | First 100 chars appear in search results |
| Keywords (Settings → Channel → Basic info) | `viral news, trending news, breaking news, crypto news, stock market news, tech news, news shorts, world news today` | Channel-level keywords feed topic classification |
| Category (per video) | **25 — News & Politics** | Set automatically via `YOUTUBE_CATEGORY_ID=25` |
| Country | United States | Drives which trending/ad market you are matched to |
| Upload defaults | Title suffix `#shorts`, visibility Public | Already handled by the pipeline |

Channel description to paste:

```
Trending news in 30 seconds. Crypto, markets, tech and world stories that are
actually going viral right now - explained fast, no fluff.

New shorts every day. Subscribe so you hear it here first.
```

## 2. Why the automated SEO is built the way it is

**Title** — the story's own headline comes first (keywords a person would
actually search), trimmed to ~66 characters so nothing is cut off on mobile, then
`#shorts`. No invented clickbait: a title that does not match the content tanks
watch time, which is the metric that matters.

**Hashtags** — the first three are shown *above* the title, so they are the broad
ones (`#shorts #news` + the category tag). Live trending terms from Google Trends
are appended, then reach tags. Junk tags (numbers like `#000`, filler words) are
filtered out — they dilute classification.

**Description** — the first line repeats the headline plus "why it matters"
(this is what search indexes), then context from the source, then **source
attribution**, then the CTA, then hashtags. Attribution matters on a news
channel: it is the difference between commentary and unverified claims.

**Search tags** — the story's entities plus category terms, with weak words
stripped. Max 15.

**Category 25 (News & Politics)** — matching the real category is how YouTube
finds the right audience. A news video filed under Science & Technology gets
shown to the wrong people.

**Publishing immediately, not at a fixed peak slot** — for news, freshness beats
timing. A story posted 6 hours late competes with a hundred channels that already
covered it. The cron therefore runs 3x/day (12pm, 4pm, 8pm ET) and publishes on
the spot. Evergreen content is the opposite, which is why `ai_shorts` mode still
uses peak scheduling.

**3 posts per day, every day** — consistency is itself an algorithm signal, and
2 shorts x 3 runs = 6/day is exactly the free YouTube API quota.

**Thumbnail** — a real frame from the video with a large hook, chosen from 48
layout/palette combinations so no two thumbnails on the channel look alike.

## 3. Retention (the metric that decides everything)

- Hook in the first 2 seconds, max 12 words.
- Yellow on-screen hook burned over the first 3 seconds.
- Scene changes every ~2-4 seconds (tied to each narration line).
- Follow/subscribe CTA in the last 3 seconds only — never earlier.
- 30-45 seconds total: long enough to matter, short enough to be re-watched.

## 4. Safety = revenue (read this before turning politics on)

`src/safety.py` skips tragedy, violence, medical claims, election claims and
adult/gambling topics. This is not censorship, it is money and survival:

- YouTube's advertiser-friendly guidelines **limit ads** on tragedy, conflict and
  "controversial issues" — those videos earn a fraction even when they perform.
- An unsupervised script narrating a death toll or a health claim is exactly how
  channels collect strikes.

Politics is off by default (`ALLOW_POLITICS=false`). Turning it on means Modi /
Trump / protest stories become eligible — more views, noticeably lower CPM, and
more policy risk. Your call, one variable.

## 5. Tuning variables (GitHub → Settings → Variables)

| Variable | Default | Effect |
|---|---|---|
| `CONTENT_FORMAT` | `viral_news` | `ai_shorts` switches back to evergreen AI tips |
| `SHORTS_PER_DAY` | `2` | Per **run** (3 runs/day) |
| `TRENDS_GEO` | `US` | Which country's trends to follow |
| `MIN_TREND_SOURCES` | `2` | Raise to 3 for stricter "really viral" filtering |
| `ALLOW_POLITICS` | `false` | Include political stories |
| `STORY_WINDOW_DAYS` | `7` | How long before a subject can be revisited |
| `YOUTUBE_CATEGORY_ID` | `25` | 25 News, 28 Science & Tech |

## 6. Instagram + Facebook

Deliberately **not enabled yet**. `src/upload_meta.py` is written but stays off
until you create the Page + Instagram professional account and the Meta token.
The blocker is that Meta pulls Reels from a **public URL** rather than accepting a
file upload, so that step needs a public host (a GitHub Release asset works) —
that is the next phase, not this one.
