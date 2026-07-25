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
    sprites_dir: Path = field(default_factory=lambda: _path("characters/sprites"))
    content_dir: Path = field(default_factory=lambda: _path("content"))
    assets_audio_dir: Path = field(default_factory=lambda: _path("assets/audio"))
    output_dir: Path = field(default_factory=lambda: _path("output"))

    # --- gemini ---
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # --- content format / niche ---
    # "ai_shorts" = faceless AI-tools shorts built from real HD stock footage
    # (fully automatic, CPU-only, runs on GitHub Actions)
    content_format: str = os.getenv("CONTENT_FORMAT", "ai_shorts")

    # --- stock footage (free APIs) ---
    pexels_api_key: str = os.getenv("PEXELS_API_KEY", "")
    pixabay_api_key: str = os.getenv("PIXABAY_API_KEY", "")

    # --- voice ---
    tts_voice: str = os.getenv("TTS_VOICE", "en-US-AriaNeural")  # narrator fallback
    # Distinct voices so it feels like the two characters are talking.
    tts_voice_jon: str = os.getenv("TTS_VOICE_JON", "en-US-GuyNeural")     # playful male
    tts_voice_katie: str = os.getenv("TTS_VOICE_KATIE", "en-US-JennyNeural")  # elegant female
    narration_mode: str = os.getenv("NARRATION_MODE", "narrate")  # narrate|silent

    def voice_for(self, speaker: str) -> str:
        s = (speaker or "").strip().lower()
        if s == "jon":
            return self.tts_voice_jon
        if s == "katie":
            return self.tts_voice_katie
        return self.tts_voice

    # --- video backend ---
    # puppet = talking-puppet animation (real lip-sync, CPU only) <- recommended
    # ltx/kaggle/local = AI image-to-video (needs a GPU), stub = Ken Burns
    video_backend: str = os.getenv("VIDEO_BACKEND", "puppet")
    kaggle_username: str = os.getenv("KAGGLE_USERNAME", "")
    kaggle_key: str = os.getenv("KAGGLE_KEY", "")

    # --- youtube ---
    youtube_client_secret_file: str = os.getenv(
        "YOUTUBE_CLIENT_SECRET_FILE", "secrets/youtube_client_secret.json"
    )
    youtube_token_file: str = os.getenv(
        "YOUTUBE_TOKEN_FILE", "secrets/youtube_token.json"
    )
    # YouTube category: 28 = Science & Technology (correct for an AI channel).
    # 24 = Entertainment, 22 = People & Blogs, 15 = Pets & Animals.
    youtube_category_id: int = int(os.getenv("YOUTUBE_CATEGORY_ID", "28"))

    # --- meta ---
    meta_access_token: str = os.getenv("META_ACCESS_TOKEN", "")
    meta_ig_user_id: str = os.getenv("META_IG_USER_ID", "")
    meta_fb_page_id: str = os.getenv("META_FB_PAGE_ID", "")

    # --- audience / scheduling ---
    target_timezone: str = os.getenv("TARGET_TIMEZONE", "America/New_York")
    # Two main markets for prime-time scheduling.
    usa_timezone: str = os.getenv("USA_TIMEZONE", "America/New_York")
    india_timezone: str = os.getenv("INDIA_TIMEZONE", "Asia/Kolkata")
    channel_name: str = os.getenv("CHANNEL_NAME", "AI Tool Drop")

    # --- content mode ---
    # Shorts-only for now (long-form vlog gets added later once reach grows).
    shorts_only: bool = os.getenv("SHORTS_ONLY", "true").lower() == "true"
    # How many shorts per day (US evening → late-night slots; 6 fits the free
    # YouTube API quota comfortably).
    shorts_per_day: int = int(os.getenv("SHORTS_PER_DAY", "6"))

    # --- render quality ---
    # "hd" = 1080x1920 (YouTube Shorts native, recommended)
    # "4k" = 2160x3840 (heavier render; only worth it if footage is 4K)
    video_quality: str = os.getenv("VIDEO_QUALITY", "hd")
    # x264 quality: lower = better. 18 is visually near-lossless for shorts.
    video_crf: int = int(os.getenv("VIDEO_CRF", "18"))

    # --- housekeeping ---
    # Delete generated video/footage files after a successful upload so the
    # repo/runner storage never fills up.
    cleanup_after_upload: bool = os.getenv("CLEANUP_AFTER_UPLOAD", "true").lower() == "true"

    # --- upload behaviour ---
    # Which platforms to post to (comma list). YouTube-only for now.
    upload_targets: str = os.getenv("UPLOAD_TARGETS", "youtube")
    # YouTube privacy when NOT scheduling to peak: public|unlisted|private.
    youtube_privacy: str = os.getenv("YOUTUBE_PRIVACY", "public")
    # If true, upload as private + auto-publish at the prime-time slot. If false
    # (default, good for testing), publish immediately with `youtube_privacy`.
    schedule_to_peak: bool = os.getenv("SCHEDULE_TO_PEAK", "false").lower() == "true"

    def ensure_dirs(self) -> None:
        for d in (self.refs_dir, self.assets_audio_dir, self.output_dir):
            d.mkdir(parents=True, exist_ok=True)

    def character_bible(self) -> str:
        f = self.characters_dir / "character-bible.md"
        return f.read_text(encoding="utf-8") if f.exists() else ""


settings = Settings()
