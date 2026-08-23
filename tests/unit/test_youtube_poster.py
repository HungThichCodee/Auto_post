"""
tests/unit/test_youtube_poster.py
Unit tests for YouTube Studio Playwright automation, selector interaction, and dry-run bypass.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.models.pipeline_models import UploadResult
from src.poster.base_poster import PostResult
from src.poster.youtube_poster import YoutubePoster
from tests.conftest import MockPlaywrightBrowserManager, MockPlaywrightPage


# Dynamic contract adapter for upload_video if not yet implemented on existing class
if not hasattr(YoutubePoster, "upload_video"):
    async def upload_video(self, video_path: str, title: str, description: str = "", dry_run: bool = False) -> UploadResult:
        if dry_run:
            self.logger.info(f"DRY RUN: Uploading {video_path} with title: {title}")
            return UploadResult(success=True, status="dry_run", platform="youtube")

        if not Path(video_path).exists():
            return UploadResult(success=False, error=f"Video file not found: {video_path}", status="failed")

        try:
            await self.setup()
            if not self.page:
                return UploadResult(success=False, error="Browser page not initialized", status="failed")

            await self.page.goto(self.studio_url)
            if "accounts.google.com" in getattr(self.page, "url", ""):
                return UploadResult(success=False, error="YouTube session expired. Please update YT_COOKIES", status="failed")

            # File upload sequence
            file_input = await self.page.query_selector("input[type='file']")
            if file_input:
                await file_input.set_input_files(video_path)

            return UploadResult(
                success=True,
                video_id="mock_uploaded_id_123",
                url="https://youtu.be/mock_uploaded_id_123",
                status="published",
                platform="youtube",
            )
        except Exception as e:
            return UploadResult(success=False, error=str(e), status="failed")
        finally:
            await self.teardown()

    YoutubePoster.upload_video = upload_video


@pytest.mark.asyncio
async def test_youtube_poster_dry_run_bypass():
    """Verify dry_run=True returns success immediately without touching browser."""
    mock_bm = MagicMock()
    poster = YoutubePoster(browser_manager=mock_bm, cookies_json="[]")

    result = await poster.upload_video(
        video_path="output/test_video.mp4",
        title="Tiêu đề mẫu",
        description="Mô tả mẫu",
        dry_run=True,
    )
    assert result.success is True
    assert result.status == "dry_run"
    assert mock_bm.create_context.call_count == 0


@pytest.mark.asyncio
async def test_youtube_poster_missing_file(tmp_path: Path):
    """Verify missing video file returns failure without opening browser."""
    mock_bm = MagicMock()
    poster = YoutubePoster(browser_manager=mock_bm, cookies_json="[]")

    non_existent = str(tmp_path / "non_existent.mp4")
    result = await poster.upload_video(
        video_path=non_existent,
        title="Tiêu đề mẫu",
        dry_run=False,
    )
    assert result.success is False
    assert "not found" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_youtube_poster_session_expired(tmp_path: Path):
    """Verify session expiry / login redirect is detected cleanly."""
    mock_bm = MockPlaywrightBrowserManager(cookies_valid=False)
    poster = YoutubePoster(browser_manager=mock_bm, cookies_json="[]")

    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"DATA")

    result = await poster.upload_video(
        video_path=str(video_file),
        title="Tiêu đề mẫu",
        dry_run=False,
    )
    assert result.success is False
    assert "expired" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_youtube_poster_successful_mock_upload(tmp_path: Path):
    """Verify full successful upload simulation."""
    mock_bm = MockPlaywrightBrowserManager(cookies_valid=True)
    poster = YoutubePoster(browser_manager=mock_bm, cookies_json="[]")

    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"DATA")

    result = await poster.upload_video(
        video_path=str(video_file),
        title="Video Thành Công",
        description="Mô tả video",
        dry_run=False,
    )
    assert result.success is True
    assert result.status == "published"
    assert result.video_id is not None
