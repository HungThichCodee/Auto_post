import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional
from ..utils.browser_manager import BrowserManager
from ..utils.human_simulator import HumanSimulator

class PostResult:
    def __init__(self, success: bool, platform: str, 
                 post_url: str = "", error: str = ""):
        self.success = success
        self.platform = platform
        self.post_url = post_url
        self.error = error

class BasePoster(ABC):
    def __init__(self, browser_manager: BrowserManager, cookies_json: Optional[str] = None):
        self.browser_manager = browser_manager
        self.cookies_json = cookies_json
        self.logger = logging.getLogger(self.__class__.__name__)
        self.simulator = HumanSimulator()
        self.context = None
        self.page = None
        
    @abstractmethod
    async def post(self, content: str, image_path: str) -> PostResult:
        pass
    
    async def setup(self):
        """Setup the browser context and page for posting."""
        self.logger.info("Setting up browser for poster")
        self.context = await self.browser_manager.create_context(cookies_json=self.cookies_json)
        self.page = await self.browser_manager.new_page(context=self.context)
        self.logger.info("Poster browser setup complete")
            
    async def teardown(self):
        """Cleanup after posting."""
        self.logger.info("Tearing down poster")
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
        self.logger.info("Poster teardown complete")
