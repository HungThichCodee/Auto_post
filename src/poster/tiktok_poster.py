import asyncio
import logging
from typing import Optional
from .base_poster import BasePoster, PostResult
from ..utils.browser_manager import BrowserManager

class TiktokPoster(BasePoster):
    def __init__(self, browser_manager: BrowserManager, cookies_json: Optional[str] = None):
        super().__init__(browser_manager, cookies_json)
        self.upload_url = "https://www.tiktok.com/creator-center/upload?mode=photo"
        
    async def post(self, content: str, image_path: str) -> PostResult:
        try:
            await self.setup()
            if not self.page:
                return PostResult(False, "TikTok", error="Browser page not initialized")

            self.logger.info("Navigating to TikTok upload page")
            await self.page.goto(self.upload_url, wait_until="networkidle")
            await self.simulator.random_delay(3.0, 5.0)

            # Check for CAPTCHA or Login
            try:
                login_modal = await self.page.query_selector("div[data-e2e='login-modal']")
                if login_modal:
                    return PostResult(False, "TikTok", error="Session expired, login required")
            except Exception:
                pass

            # Upload image
            file_input_selector = "input[type='file'][accept*='image']"
            try:
                file_input = await self.page.wait_for_selector(file_input_selector, state='attached', timeout=10000)
                if file_input:
                    await file_input.set_input_files(image_path)
                    self.logger.info("Image uploaded to TikTok")
            except Exception as e:
                return PostResult(False, "TikTok", error=f"Could not upload image: {e}")

            await self.simulator.random_delay(3.0, 5.0)

            # Enter caption
            caption_selector = ".public-DraftEditor-content"
            try:
                await self.page.wait_for_selector(caption_selector, timeout=10000)
                await self.simulator.human_click(self.page, caption_selector)
                await self.simulator.human_type(self.page, caption_selector, content)
            except Exception as e:
                self.logger.warning(f"Could not type caption naturally, trying fallback: {e}")
                try:
                    await self.page.fill(caption_selector, content)
                except Exception as e2:
                    return PostResult(False, "TikTok", error=f"Failed to enter caption: {e2}")

            await self.simulator.random_delay(1.5, 3.0)

            # Click Publish
            publish_selectors = [
                "button[data-e2e='post-button']",
                "button:has-text('Post')",
                "button:has-text('Đăng')"
            ]
            
            posted = False
            for selector in publish_selectors:
                try:
                    button = await self.page.wait_for_selector(selector, state='visible', timeout=5000)
                    if button:
                        await self.simulator.human_click(self.page, selector)
                        posted = True
                        break
                except Exception:
                    continue

            if not posted:
                return PostResult(False, "TikTok", error="Could not find or click Post button")

            # Wait for success message
            await self.simulator.random_delay(5.0, 10.0)
            
            return PostResult(True, "TikTok")
            
        except Exception as e:
            self.logger.error(f"TikTok posting failed: {e}")
            return PostResult(False, "TikTok", error=str(e))
        finally:
            await self.teardown()
