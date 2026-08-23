"""
src/poster/youtube_poster.py
YouTube Studio video uploader via Playwright browser automation.
"""

import asyncio
import logging
import os
from typing import Optional

from .base_poster import BasePoster, PostResult
from ..utils.browser_manager import BrowserManager

logger = logging.getLogger(__name__)


class YoutubePoster(BasePoster):
    """Uploads videos to YouTube via Playwright browser automation of YouTube Studio."""

    STUDIO_URL = "https://studio.youtube.com/"

    def __init__(self, browser_manager: BrowserManager, cookies_json: Optional[str] = None):
        super().__init__(browser_manager, cookies_json)

    async def post(self, content: str, image_path: str) -> PostResult:
        """Legacy interface — redirects to upload_video for backward compatibility."""
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
    ) -> PostResult:
        """
        Upload a video to YouTube via YouTube Studio browser automation.

        Args:
            video_path: Path to the .mp4 video file.
            title: Video title (Vietnamese).
            description: Video description (Vietnamese).
            dry_run: If True, log steps but skip actual interactions.
        """
        try:
            await self.setup()
            if not self.page:
                return PostResult(False, "YouTube", error="Browser page not initialized")

            if dry_run:
                self.logger.info("[DRY RUN] Would upload video to YouTube Studio")
                self.logger.info(f"[DRY RUN] Video: {video_path}")
                self.logger.info(f"[DRY RUN] Title: {title}")
                self.logger.info(f"[DRY RUN] Description: {description[:100]}...")
                return PostResult(True, "YouTube", post_url="dry_run://youtube")

            # Step 1: Navigate to YouTube Studio
            self.logger.info("Navigating to YouTube Studio...")
            await self.page.goto(self.STUDIO_URL, wait_until="networkidle", timeout=60000)
            await self.simulator.random_delay(3.0, 5.0)

            # Check if logged in
            current_url = self.page.url
            if "accounts.google.com" in current_url:
                return PostResult(False, "YouTube", error="Not logged in — cookies may be expired")

            # Step 2: Click Upload / Create button
            self.logger.info("Looking for Create/Upload button...")
            create_selectors = [
                "#upload-icon",
                "#create-icon",
                "ytcp-button#create-icon",
                "button[aria-label='Upload videos']",
                "button[aria-label='Tải video lên']",
                "button[aria-label='Create']",
                "button[aria-label='Tạo']",
            ]
            clicked = await self._try_click_selectors(create_selectors)
            if not clicked:
                # Try finding the upload button by text
                try:
                    await self.page.locator("text=Upload videos").or_(
                        self.page.locator("text=Tải video lên")
                    ).first.click(timeout=5000)
                    clicked = True
                except Exception:
                    pass

            if not clicked:
                return PostResult(False, "YouTube", error="Could not find Create/Upload button")

            await self.simulator.random_delay(1.5, 3.0)

            # Step 3: Click "Upload videos" option in dropdown
            self.logger.info("Selecting 'Upload videos' option...")
            upload_option_selectors = [
                "#text-item-0",  # Usually first item in create menu
                "tp-yt-paper-item#text-item-0",
                "a[href*='upload']",
                "tp-yt-paper-item:has-text('Upload videos')",
                "tp-yt-paper-item:has-text('Tải video lên')",
                "tp-yt-paper-item:has-text('Upload video')",
            ]
            await self._try_click_selectors(upload_option_selectors)
            await self.simulator.random_delay(2.0, 4.0)

            # Step 4: Upload video file via file input
            self.logger.info(f"Uploading video file: {video_path}")
            file_input = await self.page.query_selector("input[type='file']")
            if not file_input:
                # Wait for it to appear
                try:
                    file_input = await self.page.wait_for_selector(
                        "input[type='file']", state="attached", timeout=10000
                    )
                except Exception:
                    return PostResult(False, "YouTube", error="Could not find file input for video upload")

            await file_input.set_input_files(video_path)
            self.logger.info("Video file selected, waiting for upload to begin...")
            await self.simulator.random_delay(5.0, 8.0)

            # Step 5: Fill in Title
            self.logger.info(f"Setting title: {title[:50]}...")
            title_selectors = [
                "#textbox[aria-label*='title' i]",
                "#textbox[aria-label*='tiêu đề' i]",
                "div#textbox.ytcp-social-suggestions-textbox",
                "#title-textarea #textbox",
                "ytcp-social-suggestions-textbox #textbox",
            ]
            title_filled = False
            for selector in title_selectors:
                try:
                    title_el = await self.page.wait_for_selector(selector, timeout=5000)
                    if title_el:
                        # Clear existing title
                        await title_el.click()
                        await self.page.keyboard.press("Control+A")
                        await self.page.keyboard.press("Backspace")
                        await self.simulator.random_delay(0.5, 1.0)
                        # Type new title
                        await title_el.fill(title[:100])
                        title_filled = True
                        self.logger.info("Title set successfully")
                        break
                except Exception:
                    continue

            if not title_filled:
                self.logger.warning("Could not find title field, trying keyboard shortcut...")
                try:
                    await self.page.keyboard.press("Tab")
                    await self.page.keyboard.type(title[:100], delay=30)
                except Exception as e:
                    self.logger.warning(f"Title fill fallback failed: {e}")

            await self.simulator.random_delay(1.0, 2.0)

            # Step 6: Fill in Description
            self.logger.info("Setting description...")
            desc_selectors = [
                "#description-textarea #textbox",
                "#textbox[aria-label*='description' i]",
                "#textbox[aria-label*='mô tả' i]",
                "div#description-wrapper #textbox",
            ]
            for selector in desc_selectors:
                try:
                    desc_el = await self.page.wait_for_selector(selector, timeout=3000)
                    if desc_el:
                        await desc_el.click()
                        await desc_el.fill(description[:5000])
                        self.logger.info("Description set successfully")
                        break
                except Exception:
                    continue

            await self.simulator.random_delay(1.0, 2.0)

            # Step 7: Select "Not made for kids"
            self.logger.info("Selecting 'Not made for kids'...")
            not_for_kids_selectors = [
                "#audience tp-yt-paper-radio-button[name='NOT_MADE_FOR_KIDS']",
                "tp-yt-paper-radio-button[name='NOT_MADE_FOR_KIDS']",
                "#radioLabel:has-text('not made for kids')",
                "#radioLabel:has-text('không dành cho trẻ em')",
                "tp-yt-paper-radio-button:nth-child(2)",
            ]
            await self._try_click_selectors(not_for_kids_selectors)
            await self.simulator.random_delay(1.0, 2.0)

            # Step 8: Click Next through remaining steps (3 times)
            self.logger.info("Clicking through Next steps...")
            next_selectors = [
                "#next-button",
                "ytcp-button#next-button",
                "#step-badge-3",
            ]
            for step in range(3):
                await self.simulator.random_delay(1.5, 3.0)
                for selector in next_selectors:
                    try:
                        btn = await self.page.wait_for_selector(selector, timeout=5000)
                        if btn:
                            await btn.click()
                            self.logger.info(f"Clicked Next (step {step + 1}/3)")
                            break
                    except Exception:
                        continue
                await self.simulator.random_delay(1.0, 2.0)

            # Step 9: Select Public visibility
            self.logger.info("Setting visibility to Public...")
            public_selectors = [
                "tp-yt-paper-radio-button[name='PUBLIC']",
                "#privacy-radios tp-yt-paper-radio-button:first-child",
                "#radioLabel:has-text('Public')",
                "#radioLabel:has-text('Công khai')",
            ]
            await self._try_click_selectors(public_selectors)
            await self.simulator.random_delay(1.5, 3.0)

            # Step 10: Click Publish/Done
            self.logger.info("Publishing video...")
            publish_selectors = [
                "#done-button",
                "ytcp-button#done-button",
                "ytcp-button:has-text('Publish')",
                "ytcp-button:has-text('Xuất bản')",
                "ytcp-button:has-text('Done')",
                "ytcp-button:has-text('Xong')",
            ]
            published = await self._try_click_selectors(publish_selectors)
            if not published:
                return PostResult(False, "YouTube", error="Could not find Publish/Done button")

            # Step 11: Wait for confirmation
            self.logger.info("Waiting for upload confirmation...")
            await self.simulator.random_delay(8.0, 15.0)

            # Try to get the video URL from the confirmation dialog
            video_url = ""
            try:
                link_el = await self.page.query_selector("a.ytcp-video-info[href*='youtu']")
                if link_el:
                    video_url = await link_el.get_attribute("href") or ""
            except Exception:
                pass

            # Close the dialog if present
            try:
                close_btn = await self.page.query_selector("ytcp-button#close-button")
                if close_btn:
                    await close_btn.click()
            except Exception:
                pass

            self.logger.info(f"Video published successfully! URL: {video_url}")
            return PostResult(True, "YouTube", post_url=video_url)

        except Exception as e:
            self.logger.error(f"YouTube upload failed: {e}")
            return PostResult(False, "YouTube", error=str(e))
        finally:
            await self.teardown()

    async def _try_click_selectors(self, selectors: list, timeout: int = 5000) -> bool:
        """Try clicking the first matching selector from a list."""
        for selector in selectors:
            try:
                el = await self.page.wait_for_selector(selector, state="visible", timeout=timeout)
                if el:
                    await el.click()
                    return True
            except Exception:
                continue
        return False
