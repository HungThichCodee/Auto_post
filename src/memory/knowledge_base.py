import os
import logging
from datetime import datetime
from typing import Optional, List

class KnowledgeBase:
    """Manages the long-term memory knowledge base file."""
    
    def __init__(self, filepath: str = "knowledge_base.md"):
        self.filepath = filepath
        self.logger = logging.getLogger(__name__)
        
        # Create file if not exists
        if not os.path.exists(self.filepath):
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.filepath)), exist_ok=True)
                with open(self.filepath, 'w', encoding='utf-8') as f:
                    f.write("# Knowledge Base\n\n")
                self.logger.info(f"Created new knowledge base at {self.filepath}")
            except Exception as e:
                self.logger.error(f"Failed to create knowledge base: {e}")
                
    def read_history(self) -> str:
        """Read the entire knowledge base content for AI context."""
        try:
            if not os.path.exists(self.filepath):
                return ""
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Error reading knowledge base: {e}")
            return ""
            
    def append_entry(self, 
                     platform: str, 
                     niche: str, 
                     content_summary: str, 
                     themes: List[str],
                     post_url: str = ""):
        """Append a new entry after posting."""
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        themes_str = ", ".join(themes)
        
        entry = f"### {date_str} | {platform} | {niche}\n"
        entry += f"- **Summary**: {content_summary}\n"
        entry += f"- **Themes**: {themes_str}\n"
        if post_url:
            entry += f"- **Post URL**: {post_url}\n"
        entry += "---\n\n"
        
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                f.write(entry)
            self.logger.info(f"Appended new entry to knowledge base for {platform}")
        except Exception as e:
            self.logger.error(f"Error appending to knowledge base: {e}")
            
    def get_recent_themes(self, n: int = 20) -> List[str]:
        """Extract themes from the last N entries to help AI avoid repetition."""
        themes = []
        try:
            if not os.path.exists(self.filepath):
                return []
                
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            entries = content.split("---")
            # Get last N entries, ignoring the empty string at the end if any
            recent_entries = [e for e in entries if e.strip()][-n:]
            
            for entry in recent_entries:
                lines = entry.strip().split('\n')
                for line in lines:
                    if line.startswith("- **Themes**:"):
                        themes_part = line.replace("- **Themes**:", "").strip()
                        entry_themes = [t.strip() for t in themes_part.split(",")]
                        themes.extend(entry_themes)
                        
            return themes
        except Exception as e:
            self.logger.error(f"Error extracting themes: {e}")
            return []
            
    def get_entry_count(self) -> int:
        """Count total entries in the knowledge base."""
        try:
            if not os.path.exists(self.filepath):
                return 0
                
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            # Each entry is separated by "---", so count occurrences
            return content.count("---")
        except Exception as e:
            self.logger.error(f"Error counting entries: {e}")
            return 0
