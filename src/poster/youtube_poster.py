"""
src/poster/youtube_poster.py
YouTube video uploader using the official YouTube Data API v3.
"""

import os
import json
import logging
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

from .base_poster import BasePoster, PostResult
from ..utils.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

class YoutubePoster(BasePoster):
    """Uploads videos to YouTube via the official YouTube Data API v3."""

    def __init__(self, browser_manager: BrowserManager, cookies_json: Optional[str] = None):
        super().__init__(browser_manager, cookies_json)
        self.credentials = None
        self.youtube = None

    async def setup(self):
        """Initialize the YouTube API client."""
        # For the API approach, we don't need Playwright setup,
        # but we must call super().setup() to satisfy BasePoster if needed.
        pass

    async def teardown(self):
        """Clean up resources."""
        pass

    def _get_authenticated_service(self):
        """Authenticate and return the YouTube API service."""
        client_id = os.getenv("YT_CLIENT_ID")
        client_secret = os.getenv("YT_CLIENT_SECRET")
        refresh_token = os.getenv("YT_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            raise ValueError("Missing YouTube API credentials. Set YT_CLIENT_ID, YT_CLIENT_SECRET, and YT_REFRESH_TOKEN in environment variables (or GitHub Secrets).")

        # Reconstruct OAuth credentials from the refresh token
        client_config = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        self.credentials = Credentials.from_authorized_user_info(client_config)
        
        # Refresh the token if it's expired
        if self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())

        return build("youtube", "v3", credentials=self.credentials, cache_discovery=False)

    async def post(self, content: str, image_path: str) -> PostResult:
        """Legacy interface — redirects to upload_video."""
        return await self.upload_video(
            video_path=image_path,
            title=content[:100],
            description=content,
        )

    async def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        dry_run: bool = False,
        tags: list = None,
    ) -> PostResult:
        """
        Upload a video to YouTube via the official API.
        """
        if dry_run:
            self.logger.info("[DRY RUN] Would upload video via API")
            self.logger.info(f"[DRY RUN] Video: {video_path}")
            self.logger.info(f"[DRY RUN] Title: {title}")
            return PostResult(True, "YouTube", post_url="dry_run://youtube")

        try:
            self.youtube = self._get_authenticated_service()
            self.logger.info("Successfully authenticated with YouTube API.")

            snippet = {
                "title": title[:100],
                "description": description[:5000],
                "categoryId": "24",  # 24 is Entertainment
            }
            if tags:
                # YouTube allows max 500 chars total for tags
                valid_tags = []
                total_len = 0
                for tag in tags:
                    tag = str(tag).strip()
                    if tag and total_len + len(tag) + 1 <= 500:
                        valid_tags.append(tag)
                        total_len += len(tag) + 1
                snippet["tags"] = valid_tags

            body = {
                "snippet": snippet,
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                }
            }

            self.logger.info(f"Preparing to upload {video_path}...")
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            self.logger.info("Uploading video to YouTube...")
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    self.logger.info(f"Uploaded {int(status.progress() * 100)}%")

            video_id = response.get("id")
            video_url = f"https://youtu.be/{video_id}"
            
            self.logger.info(f"Video published successfully! URL: {video_url}")
            return PostResult(True, "YouTube", post_url=video_url)

        except Exception as e:
            self.logger.error(f"YouTube API upload failed: {e}")
            return PostResult(False, "YouTube", error=str(e))
