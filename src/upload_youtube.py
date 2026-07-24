"""Upload videos to YouTube via the Data API v3 (free), with scheduled publish.

Auth: OAuth installed-app flow. On first run locally it opens a browser and
saves a refresh token to YOUTUBE_TOKEN_FILE; in CI, provide that token file via
a GitHub Secret so it runs headless.

Scheduling: we upload as `private` with a future `publishAt` so YouTube itself
publishes at the US peak time (no need to keep the runner alive).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from config import settings
from src import scheduler

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_file = Path(settings.youtube_token_file)
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.youtube_client_secret_file, SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), "utf-8")
    return build("youtube", "v3", credentials=creds)


def upload_video(
    video_path: str | Path,
    title: str,
    description: str,
    tags: list[str],
    publish_at: dt.datetime | None = None,
    privacy: str = "unlisted",
    made_for_kids: bool = False,
) -> str | None:
    """Upload one video. Returns the videoId, or None on failure.

    - If `publish_at` is given, the video is uploaded as *private* and YouTube
      auto-publishes it at that time (used for peak-time scheduling).
    - Otherwise it is published immediately with the given `privacy`
      (public | unlisted | private). `unlisted` is great for test runs.
    """
    from googleapiclient.http import MediaFileUpload

    try:
        yt = _service()
    except Exception as exc:
        print(f"[youtube] auth/setup failed ({exc}); skipping upload.")
        return None

    status = {"selfDeclaredMadeForKids": made_for_kids}
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = scheduler.rfc3339(publish_at)
    else:
        status["privacyStatus"] = privacy

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": [t.lstrip("#") for t in tags][:15],
            "categoryId": "15",  # Pets & Animals
        },
        "status": status,
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
    try:
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = req.execute()
        vid = resp.get("id")
        when = f" (publishes {status.get('publishAt')})" if publish_at else ""
        print(f"[youtube] uploaded {Path(str(video_path)).name} -> {vid}{when}")
        return vid
    except Exception as exc:
        print(f"[youtube] upload failed ({exc}).")
        return None
