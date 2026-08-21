import asyncio
import logging
from typing import Optional
from .base_poster import BasePoster, PostResult
from ..utils.browser_manager import BrowserManager

class YoutubePoster(BasePoster):
    def __init__(self, browser_manager: BrowserManager, cookies_json: Optional[str] = None):
        super().__init__(browser_manager, cookies_json)
        self.studio_url = "https://studio.youtube.com/"
        
    async def post(self, content: str, image_path: str) -> PostResult:
        try:
            await self.setup()
            if not self.page:
                return PostResult(False, "YouTube", error="Browser page not initialized")

            self.logger.info("Navigating to YouTube Studio")
            await self.page.goto(self.studio_url, wait_until="networkidle")
            await self.simulator.random_delay(3.0, 5.0)

            # Click Create
            create_btn_selector = "ytcp-button#create-icon"
            try:
                await self.page.wait_for_selector(create_btn_selector, timeout=10000)
                await self.simulator.human_click(self.page, create_btn_selector)
            except Exception as e:
                return PostResult(False, "YouTube", error=f"Could not click create button: {e}")

            await self.simulator.random_delay(1.0, 2.0)

            # Click Create Post (Community)
            create_post_selector = "tp-yt-paper-item#text-item-2" # Usually the 3rd item
            try:
                await self.page.wait_for_selector(create_post_selector, timeout=5000)
                await self.simulator.human_click(self.page, create_post_selector)
            except Exception as e:
                # Try finding by text
                try:
                    alt_selector = "tp-yt-paper-item:has-text('Create post')"
                    await self.simulator.human_click(self.page, alt_selector)
                except Exception as e2:
                    return PostResult(False, "YouTube", error=f"Could not click 'Create post' option: {e2}")

            # Wait for Community tab to open
            await self.page.wait_for_load_state("networkidle")
            await self.simulator.random_delay(3.0, 5.0)

            # Upload Image
            image_btn_selector = "ytd-post-creation-dialog-endpoint:has(tp-yt-iron-icon[icon='image'])"
            try:
                # Often the UI is already in text post mode, we click the image icon
                await self.simulator.human_click(self.page, image_btn_selector)
                await self.simulator.random_delay(1.0, 2.0)
                
                file_input = await self.page.query_selector("input[type='file'][accept*='image']")
                if file_input:
                    await file_input.set_input_files(image_path)
            except Exception as e:
                self.logger.warning(f"Could not upload image directly, it might not be supported or UI changed: {e}")

            await self.simulator.random_delay(3.0, 5.0)

            # Type text
            text_box_selector = "div#contenteditable-root"
            try:
                await self.page.wait_for_selector(text_box_selector, timeout=10000)
                await self.simulator.human_type(self.page, text_box_selector, content)
            except Exception as e:
                return PostResult(False, "YouTube", error=f"Could not type content: {e}")

            await self.simulator.random_delay(1.5, 3.0)

            # Click Post
            post_btn_selector = "ytd-button-renderer#submit-button button"
            try:
                await self.page.wait_for_selector(post_btn_selector, state='visible', timeout=5000)
                await self.simulator.human_click(self.page, post_btn_selector)
            except Exception as e:
                return PostResult(False, "YouTube", error=f"Could not click Post button: {e}")

            # Wait for post to finish
            await self.simulator.random_delay(5.0, 8.0)
            
            return PostResult(True, "YouTube")
            
        except Exception as e:
            self.logger.error(f"YouTube posting failed: {e}")
            return PostResult(False, "YouTube", error=str(e))
        finally:
            await self.teardown()
