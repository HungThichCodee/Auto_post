"""
Comprehensive Adversarial Stress Test Suite for YoutubeScraper (Milestone M1).

Stress-tests:
1. Tricky & Malformed URL Inputs
2. Corrupted & Unexpected window.ytInitialData JSON Schemas
3. Corrupted & Missing DOM Elements in Fallback Engine
4. Network Failures, Timeouts, and Page Navigation Crashes
5. Dual-Engine Interaction, Deduplication & Partial Returns
6. Single Video Page Edge Cases & Failures
7. Consent Popup Failures & Overlays
8. Contract Conformance & Backward Compatibility
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


# ============================================================================
# TIER 1: TRICKY & ADVERSARIAL URL INPUTS
# ============================================================================

@pytest.mark.parametrize("input_url,expected_output", [
    ("https://www.youtube.com/@complex.name_123-v2", "https://www.youtube.com/@complex.name_123-v2/videos"),
    ("https://www.youtube.com/@channel/", "https://www.youtube.com/@channel/videos"),
    ("https://www.youtube.com/@channel///", "https://www.youtube.com/@channel/videos"),
    ("https://www.youtube.com/@channel/featured", "https://www.youtube.com/@channel/videos"),
    ("https://www.youtube.com/@channel/about", "https://www.youtube.com/@channel/videos"),
    ("https://www.youtube.com/@channel/community", "https://www.youtube.com/@channel/videos"),
    ("https://www.youtube.com/channel/UCabcdef123456", "https://www.youtube.com/channel/UCabcdef123456/videos"),
    ("https://www.youtube.com/c/CustomChannel", "https://www.youtube.com/c/CustomChannel/videos"),
    ("https://www.youtube.com/user/LegacyUser", "https://www.youtube.com/user/LegacyUser/videos"),
    ("https://www.youtube.com/@channel/videos", "https://www.youtube.com/@channel/videos"),
    ("https://www.youtube.com/@channel/shorts", "https://www.youtube.com/@channel/shorts"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s"),
    ("https://youtu.be/dQw4w9WgXcQ?si=tracking_id_123", "https://youtu.be/dQw4w9WgXcQ?si=tracking_id_123"),
    ("https://www.youtube.com/shorts/abc123XYZ_9", "https://www.youtube.com/shorts/abc123XYZ_9"),
    ("  https://www.youtube.com/@spaces_around  ", "https://www.youtube.com/@spaces_around/videos"),
])
def test_url_normalization_adversarial_matrix(input_url, expected_output):
    """Test URL normalization across complex edge-case URL formats."""
    scraper = YoutubeScraper(browser_manager=MagicMock())
    assert scraper._normalize_url(input_url) == expected_output


@pytest.mark.parametrize("url,expected_is_single", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
    ("https://www.youtube.com/watch?v=abc&list=xyz", True),
    ("https://youtu.be/dQw4w9WgXcQ", True),
    ("https://youtu.be/dQw4w9WgXcQ?t=5", True),
    ("https://www.youtube.com/shorts/abc_123", True),
    ("https://www.youtube.com/@AI-thegioitihon", False),
    ("https://www.youtube.com/@AI-thegioitihon/videos", False),
    ("https://www.youtube.com/@AI-thegioitihon/shorts", False),
    ("https://www.youtube.com/channel/UC12345", False),
])
def test_is_single_video_url_matrix(url, expected_is_single):
    """Test single video URL detection across various formats."""
    scraper = YoutubeScraper(browser_manager=MagicMock())
    assert scraper._is_single_video_url(url) == expected_is_single


# ============================================================================
# TIER 2: CORRUPTED & UNEXPECTED ytInitialData SCHEMAS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("corrupted_payload", [
    None,
    {},
    {"contents": None},
    {"contents": {}},
    {"contents": {"twoColumnBrowseResultsRenderer": None}},
    {"contents": {"twoColumnBrowseResultsRenderer": {}}},
    {"contents": {"twoColumnBrowseResultsRenderer": {"tabs": None}}},
    {"contents": {"twoColumnBrowseResultsRenderer": {"tabs": []}}},
    {"contents": {"twoColumnBrowseResultsRenderer": {"tabs": [None, {}, {"tabRenderer": None}]}}},
    {"contents": {"twoColumnBrowseResultsRenderer": {"tabs": [{"tabRenderer": {"content": None}}]}}},
    {"contents": {"twoColumnBrowseResultsRenderer": {"tabs": [{"tabRenderer": {"content": {"richGridRenderer": None}}}]}}},
    {"contents": {"twoColumnBrowseResultsRenderer": {"tabs": [{"tabRenderer": {"content": {"richGridRenderer": {"contents": [None, {}]}}}}]}}},
    {"contents": {"twoColumnBrowseResultsRenderer": {"tabs": [{"tabRenderer": {"content": {"sectionListRenderer": None}}}]}}},
    12345,
    "corrupted string",
    ["array", "of", "items"],
    True,
])
async def test_extract_via_yt_initial_data_malformed_schemas(mock_browser_manager, corrupted_payload):
    """Test that Primary Engine handles malformed/corrupted JS payloads without throwing."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()
    scraper.page.evaluate = AsyncMock(return_value=corrupted_payload)

    videos = await scraper._extract_via_yt_initial_data()
    assert isinstance(videos, list)
    assert len(videos) == 0


@pytest.mark.asyncio
async def test_extract_via_yt_initial_data_js_exception(mock_browser_manager):
    """Test that JS evaluate exceptions in Primary Engine are caught gracefully."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()
    scraper.page.evaluate = AsyncMock(side_effect=Exception("Execution context was destroyed."))

    videos = await scraper._extract_via_yt_initial_data()
    assert isinstance(videos, list)
    assert len(videos) == 0


@pytest.mark.parametrize("renderer_input,expected_valid", [
    ({}, False),
    ({"videoId": ""}, False),
    ({"videoId": "vid123"}, False),  # Missing title -> invalid
    ({"videoId": "vid123", "title": ""}, False),
    ({"videoId": "vid123", "title": {"runs": []}}, False),
    ({"videoId": "vid123", "title": {"runs": [{}]}}, False),
    ({"videoId": "vid123", "title": {"runs": [{"text": ""}]}}, False),
    ({"videoId": "vid123", "title": {"runs": [{"text": "Valid Title"}]}}, True),
    ({"videoId": "vid123", "title": {"simpleText": "Simple Title"}}, True),
    ({"videoId": "vid123", "title": {"accessibility": {"accessibilityData": {"label": "A11y Title"}}}}, True),
    ({"videoId": "vid123", "title": "Direct String Title"}, True),
    ({"videoId": "vid123", "headline": {"simpleText": "Headline Title"}}, True),
    ({"videoId": "vid123", "headline": "Direct Headline Title"}, True),
])
def test_parse_renderer_dict_title_variations(renderer_input, expected_valid):
    """Test renderer dictionary parsing across various title schema structures."""
    scraper = YoutubeScraper(browser_manager=MagicMock())
    result = scraper._parse_renderer_dict(renderer_input)
    if expected_valid:
        assert result is not None
        assert isinstance(result, ScrapedVideo)
        assert result.url == "https://www.youtube.com/watch?v=vid123"
        assert len(result.title) > 0
    else:
        assert result is None


def test_parse_renderer_dict_rich_metadata_variations():
    """Test parser resilience with diverse views, length, timestamps, and bylines."""
    scraper = YoutubeScraper(browser_manager=MagicMock())

    # Case A: Runs based views and duration
    renderer_a = {
        "videoId": "vid_case_a",
        "title": {"runs": [{"text": "Test Video A #fun #nature"}]},
        "viewCountText": {"runs": [{"text": "1.2M"}, {"text": " views"}]},
        "publishedTimeText": {"runs": [{"text": "2"}, {"text": " weeks ago"}]},
        "lengthText": {"runs": [{"text": "12:"}, {"text": "34"}]},
        "ownerText": {"runs": [{"text": "Nature Channel"}]},
        "descriptionSnippet": {"runs": [{"text": "Description line 1. "}, {"text": "Line 2."}]},
        "thumbnail": {"thumbnails": [{"url": "http://img1.jpg"}, {"url": "http://img2.jpg"}]}
    }
    res_a = scraper._parse_renderer_dict(renderer_a)
    assert res_a is not None
    assert res_a.title == "Test Video A #fun #nature"
    assert res_a.views == "1.2M views"
    assert res_a.timestamp == "2 weeks ago"
    assert res_a.duration_str == "12:34"
    assert res_a.channel == "Nature Channel"
    assert res_a.description == "Description line 1. Line 2."
    assert res_a.thumbnail_url == "http://img2.jpg"
    assert "#fun" in res_a.tags
    assert "#nature" in res_a.tags
    assert res_a.is_short is False

    # Case B: String based and shortViewCountText
    renderer_b = {
        "videoId": "vid_case_b",
        "title": "Direct String Title",
        "shortViewCountText": "500K",
        "publishedTimeText": "1 day ago",
        "lengthText": "0:45",
        "shortBylineText": {"runs": [{"text": "Byline Channel"}]},
        "navigationEndpoint": {"reelWatchEndpoint": {}}
    }
    res_b = scraper._parse_renderer_dict(renderer_b)
    assert res_b is not None
    assert res_b.title == "Direct String Title"
    assert res_b.views == "500K"
    assert res_b.channel == "Byline Channel"
    assert res_b.is_short is True


# ============================================================================
# TIER 3: CORRUPTED & MISSING DOM ELEMENTS (SECONDARY ENGINE)
# ============================================================================

@pytest.mark.asyncio
async def test_extract_via_dom_scrolling_corrupted_elements(mock_browser_manager):
    """Test Secondary Engine resilience when DOM elements have missing or broken sub-locators."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()

    # Create 3 elements:
    # El 1: Empty title -> skipped
    # El 2: Valid title, missing metadata/duration/channel -> succeeds with defaults
    # El 3: Exception on inner_text -> skipped

    el1 = AsyncMock()
    title_loc_1 = AsyncMock()
    title_loc_1.count = AsyncMock(return_value=0)  # No title locator
    el1.locator = MagicMock(return_value=MagicMock(first=title_loc_1))

    el2 = AsyncMock()
    title_loc_2 = AsyncMock()
    title_loc_2.count = AsyncMock(return_value=1)
    title_loc_2.inner_text = AsyncMock(return_value="Resilient Video #tag")
    title_loc_2.get_attribute = AsyncMock(return_value="/watch?v=resilient123")

    meta_loc_2 = AsyncMock()
    meta_loc_2.all_inner_texts = AsyncMock(return_value=[])  # Empty metadata

    dur_loc_2 = AsyncMock()
    dur_loc_2.count = AsyncMock(return_value=0)  # No duration

    chan_loc_2 = AsyncMock()
    chan_loc_2.count = AsyncMock(return_value=0)  # No channel

    def router_el2(sel):
        loc = AsyncMock()
        if "title" in sel:
            loc.first = title_loc_2
        elif "metadata" in sel:
            return meta_loc_2
        elif "thumbnail" in sel or "badge" in sel:
            loc.first = dur_loc_2
        elif "channel" in sel:
            loc.first = chan_loc_2
        return loc

    el2.locator = MagicMock(side_effect=router_el2)

    el3 = AsyncMock()
    title_loc_3 = AsyncMock()
    title_loc_3.count = AsyncMock(return_value=1)
    title_loc_3.inner_text = AsyncMock(side_effect=Exception("Element detached from DOM"))
    el3.locator = MagicMock(return_value=MagicMock(first=title_loc_3))

    card_loc = AsyncMock()
    card_loc.all = AsyncMock(return_value=[el1, el2, el3])

    def page_loc_router(sel):
        if sel == "ytd-rich-item-renderer":
            return card_loc
        empty_loc = AsyncMock()
        empty_loc.all = AsyncMock(return_value=[])
        return empty_loc

    scraper.page.locator = MagicMock(side_effect=page_loc_router)

    videos = await scraper._extract_via_dom_scrolling(max_videos=5)
    assert len(videos) == 1
    v = videos[0]
    assert v.title == "Resilient Video #tag"
    assert v.url == "https://www.youtube.com/watch?v=resilient123"
    assert v.views == ""
    assert v.duration_str == ""
    assert v.channel == ""
    assert "#tag" in v.tags


# ============================================================================
# TIER 4: NETWORK FAILURES, TIMEOUTS, AND PAGE NAVIGATION CRASHES
# ============================================================================

@pytest.mark.asyncio
async def test_scrape_videos_navigation_timeout_retries_and_returns_empty(mock_browser_manager):
    """Test that total navigation failure retries 3 times and returns empty list cleanly."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()
    scraper.page.goto = AsyncMock(side_effect=Exception("net::ERR_CONNECTION_TIMED_OUT"))

    # Should not raise exception
    results = await scraper.scrape_videos("https://www.youtube.com/@BrokenChannel", max_videos=5)
    assert isinstance(results, list)
    assert results == []
    # Verify _safe_execute retried 3 times
    assert scraper.page.goto.call_count == 3


@pytest.mark.asyncio
async def test_scrape_videos_target_closed_crash(mock_browser_manager):
    """Test browser process crash (TargetClosedError) during execution."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()
    scraper.page.goto = AsyncMock(side_effect=RuntimeError("Target page, context or browser has been closed"))

    results = await scraper.scrape("https://www.youtube.com/@Crashed", max_posts=3)
    assert isinstance(results, list)
    assert results == []


@pytest.mark.asyncio
async def test_scrape_videos_setup_failure(mock_browser_manager):
    """Test unhandled failure during setup() initializes results as empty list."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = None
    scraper.browser_manager.create_context = AsyncMock(side_effect=Exception("Browser launch failed"))

    results = await scraper.scrape_videos("https://www.youtube.com/@Channel", max_videos=5)
    assert isinstance(results, list)
    assert results == []


# ============================================================================
# TIER 5: DUAL-ENGINE INTERACTION, DEDUPLICATION & PARTIAL RETURNS
# ============================================================================

@pytest.mark.asyncio
async def test_dual_engine_fallback_and_deduplication(mock_browser_manager):
    """Test Engine 1 partial extraction (1 item) triggers Engine 2 to fill quota without duplicates."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()
    scraper.page.goto = AsyncMock()

    vid1 = ScrapedVideo(title="Video 1", url="https://www.youtube.com/watch?v=v1", channel="Chan1")
    vid2 = ScrapedVideo(title="Video 2", url="https://www.youtube.com/watch?v=v2", channel="Chan1")
    vid1_duplicate = ScrapedVideo(title="Video 1 Duplicate", url="https://www.youtube.com/watch?v=v1", channel="Chan1")

    # Engine 1 returns vid1
    scraper._extract_via_yt_initial_data = AsyncMock(return_value=[vid1])

    # Engine 2 returns vid1_duplicate and vid2
    async def mock_dom_scrolling(max_videos, existing=None):
        out = list(existing or [])
        for v in [vid1_duplicate, vid2]:
            if not any(r.url == v.url for r in out):
                out.append(v)
        return out

    scraper._extract_via_dom_scrolling = AsyncMock(side_effect=mock_dom_scrolling)

    results = await scraper.scrape_videos("https://www.youtube.com/@Channel", max_videos=2)

    assert len(results) == 2
    assert results[0].url == "https://www.youtube.com/watch?v=v1"
    assert results[1].url == "https://www.youtube.com/watch?v=v2"
    scraper._extract_via_dom_scrolling.assert_called_once()


# ============================================================================
# TIER 6: SINGLE VIDEO PAGE EDGE CASES & FAILURES
# ============================================================================

@pytest.mark.asyncio
async def test_scrape_single_video_missing_all_elements(mock_browser_manager):
    """Test single video scraping returns None when title is completely missing."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()

    empty_loc = AsyncMock()
    empty_loc.count = AsyncMock(return_value=0)
    empty_loc.is_visible = AsyncMock(return_value=False)

    scraper.page.locator = MagicMock(return_value=MagicMock(first=empty_loc))

    video = await scraper._scrape_single_video("https://www.youtube.com/watch?v=empty123")
    # Title cannot be empty for ScrapedVideo dataclass, so function catches error and returns None
    assert video is None


@pytest.mark.asyncio
async def test_scrape_single_video_exception_caught(mock_browser_manager):
    """Test single video scraping catches unexpected element errors cleanly."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()
    scraper.page.locator = MagicMock(side_effect=Exception("DOM Access Denied"))

    video = await scraper._scrape_single_video("https://www.youtube.com/watch?v=error123")
    assert video is None


# ============================================================================
# TIER 7: CONSENT POPUP FAILURES & OVERLAYS
# ============================================================================

@pytest.mark.asyncio
async def test_dismiss_consent_popup_all_exceptions_caught(mock_browser_manager):
    """Test that exceptions during consent popup dismissal do not break scraping."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()
    scraper.page.locator = MagicMock(side_effect=Exception("Locator failed"))
    scraper.page.evaluate = AsyncMock(side_effect=Exception("Eval failed"))

    # Should execute without throwing
    await scraper._dismiss_consent_popup()


# ============================================================================
# TIER 8: CONTRACT CONFORMANCE & BACKWARD COMPATIBILITY
# ============================================================================

@pytest.mark.asyncio
async def test_scrape_conforms_to_base_scraper_contract(mock_browser_manager):
    """Verify ScrapedVideo instances completely satisfy BaseScraper and ScrapedContent."""
    scraper = YoutubeScraper(browser_manager=mock_browser_manager)
    scraper.page = AsyncMock()
    scraper.page.goto = AsyncMock()

    sample = ScrapedVideo(
        title="Epic Cat Story #cat #shorts",
        description="A heartwarming story of a lost cat.",
        channel="PetStories",
        url="https://www.youtube.com/watch?v=cat999",
        views="1.5M views",
        duration_str="0:45",
        timestamp="2 days ago"
    )

    scraper._extract_via_yt_initial_data = AsyncMock(return_value=[sample])

    results = await scraper.scrape("https://www.youtube.com/@PetStories", max_posts=1)
    assert len(results) == 1
    video = results[0]

    # Type assertions
    assert isinstance(video, ScrapedVideo)
    assert isinstance(video, ScrapedContent)

    # ScrapedContent properties
    assert video.text == "Epic Cat Story #cat #shorts\nA heartwarming story of a lost cat.\nViews: 1.5M views"
    assert video.source_url == "https://www.youtube.com/watch?v=cat999"
    assert video.author == "PetStories"
    assert video.platform == "youtube"
    assert video.hashtags == ["#cat", "#shorts"]
    assert video.engagement["views"] == "1.5M views"
    assert video.engagement["duration"] == "0:45"
    assert video.engagement["timestamp"] == "2 days ago"

    # Property setters work
    video.text = "New raw text"
    assert video.raw_text == "New raw text"
    video.source_url = "https://youtube.com/watch?v=updated"
    assert video.url == "https://youtube.com/watch?v=updated"
    video.author = "New Author"
    assert video.channel == "New Author"

    # to_dict roundtrip
    data = video.to_dict()
    assert data["title"] == "Epic Cat Story #cat #shorts"
    assert data["text"] == "New raw text"
    assert data["source_url"] == "https://youtube.com/watch?v=updated"

    reconstructed = ScrapedVideo.from_dict(data)
    assert reconstructed.title == video.title
    assert reconstructed.url == video.url
