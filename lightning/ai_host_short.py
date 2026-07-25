"""AI + crypto talking-host short, rendered on a Lightning GPU -> straight to YouTube.

One recurring on-screen host (your generated character) explains an AI tool or a
crypto concept, vlog style, with real lip-sync driven by the narration audio.

    git clone https://github.com/ganesha98285-lgtm/jab-ketty-met-john
    cd jab-ketty-met-john
    sudo apt-get install -y ffmpeg
    export YOUTUBE_TOKEN_JSON='<same JSON as your GitHub secret>'
    export GEMINI_API_KEY='<optional: fresh daily script instead of built-ins>'
    python lightning/ai_host_short.py

Flags:
    --scenes 5           lines in the video (fewer = cheaper/faster)
    --topic ai|crypto    force the subject (default: alternates daily)
    --privacy unlisted   publish quietly
    --size 704*544       smaller frames if a 24 GB GPU runs out of memory
    --steps 30           diffusion steps
    --dry-run            build the mp4, skip the upload
    --download-only      fetch model weights only — run this on the FREE CPU
                         machine so the ~40-60 GB download costs 0 credits

You must add ONE reference image of your host:
    characters/refs/host_face.png     <- close-up, head & shoulders, facing camera

Why a human-looking host matters: audio-driven avatar models are trained on human
faces, so a human host lip-syncs far better than a cartoon animal muzzle.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("BRAND_HANDLE", "@aitooldrop")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wan_common as wc  # noqa: E402

HOST_VOICE = os.getenv("HOST_VOICE", "en-US-AndrewNeural")  # warm, natural male
REF_SPEC = {"host": ("host_face.png", "host.png", "ai_host.png")}

STYLE = (
    "professional yet friendly content creator, clean modern setup, soft studio "
    "lighting, subtle bokeh background, cinematic, highly detailed, 4k"
)

# --------------------------------------------------------------------------- #
# built-in topics (used when GEMINI_API_KEY is absent, and as the fallback)
# --------------------------------------------------------------------------- #
AI_TOPICS = [
    {
        "slug": "ai-agents",
        "title": "AI agents explained in 30 seconds",
        "lines": [
            "Everyone says AI agents, but almost nobody explains what they are.",
            "A normal chatbot answers. An agent actually does the task for you.",
            "You give it a goal, it picks the tools, runs the steps, and checks itself.",
            "That is why agents can book, research and write end to end.",
            "Follow for one AI thing you can actually use, every single day.",
        ],
        "tags": ["ai agents", "ai tools", "artificial intelligence", "automation"],
    },
    {
        "slug": "prompt-trick",
        "title": "The prompt trick that fixes lazy AI answers",
        "lines": [
            "If your AI answers feel generic, it is not the model. It is the prompt.",
            "Add one line: act as an expert and ask me questions before answering.",
            "Now it interviews you first, so the output matches what you meant.",
            "Same model, ten times better answer, zero extra cost.",
            "Follow for daily AI tricks that actually save you time.",
        ],
        "tags": ["chatgpt tips", "prompt engineering", "ai tips", "productivity"],
    },
    {
        "slug": "free-ai-video",
        "title": "Free AI tools that replaced my paid ones",
        "lines": [
            "I cancelled three subscriptions this month, and here is why.",
            "Free open models now handle video, voice and image generation.",
            "You run them on free cloud GPUs instead of paying per export.",
            "Same output, no watermark, no monthly bill.",
            "Follow so you never pay for a tool you could run free.",
        ],
        "tags": ["free ai tools", "ai video", "ai apps", "best ai tools"],
    },
    {
        "slug": "ai-workflow",
        "title": "Automate your boring work with AI in one evening",
        "lines": [
            "Most people use AI to chat. The money is in automation.",
            "Pick one task you repeat weekly. Write down every step.",
            "Give those steps to an AI tool and let it run on a schedule.",
            "That one setup can save you hours every month, forever.",
            "Follow for one automation idea a day.",
        ],
        "tags": ["ai automation", "ai workflow", "productivity", "ai tools"],
    },
]

CRYPTO_TOPICS = [
    {
        "slug": "eth-gas",
        "title": "Ethereum gas fees explained simply",
        "lines": [
            "Ever paid more in fees than the thing you were buying? Here is why.",
            "Ethereum charges gas, which is payment for the network's computing work.",
            "A busy network means people bid higher, so gas goes up.",
            "That is why the same transfer costs more at peak hours than at night.",
            "Follow for crypto and AI explained without the jargon.",
        ],
        "tags": ["ethereum", "gas fees", "crypto explained", "web3"],
    },
    {
        "slug": "btc-halving",
        "title": "Bitcoin halving in 30 seconds",
        "lines": [
            "Bitcoin cuts its own supply on a schedule, and most people miss why.",
            "Roughly every four years, the reward for mining a block is halved.",
            "Fewer new coins enter circulation, so the supply grows slower.",
            "That built-in scarcity is the whole design, written into the code.",
            "Follow for crypto basics explained clearly, every day.",
        ],
        "tags": ["bitcoin", "bitcoin halving", "crypto explained", "btc"],
    },
    {
        "slug": "eth-staking",
        "title": "What Ethereum staking actually means",
        "lines": [
            "Staking sounds complicated, but the idea is simple.",
            "You lock up Ethereum to help validate transactions on the network.",
            "In return the network pays you a share of the rewards.",
            "Your coins are working instead of just sitting in a wallet.",
            "Follow for one clear crypto idea a day.",
        ],
        "tags": ["ethereum staking", "ethereum", "crypto explained", "defi"],
    },
    {
        "slug": "wallet-safety",
        "title": "The wallet mistake that drains beginners",
        "lines": [
            "Most people lose crypto to one mistake, and it is not hacking.",
            "They store their seed phrase in a screenshot or a notes app.",
            "Anything on the internet can be read. A seed phrase must stay offline.",
            "Write it on paper, keep it somewhere only you know.",
            "Follow so you learn this before it costs you.",
        ],
        "tags": ["crypto wallet", "crypto safety", "seed phrase", "crypto tips"],
    },
]

BASE_TAGS = ["#shorts", "#ai", "#aitools", "#crypto"]
ROTATE_TAGS = ["#chatgpt", "#artificialintelligence", "#bitcoin", "#ethereum",
               "#tech", "#automation", "#web3", "#aitips", "#productivity"]

DISCLAIMER = ("Educational content only — not financial advice. "
              "Always do your own research.")


# --------------------------------------------------------------------------- #
# script
# --------------------------------------------------------------------------- #
def pick_topic(force: str | None) -> dict:
    """Alternate AI / crypto by day so the channel stays varied but consistent."""
    day = dt.date.today().toordinal()
    kind = force or ("crypto" if day % 2 else "ai")
    pool = CRYPTO_TOPICS if kind == "crypto" else AI_TOPICS
    topic = dict(pool[(day // 2) % len(pool)])
    topic["kind"] = kind
    return topic


def from_gemini(kind: str) -> dict | None:
    """Fresh daily script via the free Gemini tier. Returns None on any problem."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=key)
        subject = ("a crypto concept (Bitcoin, Ethereum, wallets, DeFi)"
                   if kind == "crypto" else
                   "a specific AI tool, prompt trick or automation idea")
        prompt = (
            f"Write a 30-second YouTube Shorts script where ONE host explains "
            f"{subject} to a US audience. Return ONLY JSON:\n"
            '{"title": "...", "lines": ["...", "...", "...", "...", "..."], '
            '"tags": ["...", "...", "...", "..."]}\n'
            "Rules: line 1 is a scroll-stopping hook under 12 words. Lines 2-4 "
            "teach one concrete idea in plain spoken English, max 14 words each. "
            "Line 5 is a follow/subscribe call to action. No emojis, no markdown, "
            "no financial advice — educational only. Title under 60 characters."
        )
        raw = genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt).text
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        lines = [str(x).strip() for x in data["lines"] if str(x).strip()]
        if len(lines) < 4:
            return None
        print("[script] fresh script from Gemini")
        return {
            "slug": "gemini",
            "title": str(data["title"]).strip()[:80],
            "lines": lines,
            "tags": [str(t) for t in data.get("tags", [])][:6],
            "kind": kind,
        }
    except Exception as exc:  # quota, parsing, network — fall back quietly
        print(f"[script] Gemini unavailable ({type(exc).__name__}), "
              f"using the built-in topic")
        return None


def build_scenes(topic: dict, n: int) -> list[dict]:
    lines = topic["lines"][:max(2, n)]
    scenes: list[dict] = []
    for i, line in enumerate(lines, start=1):
        scenes.append({
            "id": i,
            "speaker": "host",
            "narration": line,
            "hook": i == 1,
            "cta": i == len(lines),
        })
    return scenes


def prompt_for(scene: dict) -> str:
    # Close framing is what makes audio-driven lip-sync land.
    return (
        "close-up portrait of a friendly presenter talking directly to the "
        "camera, head and shoulders filling the frame, mouth clearly visible, "
        "natural mouth movement, engaging facial expression, slight head "
        f"movement, {STYLE}"
    )


def metadata(topic: dict, scenes: list[dict]) -> dict:
    hook = scenes[0]["narration"]
    tags = BASE_TAGS + [f"#{t.replace(' ', '')}" for t in topic.get("tags", [])][:3]
    tags += [t for t in ROTATE_TAGS
             if t not in tags][:max(0, 10 - len(tags))]
    body = "\n".join(f"- {s['narration']}" for s in scenes[1:-1])
    desc = (
        f"{hook}\n\n{body}\n\n"
        f"New AI + crypto short every day. Subscribe so you don't miss it.\n\n"
        f"{DISCLAIMER}\n\n" + " ".join(tags)
    )
    return {
        "title": f"{topic['title']} #shorts",
        "description": desc,
        "tags": tags,
        "hook": hook,
    }


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", type=int, default=5)
    ap.add_argument("--topic", choices=["ai", "crypto"], default=None)
    ap.add_argument("--privacy", default=os.getenv("YOUTUBE_PRIVACY", "public"),
                    choices=["public", "unlisted", "private"])
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--size", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--download-only", action="store_true")
    args = ap.parse_args()

    if args.download_only:
        print("=== DOWNLOAD ONLY — run this on the FREE CPU machine ===")
        wc.ensure_model()
        print("\n✅ weights cached. Now switch the Studio to RTX 6000 and run:\n"
              "   python lightning/ai_host_short.py")
        return

    refs = wc.preflight(REF_SPEC, args.dry_run)

    kind = args.topic or pick_topic(None)["kind"]
    topic = from_gemini(kind) or pick_topic(args.topic)
    scenes = build_scenes(topic, args.scenes)
    meta = metadata(topic, scenes)

    print(f"\n=== TODAY: [{topic['kind']}] {topic['title']} — "
          f"{len(scenes)} lines ===")
    for s in scenes:
        mark = " [HOOK]" if s["hook"] else (" [CTA]" if s["cta"] else "")
        print(f"  {s['id']}. {s['narration']}{mark}")

    work = wc.ROOT / "output" / dt.date.today().isoformat() / f"host-{topic['slug']}"
    work.mkdir(parents=True, exist_ok=True)

    wc.build_and_publish(scenes, prompt_for, refs,
                         lambda _s: HOST_VOICE, work, meta, args)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
