"""Central configuration for the Jon & Katie vlog studio.

Reads everything from environment variables (loaded from .env locally, or from
GitHub Secrets in CI). Import `settings` anywhere you need config.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional in CI where secrets are already in env
    pass

ROOT = Path(__file__).resolve().parent


def _path(rel: str) -> Path:
    p = (ROOT / rel).resolve()
    return p


@dataclass(frozen=True)
class Settings:
    # --- paths ---
    root: Path = ROOT
    characters_dir: Path = field(default_factory=lambda: _path("characters"))
    refs_dir: Path = field(default_factory=lambda: _path("characters/refs"))
    content_dir: Path = field(default_factory=lambda: _path("content"))
    assets_audio_dir: Path = field(default_factory=lambda: _path("assets/audio"))
    output_dir: Path = field(default_factory=lambda: _path("output"))

    # --- gemini ---
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # --- voice ---
    tts_voice: str = os.getenv("TTS_VOICE", "en-US-AriaNeural")
    narration_mode: str = os.getenv("NARRATION_MODE", "narrate")  # narrate|silent

    # --- video backend ---
    video_backend: str = os.getenv("VIDEO_BACKEND", "stub")  # kaggle|local|stub
    kaggle_username: str = os.getenv("KAGGLE_USERNAME", "")
    kaggle_key: str = os.getenv("KAGGLE_KEY", "")

    # --- youtube ---
    youtube_client_secret_file: str = os.getenv(
        "YOUTUBE_CLIENT_SECRET_FILE", "secrets/youtube_client_secret.json"
    )
    youtube_token_file: str = os.getenv(
        "YOUTUBE_TOKEN_FILE", "secrets/youtube_token.json"
    )

    # --- meta ---
    meta_access_token: str = os.getenv("META_ACCESS_TOKEN", "")
    meta_ig_user_id: str = os.getenv("META_IG_USER_ID", "")
    meta_fb_page_id: str = os.getenv("META_FB_PAGE_ID", "")

    # --- upload targets / behaviour ---
    # Comma-separated list of platforms to post to. For the first YouTube-only
    # test keep this = "youtube". Add "meta" later to also post IG/FB Reels.
    upload_targets: str = os.getenv("UPLOAD_TARGETS", "youtube")
    # YouTube privacy for a run: "unlisted" (safe test — only link holders see it),
    # "private", or "public".
    youtube_privacy: str = os.getenv("YOUTUBE_PRIVACY", "unlisted")
    # If "true", uploads are scheduled to US peak times (private + publishAt).
    # If "false" (default for testing), they publish immediately with the privacy
    # set above so you can review them right after the run.
    schedule_to_peak: bool = os.getenv("SCHEDULE_TO_PEAK", "false").lower() == "true"

    # --- audience / scheduling ---
    target_timezone: str = os.getenv("TARGET_TIMEZONE", "America/New_York")
    channel_name: str = os.getenv("CHANNEL_NAME", "Jon & Katie")

    def upload_target_list(self) -> list[str]:
        return [t.strip().lower() for t in self.upload_targets.split(",") if t.strip()]

    def ensure_dirs(self) -> None:
        for d in (self.refs_dir, self.assets_audio_dir, self.output_dir):
            d.mkdir(parents=True, exist_ok=True)

    def character_bible(self) -> str:
        f = self.characters_dir / "character-bible.md"
        return f.read_text(encoding="utf-8") if f.exists() else ""


settings = Settings()
