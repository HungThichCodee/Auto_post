"""
src/ai_pipeline/content_rewriter.py
Gemini 2.0 Flash AI multi-scene story rewriter and prompt engineering module.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union

from google import genai

from src.models.pipeline_models import Scene, StoryScript
from src.memory.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"


class ContentRewriter:
    """Uses Gemini 2.0 Flash API to rewrite scraped content into multi-scene StoryScript objects."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or DEFAULT_MODEL
        self.client = None

        if not self.api_key:
            logger.warning("No GEMINI_API_KEY provided. API calls will fail or rely on mocks.")
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client: {e}")
                self.client = None

    @classmethod
    def extract_past_themes_from_file(
        cls,
        knowledge_base_path: str = "knowledge_base.md",
    ) -> List[str]:
        """Extract recent themes from knowledge_base.md using KnowledgeBase helper."""
        try:
            if os.path.exists(knowledge_base_path):
                kb = KnowledgeBase(filepath=knowledge_base_path)
                return kb.get_recent_themes(n=20)
        except Exception as e:
            logger.warning(f"Could not extract past themes from {knowledge_base_path}: {e}")
        return []

    async def rewrite_story(
        self,
        scraped_text: str,
        niche: str = "stories",
        past_themes: Optional[List[str]] = None,
        video_format: str = "random",
        visual_style: str = "random",
    ) -> StoryScript:
        if not scraped_text or not scraped_text.strip():
            logger.warning("Empty scraped_text provided to rewrite_story. Using fallback story.")
            return self._create_fallback_story("", niche)

        if not self.client:
            logger.warning("Gemini Client not initialized. Using fallback story.")
            return self._create_fallback_story(scraped_text, niche)

        system_prompt = self._build_story_system_prompt(niche, video_format, visual_style)
        
        user_prompt = "Source Material:\n" + scraped_text
        if past_themes:
            user_prompt += "\n\nPast Themes to avoid heavily repeating: " + ", ".join(past_themes)
            
        full_prompt = f"System Instructions:\n{system_prompt}\n\nUser Request:\n{user_prompt}"

        logger.info(f"Generating story with Gemini model '{self.model_name}' (Format: {video_format})...")

        try:
            # Using google.genai async client
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
            )
            
            if not response or not response.text:
                raise ValueError("Empty response from Gemini")
                
            response_text = response.text
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            return self._create_fallback_story(scraped_text, niche)

        # Attempt to parse
        try:
            clean_text = self._strip_code_fences(response_text)
            data = json.loads(clean_text)
            data["video_format"] = video_format
            return StoryScript.from_dict(data)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse main JSON response: {e}. Trying regex extraction...")
            try:
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    clean_text = json_match.group(1).strip()
                    data = json.loads(clean_text)
                    data["video_format"] = video_format
                    return StoryScript.from_dict(data)
            except Exception as e:
                logger.warning(f"Regex JSON extraction also failed: {e}")

        return self._create_fallback_story(response_text, niche)

    def _strip_code_fences(self, text: str) -> str:
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()

    def _build_story_system_prompt(self, niche: str, video_format: str, visual_style: str) -> str:
        return f"""You are the Master AI Executive Director and Cinematographer for automated video storytelling.
Your mission is to transform raw narrative concepts into a highly cinematic, multi-scene video production script.

CRITICAL CINEMATOGRAPHY & DURATION CONSTRAINTS:
1. SCENE CHUNKING (<= 10.0 SECONDS PER SCENE):
   - Every scene's `narration_text_vi` MUST be strictly between 10 and 18 Vietnamese words (1 to 2 balanced sentences).
   - Under NO circumstance create sub-10-word beats or exceed 19 words (enforces expected speech 4.0s - 8.5s).
   - For Shorts (9:16): Create 5-7 scenes (Total ~70-100 words, ~35-50 seconds runtime).
   - For Long Video (16:9): Create 12-16 scenes (Total ~180-220 words, ~75-95 seconds runtime).

2. CAMERA MOTION & TEMPORAL PROMPTS:
   - For each scene, generate `video_prompt_en` describing dynamic motion, environmental physics (wind, fog, embers), and camera movement.
   - Choose `camera_movement` from: ['slow_dolly_in', 'lateral_tracking', 'low_angle_tilt_up', 'overhead_crane', 'orbit_90deg', 'organic_handheld'].
   - Ensure `image_prompt_en` provides a high-resolution keyframe description as a fallback anchor.

3. HYBRID QUOTA ALLOCATION:
   - Mark `is_hero_scene: true` for 3 to 4 major narrative beats (Scene 1 Hook, Scene 7 Turning Point, Scene 14 Climax).
   - Mark `is_hero_scene: false` for standard exposition and transition scenes.

4. VISUAL CONTINUITY & CHARACTER ANCHORS:
   - Maintain identical character style, clothing, and physical traits across ALL scenes.
   - Maintain uniform atmospheric lighting, color palette, and art style.

OUTPUT FORMAT: Strict valid JSON only (no markdown, no preamble).
Schema:
{{
  "title_vi": "Tiêu đề hấp dẫn",
  "description_vi": "Mô tả đầy đủ kèm #hashtag",
  "theme": "Chủ đề câu chuyện",
  "art_style": "3D Pixar animation style, vivid cinematic lighting",
  "character_style": "An 8-year-old Vietnamese boy with red hoodie and brass glasses",
  "scenes": [
    {{
      "scene_id": 1,
      "narration_text_vi": "Lời thuyết minh ngắn gọn từ 10 đến 18 từ.",
      "camera_movement": "slow_dolly_in",
      "is_hero_scene": true,
      "video_prompt_en": "Cinematic slow dolly-in shot. Character description, active motion in environment, volumetric lighting, 24fps.",
      "image_prompt_en": "Detailed static illustration prompt with character and environment for high-res fallback."
    }}
  ]
}}"""

    def _create_fallback_story(
        self,
        raw_text: str,
        niche: str = "stories",
    ) -> StoryScript:
        first_line = raw_text.strip().split("\n")[0][:60] if raw_text else "Cuoc Phieu Luu Ky Thu"
        title = f"Hanh Trinh Ky Thu: {first_line}" if first_line else "Hanh Trinh Ky Thu Ti Hon"

        scenes = [
            Scene(
                scene_id=1,
                narration_text_vi="Trong một thế giới kỳ diệu ngập tràn ánh sáng, câu chuyện bắt đầu với muôn vàn bí ẩn.",
                video_prompt_en="Cinematic slow dolly-in. A cute animated character starting an adventurous journey in a magical glowing forest.",
                image_prompt_en="A cute animated character starting an adventurous journey in a magical glowing forest, 3D Pixar animation style, warm morning lighting",
            ),
            Scene(
                scene_id=2,
                narration_text_vi="Những thử thách bất ngờ xuất hiện, đòi hỏi sự dũng cảm và lòng kiên trì vượt khó.",
                video_prompt_en="Lateral tracking. A brave cute animated character facing an exciting challenge on a mysterious path.",
                image_prompt_en="A brave cute animated character facing an exciting challenge on a mysterious path, dramatic cinematic lighting, 3D Pixar style",
            ),
            Scene(
                scene_id=3,
                narration_text_vi="Bằng trí thông minh và tình bạn gắn kết, mọi khó khăn đều được giải quyết êm đẹp.",
                video_prompt_en="Orbit 90deg. A joyful animated character celebrating success under a beautiful glowing sunset.",
                image_prompt_en="A joyful animated character celebrating success under a beautiful glowing sunset, vibrant soft colors, 3D Pixar animation style",
            ),
        ]
        
        for s in scenes:
            s.is_hero_scene = True

        return StoryScript(
            title_vi=title,
            description_vi=f"{title} - Video hoạt hình 3D kỳ thú dành cho bạn. #hoathinh3d #thegioitihon #shorts",
            theme=niche.capitalize(),
            art_style="cute 3D Pixar animation style, vibrant lighting, soft colors, high detail",
            character_style="Cute animated protagonist with expressive curious eyes and joyful expression",
            scenes=scenes,
            niche=niche,
            summary="Câu chuyện hoạt hình 3D phiêu lưu vượt khó đầy cảm hứng.",
            themes=["hoạt hình 3d", "phiêu lưu", "dũng cảm", niche],
        )

    async def rewrite_content(self, *args, **kwargs) -> dict:
        """Legacy rewrite_content"""
        return {"content": "", "image_prompt": "", "summary": "", "themes": []}
