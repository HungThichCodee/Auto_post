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
        format_mapping = {
            "shorts": "9:16",
            "video": "16:9",
        }
        vf = format_mapping.get(video_format, "9:16")

        style_mapping = {
            "2d_animation": "high quality 2D anime animation style, Studio Ghibli style, vibrant colors",
            "painting": "beautiful watercolor painting, artistic brush strokes, storybook illustration"
        }
        vs = style_mapping.get(visual_style, "cute 3D Pixar animation style, vibrant lighting, soft colors, high detail")

        prompt = (
            "You are an expert AI visual director and image-prompt engineer for a YouTube automated video system.\n\n"
            "Your task is to transform the provided source content into a completely original short story and create high-quality image generation prompts for every scene.\n\n"
            "IMPORTANT GOALS:\n"
            "- Preserve the core idea of the source, but NEVER copy sentences, structure, or wording.\n"
            "- Create a coherent, engaging and original story.\n"
            "- Every scene must visually connect to the previous and next scene.\n"
            "- Prioritize visual clarity, sharp subjects, strong composition and readable details.\n"
            "- The generated images will be used as the ONLY visual source for a video.\n"
            "- Do NOT request image upscaling, image editing, video generation, or external AI tools.\n"
            "- Do NOT put text, subtitles, logos, watermarks, UI elements, or written words inside generated images.\n\n"
            "LANGUAGE RULES:\n"
            "- 'title_vi', 'description_vi', 'theme', 'summary', 'themes', and all 'narration_text_vi' MUST be in VIETNAMESE.\n"
            "- 'art_style', 'character_style', and all 'image_prompt_en' MUST be in ENGLISH.\n\n"
            f"VIDEO FORMAT:\n"
            f"The video format is: {vf}\n"
            "If VIDEO_FORMAT = \"16:9\":\n"
            "- Compose for landscape YouTube video.\n"
            "- Use a wide cinematic composition.\n"
            "- Resolution target: 1920x1080.\n"
            "- Keep the main subject clearly visible and away from extreme edges.\n\n"
            "If VIDEO_FORMAT = \"9:16\":\n"
            "- Compose for YouTube Shorts.\n"
            "- Use a vertical cinematic composition.\n"
            "- Resolution target: 1080x1920.\n"
            "- Keep the main subject inside the central safe area.\n"
            "- Avoid placing important faces, hands, objects or story elements near the top/bottom edges.\n\n"
            f"ART STYLE:\n"
            f"The selected visual style is: {vs}\n\n"
            "VISUAL QUALITY REQUIREMENTS FOR EVERY IMAGE PROMPT:\n"
            "- highly detailed\n"
            "- crisp and clean details\n"
            "- sharp main subject\n"
            "- clear silhouette\n"
            "- well-defined facial features when characters are present\n"
            "- clean edges\n"
            "- coherent lighting\n"
            "- natural depth\n"
            "- detailed foreground, midground and background\n"
            "- cinematic composition\n"
            "- strong visual hierarchy\n"
            "- balanced contrast\n"
            "- consistent color palette\n"
            "- professional illustration quality\n"
            "- visually readable at both laptop and smartphone screen sizes\n\n"
            "VISUAL SHARPNESS PRIORITY:\n"
            "Prioritize large, recognizable visual details over excessive micro-details.\n"
            "The final image will be rendered at 1920x1080 or 1080x1920 and compressed into an online video. Therefore:\n"
            "- Make the main subject occupy approximately 30–60% of the frame when appropriate.\n"
            "- Keep faces clearly visible.\n"
            "- Keep important objects sufficiently large.\n"
            "- Use clean shapes and strong silhouettes.\n"
            "- Avoid extremely fine patterns.\n"
            "- Avoid dense crowds unless essential to the story.\n"
            "- Avoid excessive small objects in the background.\n"
            "- Avoid thin lines that may disappear after video compression.\n"
            "- Avoid excessive fog, haze, film grain, noise and artificial blur.\n"
            "- Use moderate depth of field.\n"
            "- Keep the main subject sharply focused.\n"
            "- Use clear separation between foreground, subject and background.\n"
            "- Make important visual information readable even on a small smartphone screen.\n\n"
            "COMPOSITION RULES:\n"
            "- Each scene must have one clear visual focal point.\n"
            "- Do not overcrowd the image.\n"
            "- Avoid excessive tiny objects.\n"
            "- Keep important details large enough to remain recognizable after video compression.\n"
            "- Use foreground, midground and background to create depth.\n"
            "- Use cinematic perspective and controlled camera framing.\n"
            "- Leave enough visual space for subtle Ken Burns zoom/pan effects.\n"
            "- Do not rely on extremely close crops.\n"
            "- Avoid important objects touching the frame edges.\n\n"
            "CHARACTER CONSISTENCY:\n"
            "If the same character appears in multiple scenes:\n"
            "- Keep the same age, face, hairstyle, clothing, body proportions and visual identity.\n"
            "- Repeat the character description consistently in every relevant image prompt.\n"
            "- Do not randomly change character appearance between scenes.\n\n"
            "IMAGE PROMPT STRUCTURE:\n"
            "For every scene, write ONE detailed English prompt following this order:\n"
            "1. Main subject and action\n"
            "2. Character appearance and consistency\n"
            "3. Environment\n"
            "4. Foreground / midground / background\n"
            "5. Camera angle and composition\n"
            "6. Lighting\n"
            "7. Color palette\n"
            "8. Art style\n"
            "9. Texture and fine details\n"
            "10. Image quality requirements\n"
            "11. Negative constraints\n\n"
            "NEGATIVE CONSTRAINTS:\n"
            "no text, no subtitles, no captions, no letters, no numbers, no logo, no watermark, no UI, no blurry subject, no low detail, no pixelation, no distorted face, no deformed hands, no extra fingers, no duplicated characters, no cropped head, no cropped important objects, no extreme close-up, no oversaturated colors, no messy composition.\n\n"
            "IMPORTANT:\n"
            "Do not write generic prompts such as:\n"
            "\"beautiful scene\", \"high quality image\", or \"cinematic image\" without explaining the actual visual content.\n"
            "Every prompt must describe exactly what should be visible in the image.\n"
            "The image prompt must be self-contained because it will be sent directly to an image generation model without additional context.\n\n"
            "STORY REQUIREMENTS:\n"
            "- Create 5–6 scenes unless the story genuinely requires fewer.\n"
            "- Each scene should move the story forward.\n"
            "- Avoid redundant scenes.\n"
            "- Each narration should correspond directly to what is visually shown.\n"
            "- Maintain consistent characters and environment throughout the story.\n\n"
            "OUTPUT FORMAT:\n"
            "Return ONLY valid JSON.\n"
            "{\n"
            '  "title_vi": "Vietnamese YouTube title",\n'
            '  "description_vi": "Vietnamese YouTube description",\n'
            '  "theme": "Chủ đề chính",\n'
            f'  "art_style": "{vs}",\n'
            '  "character_style": "Detailed protagonist visual description for consistency",\n'
            '  "niche": "' + str(niche) + '",\n'
            '  "summary": "Short Vietnamese summary",\n'
            '  "themes": ["từ_khóa_1", "từ_khóa_2", "từ_khóa_3"],\n'
            '  "scenes": [\n'
            "    {\n"
            '      "scene_id": 1,\n'
            '      "narration_text_vi": "Vietnamese narration",\n'
            '      "image_prompt_en": "Detailed English image generation prompt"\n'
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
