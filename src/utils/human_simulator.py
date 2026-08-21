import asyncio
import random
from playwright.async_api import Page
from typing import Tuple

class HumanSimulator:
    """Simulates human-like interactions to avoid bot detection."""
    
    @staticmethod
    async def random_delay(min_sec: float = 1.0, max_sec: float = 3.0):
        """Sleeps for a random duration between min_sec and max_sec."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
    
    @staticmethod
    async def human_type(page: Page, selector: str, text: str, delay_per_char: tuple = (50, 150)):
        """Types text character by character with random delays and occasional typos."""
        await page.focus(selector)
        for char in text:
            # 5% chance of typo
            if random.random() < 0.05 and char.isalpha():
                wrong_char = chr(ord(char) + random.choice([-1, 1]))
                if wrong_char.isalpha():
                    await page.keyboard.type(wrong_char)
                    await asyncio.sleep(random.randint(100, 300) / 1000.0)
                    await page.keyboard.press("Backspace")
                    await asyncio.sleep(random.randint(50, 150) / 1000.0)
            
            await page.keyboard.type(char)
            delay_ms = random.randint(delay_per_char[0], delay_per_char[1])
            await asyncio.sleep(delay_ms / 1000.0)
    
    @staticmethod
    async def natural_scroll(page: Page, distance: int = 300):
        """Scrolls the page in small, natural increments."""
        steps = random.randint(3, 7)
        step_distance = distance // steps
        
        for _ in range(steps):
            jitter = random.randint(-20, 20)
            actual_step = step_distance + jitter
            await page.mouse.wheel(0, actual_step)
            await asyncio.sleep(random.uniform(0.1, 0.4))
            
    @staticmethod
    async def random_mouse_movement(page: Page):
        """Moves the mouse to random positions on the page."""
        viewport = page.viewport_size
        if not viewport:
            return
            
        width = viewport['width']
        height = viewport['height']
        
        x = random.randint(0, width)
        y = random.randint(0, height)
        
        # Move in steps
        await page.mouse.move(x, y, steps=random.randint(5, 15))
    
    @staticmethod
    async def human_click(page: Page, selector: str):
        """Hovers then clicks an element with a slight offset."""
        element = await page.query_selector(selector)
        if not element:
            return
            
        box = await element.bounding_box()
        if not box:
            return
            
        # Target a random point within the element
        target_x = box['x'] + (box['width'] * random.uniform(0.2, 0.8))
        target_y = box['y'] + (box['height'] * random.uniform(0.2, 0.8))
        
        # Move to target
        await page.mouse.move(target_x, target_y, steps=random.randint(5, 10))
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Click
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await page.mouse.up()
        
    @staticmethod
    async def dismiss_popups(page: Page):
        """Attempts to dismiss common popups (cookies, newsletters, etc.)."""
        common_selectors = [
            "button:has-text('Accept')",
            "button:has-text('Got it')",
            "button:has-text('Close')",
            "[aria-label='Close']",
            ".cookie-banner .close"
        ]
        
        for selector in common_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    if await el.is_visible():
                        await el.click()
                        await asyncio.sleep(0.5)
            except Exception:
                pass
