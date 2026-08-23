"""
src/ai_pipeline/image_generator.py
Pollinations.ai batch scene image generation with visual consistency, aspect ratio adaptation, and resilient retries.
"""

import asyncio
import hashlib
import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import quote

import httpx
from PIL import Image

from src.models.pipeline_models import Scene

logger = logging.getLogger(__name__)

ASPECT_RATIO_MAP: Dict[str, Tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1024, 1024),
    "4:5": (1080, 1350),
}


def get_dimensions_for_aspect_ratio(aspect_ratio: str, high_res: bool = True) -> Tuple[int, int]:
    """Resolve aspect ratio string to (width, height) pixel dimensions."""
    if aspect_ratio in ASPECT_RATIO_MAP:
        w, h = ASPECT_RATIO_MAP[aspect_ratio]
        return (w, h) if high_res else (int(w * 0.666), int(h * 0.666))
    if ":" in aspect_ratio:
        try:
            rw, rh = map(float, aspect_ratio.split(":"))
            if rw > 0 and rh > 0:
                if rw < rh:  # Vertical
                    return (1080, int(1080 * (rh / rw)))
                else:  # Horizontal
                    return (int(1080 * (rw / rh)), 1080)
        except Exception:
            pass
    return (1080, 1920)


def compose_scene_prompt(
    scene_prompt: str,
    art_style: str = "",
    character_style: str = "",
    quality_suffix: str = "highly detailed, 8k resolution, cinematic lighting",
) -> str:
    """Compose a full scene prompt enforcing character and art style consistency."""
    parts = []
    if character_style and character_style.strip():
        parts.append(character_style.strip())
    cleaned_prompt = scene_prompt.strip()
    parts.append(cleaned_prompt)
    if art_style and art_style.strip():
        art_clean = art_style.strip()
        if art_clean.lower() not in cleaned_prompt.lower():
            parts.append(f"in {art_clean}")
    if quality_suffix:
        parts.append(quality_suffix)
    return ", ".join(parts)


class ImageGenerator:
    """Generates images using Pollinations.ai free API with style consistency and robust retries."""

    BASE_URL = "https://image.pollinations.ai/prompt/"

    def __init__(
        self,
        output_dir: Union[str, Path] = "output",
        default_model: str = "flux",
        fallback_model: str = "turbo",
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_model = default_model
        self.fallback_model = fallback_model
        self.timeout = timeout
        self.max_retries = max_retries

    def _generate_filename(self, prompt: str, prefix: str = "") -> str:
        """Generate a unique deterministic filename for a prompt."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prompt_hash = hashlib.md5(prompt.encode("utf-8")).hexdigest()[:8]
        if prefix:
            return f"{prefix}_{timestamp}_{prompt_hash}.png"
        return f"{timestamp}_{prompt_hash}.png"

    def _verify_image_data(self, image_data: bytes) -> bool:
        """Verify binary data represents a valid, uncorrupted image."""
        if len(image_data) < 1024:
            return False
        try:
            img = Image.open(io.BytesIO(image_data))
            img.verify()
            img_load = Image.open(io.BytesIO(image_data))
            img_load.load()
            return img_load.size[0] > 0 and img_load.size[1] > 0
        except Exception:
            return False

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        model: Optional[str] = None,
        custom_filepath: Optional[Union[str, Path]] = None,
    ) -> str:
        """Generate a single image from a prompt with retry and model fallback."""
        requested_model = model or self.default_model
        encoded_prompt = quote(prompt.strip(), safe="")

        filepath = (
            Path(custom_filepath)
            if custom_filepath
            else self.output_dir / self._generate_filename(prompt)
        )
        filepath.parent.mkdir(parents=True, exist_ok=True)

        current_seed = seed
        client_timeout = httpx.Timeout(self.timeout, connect=10.0, read=self.timeout)

        async with httpx.AsyncClient(timeout=client_timeout, follow_redirects=True) as client:
            for attempt in range(1, self.max_retries + 1):
                # On final attempt, fallback to fallback_model if requested_model was default
                if attempt == self.max_retries and requested_model == self.default_model:
                    current_model = self.fallback_model
                else:
                    current_model = requested_model

                if current_seed is None and attempt > 1:
                    current_seed = int(hashlib.md5(f"{prompt}_{attempt}".encode()).hexdigest(), 16) % (2**31 - 1)

                url = (
                    f"{self.BASE_URL}{encoded_prompt}"
                    f"?width={width}&height={height}&model={current_model}&nologo=true&enhance=false"
                )
                if current_seed is not None:
                    url += f"&seed={current_seed}"

                try:
                    logger.info(f"Attempt {attempt}/{self.max_retries}: Generating image (model={current_model})...")
                    response = await client.get(url)
                    response.raise_for_status()

                    image_data = response.content
                    if not self._verify_image_data(image_data):
                        logger.warning(
                            f"Attempt {attempt}: Corrupt or undersized payload ({len(image_data)} bytes). Retrying..."
                        )
                        if attempt < self.max_retries:
                            await asyncio.sleep(2.0 ** attempt)
                        continue

                    temp_file = filepath.with_suffix(".tmp")
                    with open(temp_file, "wb") as f:
                        f.write(image_data)
                    if temp_file.exists():
                        if filepath.exists():
                            filepath.unlink()
                        temp_file.rename(filepath)

                    logger.info(f"Image successfully generated: {filepath}")
                    return str(filepath)

                except httpx.HTTPError as e:
                    logger.error(f"Attempt {attempt}: HTTP Error ({e})")
                except Exception as e:
                    logger.error(f"Attempt {attempt}: Unexpected error ({e})")

                if attempt < self.max_retries:
                    await asyncio.sleep(2.0 ** attempt)

        raise Exception(f"Failed to generate image after {self.max_retries} attempts.")

    async def generate_single_image(
        self,
        prompt: str,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
        max_retries: int = 3,
    ) -> bool:
        """Helper to generate a single image directly to a specified destination."""
        try:
            await self.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                custom_filepath=output_path,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to generate single image to {output_path}: {e}")
            return False

    async def generate_scene_images(
        self,
        scenes: List[Scene],
        art_style: str = "3D Pixar animation",
        character_style: str = "",
        aspect_ratio: str = "9:16",
        output_dir: Optional[str] = None,
    ) -> List[Scene]:
        """Batch generate illustration images for all scenes with style consistency."""
        target_dir = Path(output_dir) if output_dir else self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        width, height = get_dimensions_for_aspect_ratio(aspect_ratio)

        for scene in scenes:
            if scene.image_path and Path(scene.image_path).exists() and Path(scene.image_path).stat().st_size > 1024:
                logger.info(f"Scene {scene.scene_id}: Image already exists at {scene.image_path}. Skipping.")
                if scene.status == "pending":
                    scene.status = "image_ready"
                elif scene.status == "audio_ready":
                    scene.status = "completed"
                continue

            composed_prompt = compose_scene_prompt(
                scene_prompt=scene.image_prompt_en,
                art_style=art_style,
                character_style=character_style,
            )

            filename = f"scene_{scene.scene_id:02d}_{hashlib.md5(composed_prompt.encode()).hexdigest()[:6]}.png"
            dest_path = target_dir / filename

            try:
                img_path = await self.generate_image(
                    prompt=composed_prompt,
                    width=width,
                    height=height,
                    custom_filepath=dest_path,
                )
                scene.image_path = img_path
                scene.status = "completed" if scene.audio_path else "image_ready"
            except Exception as e:
                logger.error(f"Failed generating image for Scene {scene.scene_id}: {e}")
                scene.status = "failed"
                raise

        return scenes
