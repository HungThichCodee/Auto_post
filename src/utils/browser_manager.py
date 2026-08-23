import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
import json
import logging
from typing import Optional
import random

from .proxy_manager import ProxyManager
from .human_simulator import HumanSimulator
from .logger import setup_logger

logger = setup_logger(__name__)

class BrowserManager:
    """Manages Playwright browser with stealth and anti-detection."""
    
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.proxy_manager = proxy_manager
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self._contexts: list[BrowserContext] = []
        
    async def launch(self, headless: bool = True) -> Browser:
        """Launches Chromium with stealth settings."""
        self.playwright = await async_playwright().start()
        
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-extensions',
            '--window-position=0,0'
        ]
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=args,
            ignore_default_args=["--enable-automation"]
        )
        logger.info(f"Launched browser (headless={headless})")
        return self.browser
        
    async def create_context(self, cookies_json: Optional[str] = None, proxy: Optional[dict] = None) -> BrowserContext:
        """Creates a browser context with stealth options."""
        if not self.browser:
            raise RuntimeError("Browser not launched. Call launch() first.")
            
        viewport_sizes = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1536, "height": 864}
        ]
        viewport = random.choice(viewport_sizes)
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        ]
        
        context_args = {
            "viewport": viewport,
            "user_agent": random.choice(user_agents),
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "color_scheme": "dark",
            "has_touch": False
        }
        
        if proxy:
            context_args["proxy"] = proxy
        elif self.proxy_manager:
            p = self.proxy_manager.get_random_proxy()
            if p:
                context_args["proxy"] = p
                
        context = await self.browser.new_context(**context_args)
        
        if cookies_json:
            try:
                cookies = json.loads(cookies_json)
                # Fix sameSite values for Playwright
                for cookie in cookies:
                    if 'sameSite' in cookie:
                        if cookie['sameSite'] and cookie['sameSite'].lower() == 'no_restriction':
                            cookie['sameSite'] = 'None'
                await context.add_cookies(cookies)
                logger.info("Injected cookies into context.")
            except Exception as e:
                logger.error(f"Failed to load cookies: {e}")
                
        self._contexts.append(context)
        return context
        
    async def new_page(self, context: Optional[BrowserContext] = None) -> Page:
        """Creates a new page with stealth scripts injected."""
        if not context:
            if not self._contexts:
                context = await self.create_context()
            else:
                context = self._contexts[-1]
                
        page = await context.new_page()
        
        # Inject stealth scripts
        stealth_script = """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3]
            });
        """
        await page.add_init_script(stealth_script)
        logger.info("Created new page with stealth injected.")
        return page
        
    async def close(self):
        """Cleanly shuts down the browser and playwright."""
        for context in self._contexts:
            await context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed.")
