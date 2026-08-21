import asyncio
from typing import List
from .base_scraper import BaseScraper, ScrapedContent

class TiktokScraper(BaseScraper):
    async def scrape(self, url: str, max_posts: int = 5) -> List[ScrapedContent]:
        results = []
        if not self.page:
            await self.setup()
            
        try:
            self.logger.info(f"Navigating to TikTok URL: {url}")
            await self._safe_execute(self.page.goto, url, timeout=60000)
            await self.simulator.random_delay(3, 6)
            
            # Check for CAPTCHA
            if await self._is_captcha_present():
                self.logger.warning("TikTok CAPTCHA detected. Skipping scraping.")
                return results
                
            posts_scraped = 0
            scroll_attempts = 0
            max_scrolls = 15
            
            while posts_scraped < max_posts and scroll_attempts < max_scrolls:
                await self.simulator.natural_scroll(self.page, distance=600)
                await self.simulator.random_delay(2, 4)
                
                # Extract video cards
                videos = await self._extract_videos()
                
                for video in videos:
                    if posts_scraped >= max_posts:
                        break
                        
                    if not any(p.text == video['text'] for p in results):
                        content = ScrapedContent(
                            text=video['text'],
                            source_url=video.get('link', url),
                            platform="tiktok",
                            author=video.get('author', ''),
                            hashtags=video.get('hashtags', []),
                            engagement=video.get('engagement', {})
                        )
                        results.append(content)
                        posts_scraped += 1
                        
                scroll_attempts += 1
                
        except Exception as e:
            self.logger.error(f"Error during TikTok scraping: {e}")
        finally:
            return results

    async def _is_captcha_present(self) -> bool:
        try:
            captcha_selectors = [
                "#captcha-verify-image",
                ".captcha_verify_container",
                "[data-testid='captcha-challenge']"
            ]
            for selector in captcha_selectors:
                if await self.page.locator(selector).count() > 0:
                    return True
            return False
        except Exception:
            return False

    async def _extract_videos(self) -> List[dict]:
        extracted = []
        try:
            # Selectors for TikTok video cards/descriptions
            card_selectors = [
                "div[data-e2e='user-post-item']",
                "div.tiktok-yz6ijl-DivWrapper"
            ]
            
            for selector in card_selectors:
                elements = await self.page.locator(selector).all()
                if elements:
                    for element in elements:
                        try:
                            # Try to extract description
                            desc_element = element.locator("div[data-e2e='user-post-item-desc']").first
                            text = await desc_element.inner_text() if await desc_element.count() > 0 else ""
                            
                            if not text:
                                text = await element.inner_text() # fallback
                                
                            if text:
                                # Extract hashtags from text
                                hashtags = [word for word in text.split() if word.startswith('#')]
                                extracted.append({
                                    'text': text.strip(),
                                    'hashtags': hashtags
                                })
                        except Exception:
                            continue
                    break
        except Exception as e:
            self.logger.warning(f"Error extracting videos: {e}")
            
        return extracted
