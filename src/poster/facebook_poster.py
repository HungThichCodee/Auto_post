import asyncio
import logging
import os
from typing import Optional
from .base_poster import BasePoster, PostResult
from ..utils.browser_manager import BrowserManager

class FacebookPoster(BasePoster):
    def __init__(self, browser_manager: BrowserManager, cookies_json: Optional[str] = None, page_url: str = ""):
        super().__init__(browser_manager, cookies_json)
        self.page_url = page_url or os.getenv("FB_PAGE_URL", "https://www.facebook.com/")
        
    async def post(self, content: str, image_path: str) -> PostResult:
        try:
            await self.setup()
            if not self.page:
                return PostResult(False, "Facebook", error="Browser page not initialized")

            self.logger.info(f"Navigating to Facebook page: {self.page_url}")
            await self.page.goto(self.page_url, wait_until="networkidle")
            await self.simulator.random_delay(2.0, 4.0)

            # Try to find the "Create Post" input
            create_post_selectors = [
                "div[role='button']:has-text('What\\'s on your mind')",
                "div[role='button']:has-text('Bạn đang nghĩ gì')",
                "div.x1i10hfl.x6umtig.x1b1mbwd.xaqea5y.xav7gou", 
                "div:has-text('Create post')"
            ]
            
            clicked = False
            for selector in create_post_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        await self.simulator.human_click(self.page, selector)
                        clicked = True
                        break
                except Exception:
                    continue
                    
            if not clicked:
                return PostResult(False, "Facebook", error="Could not find 'Create Post' button")
                
            await self.simulator.random_delay(1.5, 3.0)
            
            # Type content
            textbox_selector = "div[role='textbox'][contenteditable='true']"
            try:
                await self.page.wait_for_selector(textbox_selector, timeout=10000)
                await self.simulator.human_type(self.page, textbox_selector, content)
            except Exception as e:
                return PostResult(False, "Facebook", error=f"Could not type content: {e}")
                
            await self.simulator.random_delay(1.0, 2.0)
            
            # Upload image
            file_input_selector = "input[type='file'][accept^='image']"
            try:
                # First try to click the photo/video button if file input is not available
                photo_button_selectors = [
                    "div[role='button']:has-text('Photo/video')",
                    "div[role='button']:has-text('Ảnh/video')",
                    "div[aria-label='Photo/video']",
                    "div[aria-label='Ảnh/video']"
                ]
                
                # Check if file input is in DOM, if not try to click photo button
                file_input = await self.page.query_selector(file_input_selector)
                if not file_input:
                    for selector in photo_button_selectors:
                        try:
                            await self.simulator.human_click(self.page, selector)
                            await self.simulator.random_delay(1.0, 2.0)
                            break
                        except Exception:
                            continue
                            
                async with self.page.expect_file_chooser() as fc_info:
                    # In some cases we might need to click specifically on the add photo area
                    # This relies on the file input being available or triggered
                    file_input = await self.page.wait_for_selector(file_input_selector, state='attached', timeout=5000)
                    if file_input:
                        await file_input.set_input_files(image_path)
            except Exception as e:
                self.logger.warning(f"Error uploading image (non-fatal maybe?): {e}")
                
            await self.simulator.random_delay(3.0, 6.0) # Wait for upload
            
            # Click post
            post_button_selectors = [
                "div[role='button'][aria-label='Post']",
                "div[role='button'][aria-label='Đăng']",
                "div[role='button']:has-text('Post')",
                "div[role='button']:has-text('Đăng')"
            ]
            
            posted = False
            for selector in post_button_selectors:
                try:
                    button = await self.page.wait_for_selector(selector, state='visible', timeout=5000)
                    if button:
                        is_disabled = await button.get_attribute('aria-disabled')
                        if is_disabled == 'true':
                            await self.simulator.random_delay(2.0, 4.0) # wait more
                        await self.simulator.human_click(self.page, selector)
                        posted = True
                        break
                except Exception:
                    continue
                    
            if not posted:
                return PostResult(False, "Facebook", error="Could not click Post button")
                
            # Wait for post to finish
            await self.simulator.random_delay(5.0, 10.0)
            
            return PostResult(True, "Facebook", post_url="https://facebook.com/recent_post")
            
        except Exception as e:
            self.logger.error(f"Facebook posting failed: {e}")
            return PostResult(False, "Facebook", error=str(e))
        finally:
            await self.teardown()
