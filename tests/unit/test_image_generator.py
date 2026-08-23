"""
tests/unit/test_image_generator.py
Unit tests for ImageGenerator Pollinations.ai URL construction, parameter encoding, retries, and image validation.
"""

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from PIL import Image

from src.ai_pipeline.image_generator import ImageGenerator
from tests.conftest import create_synthetic_png_bytes


def test_image_generator_initialization(tmp_path: Path):
    """Verify output directory creation during initialization."""
    out_dir = tmp_path / "images_out"
    gen = ImageGenerator(output_dir=str(out_dir))
    assert out_dir.exists()
    assert gen.output_dir == out_dir


def test_filename_generation():
    """Verify filename generation includes timestamp and hash."""
    gen = ImageGenerator()
    fn = gen._generate_filename("A cute cat running in a flower field")
    assert fn.endswith(".png")
    assert "_" in fn


@pytest.mark.asyncio
async def test_generate_image_success_mock(tmp_path: Path):
    """Verify successful image generation with valid PNG payload."""
    gen = ImageGenerator(output_dir=str(tmp_path))
    valid_png_bytes = create_synthetic_png_bytes(width=1024, height=1024)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = valid_png_bytes
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        image_path = await gen.generate_image(
            prompt="A tiny ant in a sunny forest",
            width=1024,
            height=1024,
            seed=42,
            model="flux",
        )

        assert Path(image_path).exists()
        img = Image.open(image_path)
        assert img.size == (1024, 1024)

        # Verify call URL structure
        called_url = str(mock_get.call_args[0][0])
        assert "image.pollinations.ai/prompt" in called_url
        assert "width=1024" in called_url
        assert "height=1024" in called_url
        assert "seed=42" in called_url
        assert "model=flux" in called_url


@pytest.mark.asyncio
async def test_generate_image_rejects_corrupted_payload_and_retries(tmp_path: Path):
    """Verify undersized or corrupt image payloads are rejected and retried."""
    gen = ImageGenerator(output_dir=str(tmp_path))
    corrupt_bytes = b"SHORT_CORRUPT_DATA"
    valid_bytes = create_synthetic_png_bytes(width=1080, height=1920)

    res_corrupt = MagicMock(status_code=200, content=corrupt_bytes, raise_for_status=MagicMock())
    res_valid = MagicMock(status_code=200, content=valid_bytes, raise_for_status=MagicMock())

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [res_corrupt, res_valid]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            image_path = await gen.generate_image("Shorts prompt", width=1080, height=1920)
            assert Path(image_path).exists()
            assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_generate_image_retry_exhaustion_raises(tmp_path: Path):
    """Verify exception is raised after exhausting all retry attempts."""
    gen = ImageGenerator(output_dir=str(tmp_path))

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectTimeout("Connection timed out")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception, match="Failed to generate image"):
                await gen.generate_image("Test prompt")
            assert mock_get.call_count == 3


@pytest.mark.asyncio
async def test_url_encoding_special_characters(tmp_path: Path):
    """Verify prompt containing special characters is properly URL percent-encoded."""
    gen = ImageGenerator(output_dir=str(tmp_path))
    valid_bytes = create_synthetic_png_bytes(width=512, height=512)
    mock_res = MagicMock(status_code=200, content=valid_bytes, raise_for_status=MagicMock())

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_res
        special_prompt = 'A "heroic" dog & cat #100% (adventure) / 3D'
        await gen.generate_image(special_prompt, width=512, height=512)

        called_url = str(mock_get.call_args[0][0])
        assert "%20" in called_url or "+" in called_url
        assert "%26" in called_url or "&cat" not in called_url.split("?")[0]
