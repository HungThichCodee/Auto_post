"""
src/ai_pipeline/video_clip_generator.py
High-performance asynchronous video clip synthesis engine supporting Hugging Face ZeroGPU Spaces,
Pollinations.ai Video REST endpoints, local quantized models, and resilient 2.5D fallbacks.
"""

import asyncio
import logging
import os
import shutil
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx

from src.models.pipeline_models import Scene
from src.ai_pipeline.image_generator import ImageGenerator, compose_scene_prompt

logger = logging.getLogger(__name__)


class VideoClipGenerator:
    """
    Synthesizes short dynamic video clips (<= 10s) for scenes using a 3-Tier
    resilient fallback architecture with multi-space pool and hybrid quota defense.
    """

    ZEROGPU_SPACES = [
        {"space_id": "Wan-AI/Wan2.1-T2V-14B", "api_name": "/generate_video", "timeout": 45.0},
        {"space_id": "Lightricks/LTX-Video", "api_name": "/predict", "timeout": 45.0},
        {"space_id": "THUDM/CogVideoX-5B-Space", "api_name": "/generate", "timeout": 45.0},
    ]

    def __init__(
        self,
        output_dir: Union[str, Path] = "output/video_clips",
        hf_token: Optional[str] = None,
        image_generator: Optional[ImageGenerator] = None,
        concurrency_limit: int = 2,
        max_cloud_video_scenes: int = 4,  # Hybrid Quota Defense ceiling
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self.image_generator = image_generator or ImageGenerator()
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.max_cloud_video_scenes = max_cloud_video_scenes
        self._cloud_video_count = 0
        logger.info(f"VideoClipGenerator initialized (Output: {self.output_dir}, Concurrency: {concurrency_limit})")

    async def generate_scene_clips(
        self,
        scenes: List[Scene],
        aspect_ratio: str = "9:16",
        art_style: str = "3D Pixar animation",
    ) -> List[Scene]:
        """Batch generates video clips for all scenes concurrently."""
        tasks = [
            self.generate_single_clip(
                scene,
                aspect_ratio=aspect_ratio,
                art_style=art_style,
                is_hero_scene=getattr(scene, "is_hero_scene", (scene.scene_id in {1, len(scenes)//2, len(scenes)}))
            )
            for scene in scenes
        ]
        return await asyncio.gather(*tasks)

    async def generate_single_clip(
        self,
        scene: Scene,
        aspect_ratio: str = "9:16",
        art_style: str = "3D Pixar animation",
        is_hero_scene: bool = False,
    ) -> Scene:
        """Synthesizes a video clip for a single scene with 3-Tier fallback and quota defense."""
        async with self.semaphore:
            out_filename = f"scene_{scene.scene_id:03d}_clip.mp4"
            out_path = self.output_dir / out_filename

            full_prompt = f"{scene.video_prompt_en or scene.image_prompt_en}, {art_style}, cinematic lighting, high quality, 24fps"

            # -------------------------------------------------------------
            # Tier 1: Cloud ZeroGPU Spaces & Pollinations REST (Hero Scenes)
            # -------------------------------------------------------------
            if is_hero_scene and self._cloud_video_count < self.max_cloud_video_scenes:
                # Attempt 1a: ZeroGPU Spaces
                success = await self._try_hf_zerogpu(full_prompt, aspect_ratio, str(out_path))
                if success:
                    self._cloud_video_count += 1
                    scene.video_path = str(out_path)
                    scene.generation_source = "hf_zerogpu"
                    scene.status = "video_ready"
                    logger.info(f"Scene {scene.scene_id}: Generated via Hugging Face ZeroGPU Space.")
                    return scene

                # Attempt 1b: Pollinations Video REST API
                success = await self._try_pollinations_video(full_prompt, aspect_ratio, str(out_path))
                if success:
                    self._cloud_video_count += 1
                    scene.video_path = str(out_path)
                    scene.generation_source = "pollinations_video"
                    scene.status = "video_ready"
                    logger.info(f"Scene {scene.scene_id}: Generated via Pollinations Video REST API.")
                    return scene

            # -------------------------------------------------------------
            # Tier 2: Local Quantized OSS Model (if available)
            # -------------------------------------------------------------
            success = await self._try_local_oss_model(full_prompt, aspect_ratio, str(out_path))
            if success:
                scene.video_path = str(out_path)
                scene.generation_source = "local_oss"
                scene.status = "video_ready"
                logger.info(f"Scene {scene.scene_id}: Generated via Local Quantized Model.")
                return scene

            # -------------------------------------------------------------
            # Tier 3: 100% Bulletproof High-Res Image + 2.5D Fallback
            # -------------------------------------------------------------
            logger.info(f"Scene {scene.scene_id}: Generating Tier 3 High-Res Image + 2.5D Animation...")
            composed_img_prompt = compose_scene_prompt(
                scene_prompt=scene.image_prompt_en,
                art_style=art_style,
                character_style=""
            )
            dest_img_path = self.output_dir / f"scene_{scene.scene_id:03d}_image.png"

            try:
                img_path = await self.image_generator.generate_image(
                    prompt=composed_img_prompt,
                    custom_filepath=dest_img_path
                )
            except Exception as e:
                logger.warning(f"Tier 3 image generation failed: {e}. Using offline procedural canvas.")
                img_path = self._generate_offline_canvas(dest_img_path, scene.narration_text_vi)

            scene.image_path = str(img_path)
            scene.generation_source = "ken_burns"
            scene.status = "image_ready"
            return scene

    async def _try_hf_zerogpu(self, prompt: str, aspect_ratio: str, target_path: str) -> bool:
        """Invokes Hugging Face ZeroGPU Spaces via gradio_client with multi-space failover."""
        if not self.hf_token:
            return False
            
        for space in self.ZEROGPU_SPACES:
            space_id = space["space_id"]
            api_name = space["api_name"]
            timeout_sec = space["timeout"]
            try:
                logger.info(f"Attempting ZeroGPU generation on space '{space_id}' (Timeout: {timeout_sec}s)...")

                def _call_gradio():
                    from gradio_client import Client
                    client = Client(space_id, hf_token=self.hf_token)
                    return client.predict(prompt=prompt, api_name=api_name)

                result = await asyncio.wait_for(asyncio.to_thread(_call_gradio), timeout=timeout_sec)
                
                # Robust return type unpacking: handle str, tuple, list, or dict
                if isinstance(result, str):
                    temp_video = result
                elif isinstance(result, (list, tuple)) and len(result) > 0:
                    temp_video = result[0]
                elif isinstance(result, dict):
                    temp_video = result.get("video") or result.get("output")
                else:
                    temp_video = None

                if temp_video and os.path.exists(temp_video):
                    shutil.move(temp_video, target_path)
                    return True
            except Exception as e:
                logger.warning(f"ZeroGPU Space '{space_id}' failed: {e}. Trying next...")
                continue
        return False

    async def _try_pollinations_video(self, prompt: str, aspect_ratio: str, target_path: str) -> bool:
        """Invokes Pollinations.ai Video REST API with MP4 Magic Byte validation."""
        w, h = (720, 1280) if aspect_ratio == "9:16" else (1280, 720)
        encoded_prompt = urllib.parse.quote(prompt[:300])
        url = f"https://gen.pollinations.ai/video/{encoded_prompt}?width={w}&height={h}&model=seedance"

        try:
            async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
                resp = await client.get(url)
                # Ensure HTTP 200, size > 50KB, and valid MP4 binary header (ftyp or moov box)
                if resp.status_code == 200 and len(resp.content) > 50000:
                    if b"ftyp" in resp.content[:16] or b"moov" in resp.content[:128]:
                        with open(target_path, "wb") as f:
                            f.write(resp.content)
                        return True
                    else:
                        logger.warning("Pollinations returned non-MP4 binary payload (HTML/JSON error).")
        except Exception as e:
            logger.warning(f"Pollinations Video API call failed: {e}")
        return False

    async def _try_local_oss_model(self, prompt: str, aspect_ratio: str, target_path: str) -> bool:
        """Hook for local ComfyUI headless or Diffusers pipeline."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get("http://127.0.0.1:8188/system_stats")
                if resp.status_code == 200:
                    logger.info("Local ComfyUI detected. Dispatching local generation workflow...")
                    return False  # Stub for optional local server
        except Exception:
            pass
        return False

    def _generate_offline_canvas(self, target_path: Path, text: str) -> str:
        """Tier 3.5 Offline Procedural Canvas Generator (Guarantees zero-fail execution)."""
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (1080, 1920), color=(20, 24, 36))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(50, 50), (1030, 1870)], outline=(60, 80, 120), width=4)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(target_path, "PNG")
        return str(target_path)
