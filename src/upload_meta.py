"""Upload Reels to Instagram + Facebook via the Meta Graph API (free).

Requirements (all free):
  - A Facebook Page + an Instagram *Business/Creator* account linked to it.
  - A long-lived Page access token with instagram_content_publish +
    pages_manage_posts permissions.
  - The video must be reachable by a PUBLIC URL (Meta pulls it, it does not
    accept a raw file upload for Reels). Easiest free option: the pipeline
    commits the mp4 to the repo and uses the GitHub `raw` URL, or uploads to any
    free public bucket. Pass that URL as `public_video_url`.

Meta does not offer arbitrary future-scheduling on the basic Graph API for
Reels, so the GitHub Actions cron is what times these to US peak hours.
"""
from __future__ import annotations

import time

import requests

from config import settings

GRAPH = "https://graph.facebook.com/v21.0"


def _poll_container(container_id: str, token: str, tries: int = 20) -> bool:
    """Wait until a media container finishes processing before publishing."""
    for _ in range(tries):
        r = requests.get(
            f"{GRAPH}/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        )
        code = r.json().get("status_code")
        if code == "FINISHED":
            return True
        if code == "ERROR":
            print(f"[meta] container {container_id} errored: {r.json()}")
            return False
        time.sleep(6)
    return False


def upload_instagram_reel(public_video_url: str, caption: str) -> str | None:
    token = settings.meta_access_token
    ig_id = settings.meta_ig_user_id
    if not (token and ig_id):
        print("[meta/ig] missing META_ACCESS_TOKEN or META_IG_USER_ID; skipping.")
        return None
    try:
        create = requests.post(
            f"{GRAPH}/{ig_id}/media",
            data={
                "media_type": "REELS",
                "video_url": public_video_url,
                "caption": caption,
                "access_token": token,
            },
            timeout=60,
        ).json()
        container = create.get("id")
        if not container or not _poll_container(container, token):
            print(f"[meta/ig] container not ready: {create}")
            return None
        pub = requests.post(
            f"{GRAPH}/{ig_id}/media_publish",
            data={"creation_id": container, "access_token": token},
            timeout=60,
        ).json()
        print(f"[meta/ig] published reel -> {pub}")
        return pub.get("id")
    except Exception as exc:
        print(f"[meta/ig] failed ({exc}).")
        return None


def upload_facebook_reel(public_video_url: str, caption: str) -> str | None:
    token = settings.meta_access_token
    page_id = settings.meta_fb_page_id
    if not (token and page_id):
        print("[meta/fb] missing META_ACCESS_TOKEN or META_FB_PAGE_ID; skipping.")
        return None
    try:
        # Facebook Page video post (works for Reels-style vertical video).
        resp = requests.post(
            f"{GRAPH}/{page_id}/videos",
            data={
                "file_url": public_video_url,
                "description": caption,
                "access_token": token,
            },
            timeout=120,
        ).json()
        print(f"[meta/fb] posted video -> {resp}")
        return resp.get("id")
    except Exception as exc:
        print(f"[meta/fb] failed ({exc}).")
        return None


def caption_from(title: str, hashtags: list[str]) -> str:
    tags = " ".join(hashtags)
    return f"{title}\n\n{tags}\n\nNew episode every day! 🐶🐱"
