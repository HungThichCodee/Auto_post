import httpx
import logging
import os
import hashlib
import asyncio
from pathlib import Path
from urllib.parse import quote
from datetime import datetime
from typing import Optional
from PIL import Image
import io

logger = logging.getLogger(__name__)

class ImageGenerator:
    """Generates images using Pollinations.ai free API."""
    
    BASE_URL = "https://image.pollinations.ai/prompt/"
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_image(self, prompt: str, 
                              width: int = 1024, 
                              height: int = 1024,
                              seed: Optional[int] = None,
                              model: str = "flux") -> str:
        """
        Generate an image from a text prompt using Pollinations.ai.
        
        Args:
            prompt: English image description
            width: Image width (default 1024)
            height: Image height (default 1024) 
            seed: Random seed for reproducibility
            model: Model to use (default 'flux')
        
        Returns:
            Path to the downloaded image file
        """
        encoded_prompt = quote(prompt)
        url = f"{self.BASE_URL}{encoded_prompt}?width={width}&height={height}&model={model}&nologo=true&enhance=true"
        if seed is not None:
            url += f"&seed={seed}"
            
        filename = self._generate_filename(prompt)
        filepath = self.output_dir / filename
        
        max_retries = 3
        timeout = httpx.Timeout(120.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"Attempt {attempt}/{max_retries}: Generating image for prompt: {prompt[:50]}...")
                    response = await client.get(url)
                    response.raise_for_status()
                    
                    image_data = response.content
                    
                    if len(image_data) < 1024:
                        logger.warning("Downloaded image is too small (< 1KB). Retrying...")
                        continue
                        
                    try:
                        # Verify it's a valid image
                        img = Image.open(io.BytesIO(image_data))
                        img.verify()
                    except Exception as e:
                        logger.warning(f"Downloaded file is not a valid image: {e}. Retrying...")
                        continue
                        
                    with open(filepath, "wb") as f:
                        f.write(image_data)
                        
                    logger.info(f"Image successfully generated and saved to {filepath}")
                    return str(filepath)
                    
                except httpx.HTTPError as e:
                    logger.error(f"HTTP Error during image generation: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error during image generation: {e}")
                
                if attempt < max_retries:
                    await asyncio.sleep(5)  # Wait before retrying
                    
        raise Exception(f"Failed to generate image after {max_retries} attempts.")
    
    def _generate_filename(self, prompt: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        return f"{timestamp}_{prompt_hash}.png"
