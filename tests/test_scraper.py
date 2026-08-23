"""
Unit and Offline Mock Tests for YoutubeScraper (Milestone M1).
Tests cover:
- URL normalization & routing (channel, shorts, watch, youtu.be)
- Single video URL detection
- Primary Engine: window.ytInitialData parsing (richGridRenderer, gridRenderer, reelItemRenderer)
- Secondary Engine: Multi-selector DOM fallback extraction with natural scrolling
- Single video watch page scraping
- Cookie and consent popup dismissal
- Exception resilience and error handling
- Backward compatibility with BaseScraper and ScrapedContent
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.scraper.youtube_scraper import YoutubeScraper
from src.scraper.base_scraper import ScrapedContent, BaseScraper
from src.models.pipeline_models import ScrapedVideo


@pytest.fixture
def mock_browser_manager():
    """Mock BrowserManager to avoid spawning actual headless browsers."""
    manager = MagicMock()
    context = AsyncMock()
    page = AsyncMock()
    manager.create_context = AsyncMock(return_value=context)
    manager.new_page = AsyncMock(return_value=page)
    return manager


# ==========================================
# 1. URL Normalization & Routing Tests
# ==========================================

def test_normalize_url_channel_handle():
    """Test channel handle normalization to /videos."""
    scraper = YoutubeScraper(browser_manager=MagicMock())
    assert scraper._normalize_url("https://www.youtube.com/@AI-thegioitihon") == "https://www.youtube.com/@AI-thegioitihon/videos"
    assert scraper._normalize_url("https://www.youtube.com/@AI-thegioitihon/") == "https://www.youtube.com/@AI-thegioitihon/videos"


def test_normalize_url_channel_sub_tabs():
    """Test stripping sub-tabs (/featured, /about, /community) and adding /videos."""
    scraper = YoutubeScraper(browser_manager=MagicMock())
    assert scraper._normalize_url("https://www.youtube.com/@Channel/featured") == "https://www.youtube.com/@Channel/videos"
    assert scraper._normalize_url("https://www.youtube.com/@Channel/about") == "https://www.youtube.com/@Channel/videos"
    assert scraper._normalize_url("https://www.youtube.com/@Channel/community") == "https://www.youtube.com/@Channel/videos"


def test_normalize_url_channel_id_and_c():
    """Test /channel/, /c/, and /user/ URLs normalization."""
    scraper = YoutubeScraper(browser_manager=MagicMock())
    assert scraper._normalize_url("https://www.youtube.com/channel/UC1234567890") == "https://www.youtube.com/channel/UC1234567890/videos"
    assert scraper._normalize_url("https://www.youtube.com/c/CustomName") == "https://www.youtube.com/c/CustomName/videos"


def test_normalize_url_preserved_endpoints():
    """Test that /videos, /shorts, and direct video URLs are preserved."""
    scraper = YoutubeScraper(browser_manager=MagicMock())
    assert scraper._normalize_url("https://www.youtube.com/@Channel/videos") == "https://www.youtube.com/@Channel/videos"
    assert scraper._normalize_url("https://www.youtube.com/@Channel/shorts") == "https://www.youtube.com/@Channel/shorts"
    assert scraper._normalize_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert scraper._normalize_url("https://youtu.be/dQw4w9WgXcQ") == "https://youtu.be/dQw4w9WgXcQ"
    assert scraper._normalize_url("https://www.youtube.com/shorts/abc123xyz") == "https://www.youtube.com/shorts/abc123xyz"


def test_is_single_video_url():
    """Test detection of single video vs channel pages."""
    scraper = YoutubeScraper(browser_manager=MagicMock())
    assert scraper._is_single_video_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True
    assert scraper._is_single_video_url("https://youtu.be/dQw4w9WgXcQ") is True
    assert scraper._is_single_video_url("https://www.youtube.com/shorts/dQw4w9WgXcQ") is True
    assert scraper._is_single_video_url("https://www.youtube.com/@AI-thegioitihon/videos") is False


# ==========================================
# 2. Engine 1: ytInitialData Extraction Tests
# ==========================================

@pytest.mark.asyncio
async def test_extract_via_yt_initial_data_rich_grid(mock_browser_manager):
    """Test Primary Engine extracting videos from richGridRenderer structure."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()

    mock_yt_data = {
        "contents": {
            "twoColumnBrowseResultsRenderer": {
                "tabs": [
                    {
                        "tabRenderer": {
                            "title": "Videos",
                            "content": {
                                "richGridRenderer": {
                                    "contents": [
                                        {
                                            "richItemRenderer": {
                                                "content": {
                                                    "videoRenderer": {
                                                        "videoId": "vid001",
                                                        "title": {"runs": [{"text": "Bí Ẩn Rừng Xanh #shorts #khampha"}]},
                                                        "viewCountText": {"simpleText": "25K views"},
                                                        "publishedTimeText": {"simpleText": "1 day ago"},
                                                        "lengthText": {"simpleText": "00:45"},
                                                        "ownerText": {"runs": [{"text": "Thế Giới Tí Hôn"}]},
                                                        "descriptionSnippet": {"runs": [{"text": "Khám phá bí ẩn rừng xanh sống động."}]},
                                                        "thumbnail": {
                                                            "thumbnails": [
                                                                {"url": "https://i.ytimg.com/vi/vid001/default.jpg"},
                                                                {"url": "https://i.ytimg.com/vi/vid001/hqdefault.jpg"}
                                                            ]
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        }
    }
    scraper.page.evaluate = AsyncMock(return_value=mock_yt_data)

    videos = await scraper._extract_via_yt_initial_data()
    assert len(videos) == 1
    v = videos[0]
    assert isinstance(v, ScrapedVideo)
    assert v.title == "Bí Ẩn Rừng Xanh #shorts #khampha"
    assert v.url == "https://www.youtube.com/watch?v=vid001"
    assert v.views == "25K views"
    assert v.timestamp == "1 day ago"
    assert v.duration_str == "00:45"
    assert v.channel == "Thế Giới Tí Hôn"
    assert v.thumbnail_url == "https://i.ytimg.com/vi/vid001/hqdefault.jpg"
    assert "#shorts" in v.tags
    assert "#khampha" in v.tags
    assert "Bí Ẩn Rừng Xanh" in v.raw_text


@pytest.mark.asyncio
async def test_extract_via_yt_initial_data_section_list_grid(mock_browser_manager):
    """Test Primary Engine extracting videos from sectionListRenderer/gridRenderer."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()

    mock_yt_data = {
        "contents": {
            "twoColumnBrowseResultsRenderer": {
                "tabs": [
                    {
                        "tabRenderer": {
                            "title": "Videos",
                            "content": {
                                "sectionListRenderer": {
                                    "contents": [
                                        {
                                            "itemSectionRenderer": {
                                                "contents": [
                                                    {
                                                        "gridRenderer": {
                                                            "items": [
                                                                {
                                                                    "gridVideoRenderer": {
                                                                        "videoId": "grid002",
                                                                        "title": {"simpleText": "Cuộc Sống Động Vật"},
                                                                        "viewCountText": {"simpleText": "100K views"},
                                                                        "publishedTimeText": {"simpleText": "3 days ago"},
                                                                        "shortBylineText": {"runs": [{"text": "Kênh Động Vật"}]}
                                                                    }
                                                                }
                                                            ]
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        }
    }
    scraper.page.evaluate = AsyncMock(return_value=mock_yt_data)

    videos = await scraper._extract_via_yt_initial_data()
    assert len(videos) == 1
    assert videos[0].title == "Cuộc Sống Động Vật"
    assert videos[0].url == "https://www.youtube.com/watch?v=grid002"
    assert videos[0].views == "100K views"
    assert videos[0].channel == "Kênh Động Vật"


@pytest.mark.asyncio
async def test_extract_via_yt_initial_data_none_or_corrupt(mock_browser_manager):
    """Test Primary Engine gracefully handles None or malformed ytInitialData."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()

    # When evaluate returns None
    scraper.page.evaluate = AsyncMock(return_value=None)
    videos = await scraper._extract_via_yt_initial_data()
    assert videos == []

    # When evaluate throws an exception
    scraper.page.evaluate = AsyncMock(side_effect=Exception("JS Evaluation Failed"))
    videos = await scraper._extract_via_yt_initial_data()
    assert videos == []


# ==========================================
# 3. Engine 2: DOM Fallback Extraction Tests
# ==========================================

@pytest.mark.asyncio
async def test_extract_via_dom_scrolling(mock_browser_manager):
    """Test Secondary Engine extracting videos from rendered DOM elements."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()

    # Setup element mock
    mock_el = AsyncMock()

    # Title & link locator
    mock_title_loc = AsyncMock()
    mock_title_loc.count = AsyncMock(return_value=1)
    mock_title_loc.inner_text = AsyncMock(return_value="Câu Chuyện Chú Voi Con #shorts")
    mock_title_loc.get_attribute = AsyncMock(return_value="/watch?v=elephant123")

    # Metadata locator (views, date)
    mock_meta_loc = AsyncMock()
    mock_meta_loc.all_inner_texts = AsyncMock(return_value=["12K views", "5 days ago"])

    # Duration locator
    mock_dur_loc = AsyncMock()
    mock_dur_loc.count = AsyncMock(return_value=1)
    mock_dur_loc.inner_text = AsyncMock(return_value="0:58")

    # Channel locator
    mock_chan_loc = AsyncMock()
    mock_chan_loc.count = AsyncMock(return_value=1)
    mock_chan_loc.inner_text = AsyncMock(return_value="Thế Giới Tí Hôn")

    def mock_locator_router(selector):
        loc = AsyncMock()
        if "title" in selector:
            loc.first = mock_title_loc
            return loc
        elif "metadata" in selector:
            return mock_meta_loc
        elif "thumbnail-overlay" in selector or "badge" in selector:
            loc.first = mock_dur_loc
            return loc
        elif "channel" in selector:
            loc.first = mock_chan_loc
            return loc
        return loc

    mock_el.locator = MagicMock(side_effect=mock_locator_router)

    # Page locator for cards
    mock_card_locator = AsyncMock()
    mock_card_locator.all = AsyncMock(return_value=[mock_el])

    def page_locator_router(selector):
        if selector == "ytd-rich-item-renderer":
            return mock_card_locator
        empty_loc = AsyncMock()
        empty_loc.all = AsyncMock(return_value=[])
        return empty_loc

    scraper.page.locator = MagicMock(side_effect=page_locator_router)

    videos = await scraper._extract_via_dom_scrolling(max_videos=1)
    assert len(videos) == 1
    assert videos[0].title == "Câu Chuyện Chú Voi Con #shorts"
    assert videos[0].url == "https://www.youtube.com/watch?v=elephant123"
    assert videos[0].views == "12K views"
    assert videos[0].timestamp == "5 days ago"
    assert videos[0].duration_str == "0:58"
    assert videos[0].channel == "Thế Giới Tí Hôn"
    assert "#shorts" in videos[0].tags


# ==========================================
# 4. Single Video Scraping Tests
# ==========================================

@pytest.mark.asyncio
async def test_scrape_single_video(mock_browser_manager):
    """Test extracting rich metadata for a single /watch?v=... page."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()

    # Title locator
    mock_title_loc = AsyncMock()
    mock_title_loc.count = AsyncMock(return_value=1)
    mock_title_loc.inner_text = AsyncMock(return_value="Kỳ Quan Thiên Nhiên #khampha")

    # Channel locator
    mock_chan_loc = AsyncMock()
    mock_chan_loc.count = AsyncMock(return_value=1)
    mock_chan_loc.inner_text = AsyncMock(return_value="Discovery Channel")

    # Description expander
    mock_expand_loc = AsyncMock()
    mock_expand_loc.is_visible = AsyncMock(return_value=True)
    mock_expand_loc.click = AsyncMock()

    # Description text
    mock_desc_loc = AsyncMock()
    mock_desc_loc.count = AsyncMock(return_value=1)
    mock_desc_loc.inner_text = AsyncMock(return_value="Khám phá các kỳ quan thiên nhiên trên toàn thế giới.")

    # Info locator
    mock_info_loc = AsyncMock()
    mock_info_loc.count = AsyncMock(return_value=1)
    mock_info_loc.inner_text = AsyncMock(return_value="500,000 views")

    def page_locator_router(selector):
        loc = AsyncMock()
        if "ytd-watch-metadata" in selector or "title" in selector:
            loc.first = mock_title_loc
        elif "owner" in selector or "channel-name" in selector:
            loc.first = mock_chan_loc
        elif "expand" in selector:
            loc.first = mock_expand_loc
        elif "description" in selector:
            loc.first = mock_desc_loc
        elif "info-container" in selector or "watch-info" in selector:
            loc.first = mock_info_loc
        return loc

    scraper.page.locator = MagicMock(side_effect=page_locator_router)

    video = await scraper._scrape_single_video("https://www.youtube.com/watch?v=discovery123")
    assert video is not None
    assert video.title == "Kỳ Quan Thiên Nhiên #khampha"
    assert video.channel == "Discovery Channel"
    assert video.description == "Khám phá các kỳ quan thiên nhiên trên toàn thế giới."
    assert video.views == "500,000 views"
    assert video.url == "https://www.youtube.com/watch?v=discovery123"
    assert "#khampha" in video.tags


# ==========================================
# 5. Consent Popup Dismissal Tests
# ==========================================

@pytest.mark.asyncio
async def test_dismiss_consent_popup(mock_browser_manager):
    """Test multi-language consent popup dismissal."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()

    mock_btn = AsyncMock()
    mock_btn.is_visible = AsyncMock(return_value=True)
    mock_btn.click = AsyncMock()

    mock_btn_loc = AsyncMock()
    mock_btn_loc.first = mock_btn

    scraper.page.locator = MagicMock(return_value=mock_btn_loc)
    scraper.page.evaluate = AsyncMock()

    await scraper._dismiss_consent_popup()
    mock_btn.click.assert_called_once()


# ==========================================
# 6. Full Scrape Flow & Compatibility Tests
# ==========================================

@pytest.mark.asyncio
async def test_full_scrape_method_returns_scraped_videos(mock_browser_manager):
    """Test that scrape() returns List[ScrapedVideo] compatible with BaseScraper."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()
    scraper.page.goto = AsyncMock()

    sample_video = ScrapedVideo(
        title="Sample Video",
        url="https://youtube.com/watch?v=sample",
        channel="MyChannel",
        views="10K views",
        duration_str="02:30"
    )

    scraper._extract_via_yt_initial_data = AsyncMock(return_value=[sample_video])

    results = await scraper.scrape("https://www.youtube.com/@AI-thegioitihon", max_posts=1)

    assert len(results) == 1
    video = results[0]
    assert isinstance(video, ScrapedVideo)
    assert isinstance(video, ScrapedContent)
    assert video.title == "Sample Video"
    assert video.text == "Sample Video\nViews: 10K views"
    assert video.source_url == "https://youtube.com/watch?v=sample"
    assert video.author == "MyChannel"
    assert video.engagement["views"] == "10K views"


@pytest.mark.asyncio
async def test_scrape_handles_navigation_exception_gracefully(mock_browser_manager):
    """Test that navigation exceptions are caught and an empty list is returned."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()
    scraper.page.goto = AsyncMock(side_effect=Exception("Navigation timeout"))

    results = await scraper.scrape("https://www.youtube.com/@FailChannel", max_posts=5)
    assert results == []
