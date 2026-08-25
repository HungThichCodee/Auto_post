"""
src/ai_pipeline/content_rewriter.py
Gemini 2.0 Flash AI multi-scene story rewriter and prompt engineering module.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union

import google.generativeai as genai

from src.models.pipeline_models import Scene, StoryScript
from src.memory.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.6-flash"


class ContentRewriter:
    """Uses Gemini 2.0 Flash API to rewrite scraped content into multi-scene StoryScript objects."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or DEFAULT_MODEL
        self.model = None

        if not self.api_key:
            logger.warning("No GEMINI_API_KEY provided. API calls will fail or rely on mocks.")
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini model '{self.model_name}': {e}")
                self.model = None

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
        """
        Transform raw scraped video text into a structured multi-scene StoryScript.

        Args:
            scraped_text: Raw text content from scraped video(s).
            niche: Target content niche (e.g., 'stories', 'humor', 'health').
            past_themes: List of recent themes to avoid duplicating.
            video_format: 'shorts', 'video', or 'random'.
            visual_style: '2d_animation', 'painting', or 'random'.

        Returns:
            StoryScript instance containing scenes and visual metadata.
        """
        if not scraped_text or not scraped_text.strip():
            logger.warning("Empty scraped_text provided to rewrite_story. Using fallback story.")
            return self._create_fallback_story("Nội dung trống", niche)

        if past_themes is None:
            past_themes = self.extract_past_themes_from_file()

        system_prompt = self._build_story_system_prompt(niche, video_format, visual_style)
        user_prompt = self._build_story_user_prompt(scraped_text, past_themes)
        full_prompt = f"System Instructions:\n{system_prompt}\n\nUser Request:\n{user_prompt}"

        if not self.model:
            logger.warning("Gemini model not initialized. Returning structured fallback story.")
            return self._create_fallback_story(scraped_text, niche)

        try:
            response = await self.model.generate_content_async(full_prompt)
            response_text = response.text if response else ""
            if not response_text or not response_text.strip():
                raise ValueError("Empty response text received from Gemini API.")
            return self._parse_story_response(response_text, niche)
        except Exception as e:
            logger.error(f"Error during Gemini story rewriting: {e}")
            return self._create_fallback_story(scraped_text, niche)

    def _build_story_system_prompt(self, niche: str, video_format: str, visual_style: str) -> str:
        """Construct system instructions enforcing multi-scene JSON format, art style, and character consistency."""
        if video_format == "shorts":
            format_instruction = "Structure the story strictly into 3 to 4 sequential SCENES to make a short vertical video (~45s)."
        elif video_format == "video":
            format_instruction = "Structure the story strictly into 7 to 8 sequential SCENES to make a standard horizontal video (~90s)."
        else:
            format_instruction = "Structure the story into 3 to 8 sequential SCENES."

        if visual_style == "2d_animation":
            style_instruction = "Define an overarching 'art_style' as 'high quality 2D anime animation style, Studio Ghibli style, vibrant colors'."
        elif visual_style == "painting":
            style_instruction = "Define an overarching 'art_style' as 'beautiful watercolor painting, artistic brush strokes, storybook illustration'."
        else:
            style_instruction = "Define an overarching 'art_style' (e.g., 'cute 3D Pixar animation style' or 'watercolor painting')."

        prompt = (
            "You are an elite viral YouTube creator, animator scriptwriter, and creative visual director.\n"
            "Your task is to transform source material into an original, engaging multi-scene video script.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. LANGUAGE RULES:\n"
            "   - 'title_vi', 'description_vi', 'theme', 'summary', 'themes', and all 'narration_text_vi' MUST be in VIETNAMESE.\n"
            "   - 'art_style', 'character_style', and all 'image_prompt_en' MUST be in ENGLISH.\n"
            "2. ORIGINALITY & ADAPTATION:\n"
            "   - Create an entirely NEW story/script on the same broad theme. Do NOT copy the source text verbatim.\n"
            f"   - {format_instruction}\n"
            "3. SCENE BREAKDOWN:\n"
            "   - Each scene must have a natural Vietnamese voiceover narration ('narration_text_vi') designed for spoken audio.\n"
            "   - Each scene must have a detailed English image prompt ('image_prompt_en') describing visual composition, character action, and setting.\n"
            "4. VISUAL & CHARACTER CONSISTENCY:\n"
            f"   - {style_instruction}\n"
            "   - Define a detailed 'character_style' establishing the protagonist's recurring visual traits (species, colors, clothing, eyes).\n"
            "   - Incorporate the character description and art style into every scene's 'image_prompt_en' to maintain visual continuity.\n"
            "5. OUTPUT FORMAT:\n"
            "   - Output MUST be strictly valid JSON matching the schema below. Do not output conversational text or explanation.\n\n"
            "JSON SCHEMA:\n"
            "{\n"
            '  "title_vi": "Tiêu đề video YouTube hấp dẫn (tiếng Việt)",\n'
            '  "description_vi": "Mô tả video chi tiết tiếng Việt kèm 3-5 hashtags (#thegioitihon #hoathinh3d #shorts)",\n'
            '  "theme": "Chủ đề chính",\n'
            '  "art_style": "cute 3D Pixar animation style, vibrant lighting, soft colors, high detail",\n'
            '  "character_style": "Detailed protagonist visual description for consistency",\n'
            '  "niche": "' + str(niche) + '",\n'
            '  "summary": "Tóm tắt ngắn gọn câu chuyện 1-2 câu",\n'
            '  "themes": ["từ_khóa_1", "từ_khóa_2", "từ_khóa_3"],\n'
            '  "scenes": [\n'
            "    {\n"
            '      "scene_id": 1,\n'
            '      "narration_text_vi": "Lời đọc thuyết minh cảnh 1 tiếng Việt...",\n'
            '      "image_prompt_en": "Detailed English visual prompt for scene 1..."\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )
        return prompt

    def _build_story_user_prompt(
        self,
        scraped_text: str,
        past_themes: Optional[List[str]] = None,
    ) -> str:
        """Construct user prompt containing scraped source material and anti-repetition past themes."""
        prompt_parts = []
        if past_themes:
            themes_str = ", ".join(past_themes[:20])
            prompt_parts.append(
                f"[CRITICAL ANTI-REPETITION CONSTRAINT]\n"
                f"The following themes/topics/characters have ALREADY been produced recently:\n"
                f"{themes_str}\n"
                f"You MUST create a completely DIFFERENT plot, character, and setting. Do NOT reuse these specific topics.\n"
            )
        prompt_parts.append(
            f"[SOURCE INSPIRATION MATERIAL]\n"
            f"{scraped_text}\n\n"
            f"Generate the complete structured multi-scene JSON story script now:"
        )
        return "\n".join(prompt_parts)

    def _parse_story_response(
        self,
        response_text: str,
        niche: str = "stories",
    ) -> StoryScript:
        """Parse Gemini output into a strongly-typed StoryScript dataclass with fallback handling."""
        clean_text = self._strip_code_fences(response_text)
        try:
            data = json.loads(clean_text)
            if isinstance(data, dict):
                if "niche" not in data:
                    data["niche"] = niche
                return StoryScript.from_dict(data)
        except Exception as e:
            logger.warning(f"Direct JSON parsing failed ({e}). Attempting regex extraction.")

        # Attempt regex search for outermost JSON object
        match = re.search(r"\{[\s\S]*\}", response_text)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    if "niche" not in data:
                        data["niche"] = niche
                    return StoryScript.from_dict(data)
            except Exception as e:
                logger.warning(f"Regex JSON extraction also failed: {e}")

        return self._create_fallback_story(response_text, niche)

    def _strip_code_fences(self, text: str) -> str:
        """Clean markdown code fences from JSON response."""
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()

    def _create_fallback_story(
        self,
        raw_text: str,
        niche: str = "stories",
    ) -> StoryScript:
        """Construct a high-quality 3-scene StoryScript fallback when LLM output is malformed or unavailable."""
        first_line = raw_text.strip().split("\n")[0][:60] if raw_text else "Cuộc Phiêu Lưu Kỳ Thú"
        title = f"Hành Trình Kỳ Thú: {first_line}" if first_line else "Hành Trình Kỳ Thú Tí Hon"

        scenes = [
            Scene(
                scene_id=1,
                narration_text_vi="Trong một thế giới kỳ diệu ngập tràn ánh sáng, câu chuyện phiêu lưu bắt đầu mở ra với biết bao điều kỳ thú.",
                image_prompt_en="A cute animated character starting an adventurous journey in a magical glowing forest, 3D Pixar animation style, warm morning lighting",
            ),
            Scene(
                scene_id=2,
                narration_text_vi="Những thử thách bất ngờ xuất hiện trên đường đi, đòi hỏi sự dũng cảm và lòng kiên trì vượt khó.",
                image_prompt_en="A brave cute animated character facing an exciting challenge on a mysterious path, dramatic cinematic lighting, 3D Pixar style",
            ),
            Scene(
                scene_id=3,
                narration_text_vi="Bằng sự thông minh và tình bạn gắn kết, mọi khó khăn đều được giải quyết êm đẹp trong niềm hân hoan rực rỡ.",
                image_prompt_en="A joyful animated character celebrating success under a beautiful glowing sunset, vibrant soft colors, 3D Pixar animation style",
            ),
        ]

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

    # ========================================================================
    # Backward Compatibility Methods for M1 / Legacy callers
    # ========================================================================
    async def rewrite_content(
        self,
        raw_content: str,
        niche: dict,
        knowledge_history: str = "",
        platform: str = "youtube",
    ) -> dict:
        """Legacy rewrite_content returning dictionary for backward compatibility."""
        if not self.model:
            logger.warning("Gemini model not initialized. Check API key.")
            return {"content": "", "image_prompt": "", "summary": "", "themes": []}

        system_prompt = self._build_system_prompt(niche, platform)
        user_prompt = self._build_user_prompt(raw_content, knowledge_history)
        full_prompt = f"System Instructions:\n{system_prompt}\n\nUser Prompt:\n{user_prompt}"

        try:
            response = await self.model.generate_content_async(full_prompt)
            if not response or not response.text:
                raise ValueError("Empty response from Gemini")
            return self._parse_response(response.text)
        except Exception as e:
            logger.error(f"Error during content rewriting: {e}")
            return {"content": "", "image_prompt": "", "summary": "", "themes": []}

    def _build_system_prompt(self, niche: dict, platform: str) -> str:
        niche_name = niche.get("name", "general")
        niche_desc = niche.get("description", "")
        niche_tone = niche.get("tone", "engaging")

        prompt = (
            "You are an expert content creator. Follow these instructions carefully:\n"
            "1. Output MUST be primarily in VIETNAMESE, except for the 'image_prompt' which MUST be in English.\n"
            f"2. Your niche is '{niche_name}': {niche_desc}. Match this tone: {niche_tone}.\n"
        )
        if niche_name.lower() == "stories":
            prompt += "   - Write an episode of a serialized story, make it dramatic and engaging.\n"
        elif niche_name.lower() == "humor":
            prompt += "   - Write funny, relatable content with Vietnamese humor style.\n"
        elif niche_name.lower() == "health":
            prompt += "   - Write informative health content, focusing on vegetables or natural remedies.\n"

        if platform.lower() == "facebook":
            prompt += "3. For Facebook: Write a longer, engaging post. Use paragraphs and emojis.\n"
        elif platform.lower() == "tiktok":
            prompt += "3. For TikTok: Write a shorter, punchy script/caption with trending hashtags.\n"
        elif platform.lower() == "youtube":
            prompt += "3. For YouTube: Write in a community post style, engaging with subscribers.\n"
        else:
            prompt += "3. Adapt the length and format appropriately.\n"

        prompt += (
            "4. Be original and provide a unique perspective. Do not just copy the source.\n"
            "5. Always generate a DETAILED English image prompt (at least 50 words) suitable for AI image generation.\n"
            "6. Output must be in JSON format with the following keys:\n"
            "   - 'content': The rewritten post text (Vietnamese)\n"
            "   - 'image_prompt': Detailed English image prompt\n"
            "   - 'summary': Brief summary of the post for a knowledge base (Vietnamese)\n"
            "   - 'themes': List of key themes used (strings in Vietnamese)\n"
        )
        return prompt

    def _build_user_prompt(self, raw_content: str, knowledge_history: str) -> str:
        prompt = ""
        if knowledge_history:
            prompt += (
                "Previous Knowledge/History (Avoid repeating these ideas/themes exactly):\n"
                f"{knowledge_history}\n\n"
            )
        prompt += (
            "Source Material/Inspiration:\n"
            f"{raw_content}\n\n"
            "Based on the system instructions and the source material, generate the structured JSON output."
        )
        return prompt

    def _parse_response(self, response_text: str) -> dict:
        try:
            clean_text = self._strip_code_fences(response_text)
            data = json.loads(clean_text)
            return {
                "content": data.get("content", ""),
                "image_prompt": data.get("image_prompt", ""),
                "summary": data.get("summary", ""),
                "themes": data.get("themes", []),
            }
        except json.JSONDecodeError:
            logger.warning("Failed to parse Gemini response as JSON. Attempting manual extraction.")
            return {
                "content": response_text,
                "image_prompt": "A detailed scene capturing the essence of the content, cinematic lighting, 8k resolution, highly detailed",
                "summary": "Summary parsing failed.",
                "themes": [],
            }
