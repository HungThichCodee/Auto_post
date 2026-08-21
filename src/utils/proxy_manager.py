import httpx
import random
import logging
from typing import Optional
from .logger import setup_logger

logger = setup_logger(__name__)

class ProxyManager:
    """Manages proxy rotation for web scraping to avoid IP bans."""
    
    def __init__(self, proxy_list: Optional[str] = None):
        self.proxies: list[str] = []
        if proxy_list:
            self.proxies = [p.strip() for p in proxy_list.split(",") if p.strip()]
            logger.info(f"Initialized ProxyManager with {len(self.proxies)} provided proxies.")
        
    async def fetch_free_proxies(self) -> list[str]:
        """Fetches free proxies from public APIs."""
        urls = [
            "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text",
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt"
        ]
        
        fetched = set()
        async with httpx.AsyncClient(timeout=15.0) as client:
            for url in urls:
                try:
                    logger.info(f"Fetching proxies from {url}")
                    response = await client.get(url)
                    response.raise_for_status()
                    lines = response.text.splitlines()
                    for line in lines:
                        line = line.strip()
                        if line:
                            # Assume http if no protocol
                            if not line.startswith("http://") and not line.startswith("https://") and not line.startswith("socks"):
                                line = f"http://{line}"
                            fetched.add(line)
                except Exception as e:
                    logger.warning(f"Failed to fetch proxies from {url}: {e}")
                    
        valid_proxies = []
        logger.info(f"Validating {len(fetched)} fetched proxies...")
        # Validate a small batch to save time (e.g., top 20)
        to_validate = list(fetched)[:20]
        for p in to_validate:
            if await self.validate_proxy(p):
                valid_proxies.append(p)
                
        self.proxies.extend(valid_proxies)
        logger.info(f"Added {len(valid_proxies)} valid proxies. Total: {len(self.proxies)}")
        return valid_proxies
    
    def get_random_proxy(self) -> Optional[dict]:
        """Returns a random proxy in Playwright format."""
        if not self.proxies:
            return None
        proxy = random.choice(self.proxies)
        return {"server": proxy}
    
    async def validate_proxy(self, proxy: str) -> bool:
        """Tests if a proxy works by requesting a known URL."""
        test_url = "https://httpbin.org/ip"
        try:
            async with httpx.AsyncClient(proxies=proxy, timeout=10.0) as client:
                response = await client.get(test_url)
                if response.status_code == 200:
                    return True
        except Exception:
            pass
        return False
    
    async def refresh_proxies(self):
        """Clears invalid and fetches new ones."""
        logger.info("Refreshing proxies...")
        valid = []
        for p in self.proxies:
            if await self.validate_proxy(p):
                valid.append(p)
        self.proxies = valid
        if len(self.proxies) < 5:
            await self.fetch_free_proxies()
