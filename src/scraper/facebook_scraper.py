import asyncio
from typing import List
from .base_scraper import BaseScraper, ScrapedContent

class FacebookScraper(BaseScraper):
    async def scrape(self, url: str, max_posts: int = 5) -> List[ScrapedContent]:
        results = []
        if not self.page:
            await self.setup()
            
        try:
            self.logger.info(f"Navigating to Facebook URL: {url}")
            await self._safe_execute(self.page.goto, url, timeout=60000)
            await self.simulator.random_delay(2, 5)
            
            # Dismiss login popup if present
            await self._dismiss_login_popup()
            
            posts_scraped = 0
            scroll_attempts = 0
            max_scrolls = 15
            
            while posts_scraped < max_posts and scroll_attempts < max_scrolls:
                await self.simulator.natural_scroll(self.page, distance=800)
                await self.simulator.random_delay(1, 3)
                
                # Expand "See more" buttons
                await self._expand_see_more()
                
                # Extract posts
                posts = await self._extract_posts()
                
                for post in posts:
                    if posts_scraped >= max_posts:
                        break
                        
                    # Basic deduplication by text
                    if not any(p.text == post['text'] for p in results):
                        content = ScrapedContent(
                            text=post['text'],
                            source_url=url,
                            platform="facebook",
                            author=post.get('author', ''),
                            engagement=post.get('engagement', {})
                        )
                        results.append(content)
                        posts_scraped += 1
                        
                scroll_attempts += 1
                
        except Exception as e:
            self.logger.error(f"Error during Facebook scraping: {e}")
        finally:
            return results

    async def _dismiss_login_popup(self):
        try:
            close_buttons = [
                "div[aria-label='Close']",
                "div[aria-label='Đóng']",
                "i.x1b0d499.xep6ejk"
            ]
            for selector in close_buttons:
                button = self.page.locator(selector).first
                if await button.is_visible(timeout=2000):
                    await button.click()
                    self.logger.info("Dismissed login popup.")
                    await self.simulator.random_delay()
                    break
        except Exception:
            pass

    async def _expand_see_more(self):
        try:
            see_more_texts = ['See more', 'Xem thêm', '... See more']
            for text in see_more_texts:
                locators = await self.page.get_by_text(text, exact=False).all()
                for locator in locators:
                    if await locator.is_visible():
                        await locator.click()
                        await self.simulator.random_delay(0.5, 1.5)
        except Exception:
            pass

    async def _extract_posts(self) -> List[dict]:
        extracted = []
        try:
            post_selectors = [
                "div[data-ad-preview='message']",
                "div[dir='auto'][style*='text-align']",
                "div.x1iorvi4.x1pi30zi"
            ]
            
            for selector in post_selectors:
                elements = await self.page.locator(selector).all()
                if elements:
                    for element in elements:
                        try:
                            text = await element.inner_text()
                            if text and len(text.strip()) > 10:
                                extracted.append({'text': text.strip()})
                        except Exception:
                            continue
                    break
        except Exception as e:
            self.logger.warning(f"Error extracting posts: {e}")
            
        return extracted
