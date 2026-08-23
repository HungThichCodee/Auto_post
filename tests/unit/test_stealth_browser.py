"""
tests/unit/test_stealth_browser.py
Unit tests for BrowserManager stealth launch flags, context randomization, and HumanSimulator behavior.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.utils.browser_manager import BrowserManager
from src.utils.human_simulator import HumanSimulator


@pytest.mark.asyncio
async def test_browser_manager_launch_stealth_args():
    """Verify BrowserManager launches Playwright Chromium with stealth flags."""
    bm = BrowserManager()

    mock_playwright = MagicMock()
    mock_chromium = MagicMock()
    mock_browser = AsyncMock()

    mock_chromium.launch = AsyncMock(return_value=mock_browser)
    mock_playwright.chromium = mock_chromium

    with patch("src.utils.browser_manager.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        browser = await bm.launch(headless=True)
        assert browser == mock_browser

        launch_kwargs = mock_chromium.launch.call_args[1]
        assert launch_kwargs["headless"] is True
        assert "--disable-blink-features=AutomationControlled" in launch_kwargs["args"]
        assert "--enable-automation" in launch_kwargs["ignore_default_args"]


@pytest.mark.asyncio
async def test_browser_manager_create_context_randomization():
    """Verify create_context randomizes viewport and sets desktop User-Agent."""
    bm = BrowserManager()
    bm.browser = MagicMock()
    mock_context = AsyncMock()
    bm.browser.new_context = AsyncMock(return_value=mock_context)

    cookies = json.dumps([{"name": "SID", "value": "xyz123", "domain": ".youtube.com", "path": "/"}])
    context = await bm.create_context(cookies_json=cookies)

    assert context == mock_context
    context_kwargs = bm.browser.new_context.call_args[1]
    assert "viewport" in context_kwargs
    assert "user_agent" in context_kwargs
    assert context_kwargs["has_touch"] is False
    assert mock_context.add_cookies.call_count == 1


@pytest.mark.asyncio
async def test_browser_manager_new_page_injects_stealth():
    """Verify new_page injects navigator.webdriver masking init script."""
    bm = BrowserManager()
    mock_context = MagicMock()
    mock_page = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    page = await bm.new_page(context=mock_context)
    assert page == mock_page
    assert mock_page.add_init_script.call_count == 1
    script_content = mock_page.add_init_script.call_args[0][0]
    assert "navigator, 'webdriver'" in script_content


@pytest.mark.asyncio
async def test_human_simulator_random_delay():
    """Verify HumanSimulator.random_delay invokes asyncio.sleep within range."""
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await HumanSimulator.random_delay(min_sec=0.5, max_sec=1.5)
        assert mock_sleep.call_count == 1
        delay = mock_sleep.call_args[0][0]
        assert 0.5 <= delay <= 1.5


@pytest.mark.asyncio
async def test_human_simulator_human_type():
    """Verify human_type focuses element and types characters."""
    mock_page = MagicMock()
    mock_page.focus = AsyncMock()
    mock_page.keyboard = MagicMock()
    mock_page.keyboard.type = AsyncMock()
    mock_page.keyboard.press = AsyncMock()

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await HumanSimulator.human_type(mock_page, "input#title", "Hello", delay_per_char=(1, 5))
        assert mock_page.focus.call_count == 1
        assert mock_page.keyboard.type.call_count >= 5


@pytest.mark.asyncio
async def test_human_simulator_natural_scroll():
    """Verify natural_scroll executes mouse wheel events in steps."""
    mock_page = MagicMock()
    mock_page.mouse = MagicMock()
    mock_page.mouse.wheel = AsyncMock()

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await HumanSimulator.natural_scroll(mock_page, distance=300)
        assert mock_page.mouse.wheel.call_count >= 3


@pytest.mark.asyncio
async def test_human_simulator_human_click():
    """Verify human_click queries element bounding box and performs mouse down/up."""
    mock_page = MagicMock()
    mock_element = MagicMock()
    mock_element.bounding_box = AsyncMock(return_value={"x": 50, "y": 100, "width": 80, "height": 30})
    mock_page.query_selector = AsyncMock(return_value=mock_element)
    mock_page.mouse = MagicMock()
    mock_page.mouse.move = AsyncMock()
    mock_page.mouse.down = AsyncMock()
    mock_page.mouse.up = AsyncMock()

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await HumanSimulator.human_click(mock_page, "button#submit")
        assert mock_page.query_selector.call_count == 1
        assert mock_page.mouse.down.call_count == 1
        assert mock_page.mouse.up.call_count == 1
