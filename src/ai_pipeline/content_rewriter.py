import google.generativeai as genai
import logging
import os
import json
from typing import Optional

logger = logging.getLogger(__name__)

class ContentRewriter:
    """Uses Gemini Free API to rewrite scraped content into original posts."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("No GEMINI_API_KEY provided. API calls will fail.")
        else:
            genai.configure(api_key=self.api_key)
        self.model_name = 'gemini-2.0-flash'
        try:
            self.model = genai.GenerativeModel(self.model_name)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            self.model = None

    async def rewrite_content(self, 
                               raw_content: str, 
                               niche: dict,
                               knowledge_history: str = "",
                               platform: str = "facebook") -> dict:
        """
        Rewrite raw content into an original post.
        
        Args:
            raw_content: Scraped text content
            niche: Niche config dict with name, description, tone, image_style
            knowledge_history: Full knowledge_base.md content for context
            platform: Target platform for tone adjustment
        
        Returns:
            dict with keys:
                - 'content': The rewritten post text (in Vietnamese)
                - 'image_prompt': Detailed English image prompt
                - 'summary': Brief summary for knowledge base
                - 'themes': List of key themes used
        """
        if not self.model:
            raise ValueError("Gemini model not initialized. Check API key.")
            
        system_prompt = self._build_system_prompt(niche, platform)
        user_prompt = self._build_user_prompt(raw_content, knowledge_history)
        
        full_prompt = f"System Instructions:\n{system_prompt}\n\nUser Prompt:\n{user_prompt}"
        
        try:
            response = await self.model.generate_content_async(full_prompt)
            if not response.text:
                raise ValueError("Empty response from Gemini")
            return self._parse_response(response.text)
        except Exception as e:
            logger.error(f"Error during content rewriting: {e}")
            return {
                'content': '',
                'image_prompt': '',
                'summary': '',
                'themes': []
            }

    def _build_system_prompt(self, niche: dict, platform: str) -> str:
        niche_name = niche.get('name', 'general')
        niche_desc = niche.get('description', '')
        niche_tone = niche.get('tone', 'engaging')
        
        prompt = (
            "You are an expert content creator. Follow these instructions carefully:\n"
            "1. Output MUST be primarily in VIETNAMESE, except for the 'image_prompt' which MUST be in English.\n"
            f"2. Your niche is '{niche_name}': {niche_desc}. Match this tone: {niche_tone}.\n"
        )
        
        if niche_name.lower() == 'stories':
            prompt += "   - Write an episode of a serialized story, make it dramatic and engaging.\n"
        elif niche_name.lower() == 'humor':
            prompt += "   - Write funny, relatable content with Vietnamese humor style.\n"
        elif niche_name.lower() == 'health':
            prompt += "   - Write informative health content, focusing on vegetables or natural remedies.\n"
            
        if platform.lower() == 'facebook':
            prompt += "3. For Facebook: Write a longer, engaging post. Use paragraphs and emojis.\n"
        elif platform.lower() == 'tiktok':
            prompt += "3. For TikTok: Write a shorter, punchy script/caption with trending hashtags.\n"
        elif platform.lower() == 'youtube':
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
            # Try to parse the response as JSON directly
            # Often LLMs wrap JSON in markdown code blocks
            clean_text = response_text.strip()
            if clean_text.startswith('```json'):
                clean_text = clean_text[7:]
            if clean_text.startswith('```'):
                clean_text = clean_text[3:]
            if clean_text.endswith('```'):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            data = json.loads(clean_text)
            
            return {
                'content': data.get('content', ''),
                'image_prompt': data.get('image_prompt', ''),
                'summary': data.get('summary', ''),
                'themes': data.get('themes', [])
            }
        except json.JSONDecodeError:
            logger.warning("Failed to parse Gemini response as JSON. Attempting manual extraction.")
            # Fallback for completely unstructured response
            return {
                'content': response_text,
                'image_prompt': 'A detailed scene capturing the essence of the content, cinematic lighting, 8k resolution, highly detailed',
                'summary': 'Summary parsing failed.',
                'themes': []
            }
