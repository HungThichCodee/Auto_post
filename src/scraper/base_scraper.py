import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
from playwright.async_api import Page, BrowserContext

from ..utils.browser_manager import BrowserManager
from ..utils.human_simulator import HumanSimulator

class ScrapedContent:
    """Data class for scraped content."""
    def __init__(self, text: str, source_url: str, platform: str, 
                 author: str = "", hashtags: list = None, 
                 engagement: dict = None, scraped_at: str = ""):
        self.text = text
        self.source_url = source_url
        self.platform = platform
        self.author = author
        self.hashtags = hashtags or []
        self.engagement = engagement or {}
        self.scraped_at = scraped_at or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source_url": self.source_url,
            "platform": self.platform,
            "author": self.author,
            "hashtags": self.hashtags,
            "engagement": self.engagement,
            "scraped_at": self.scraped_at
        }

class BaseScraper(ABC):
    def __init__(self, browser_manager: BrowserManager, cookies_json: Optional[str] = None):
        self.browser_manager = browser_manager
        self.cookies_json = cookies_json
        self.logger = logging.getLogger(self.__class__.__name__)
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.simulator = HumanSimulator()
        
    @abstractmethod
    async def scrape(self, url: str, max_posts: int = 5) -> List[ScrapedContent]:
        """Scrape posts from the given URL."""
        pass
        
    async def setup(self):
        """Setup browser context and page, optionally loading cookies."""
        self.logger.info("Setting up scraper...")
        self.context = await self.browser_manager.create_context(cookies_json=self.cookies_json)
        self.page = await self.browser_manager.new_page(context=self.context)
        self.logger.info("Scraper setup complete.")

    async def teardown(self):
        """Close page and context."""
        self.logger.info("Tearing down scraper...")
        if self.page:
            try:
                await self.page.close()
            except Exception as e:
                self.logger.warning(f"Error closing page: {e}")
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                self.logger.warning(f"Error closing context: {e}")
        self.logger.info("Scraper teardown complete.")

    async def _safe_execute(self, func, *args, retries=3, **kwargs):
        """Execute a function safely with retries."""
        for attempt in range(retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == retries - 1:
                    self.logger.error(f"All {retries} attempts failed.")
                    raise
                await asyncio.sleep(2 * (attempt + 1))
