"""
Pure utility functions for PersonaPreparation.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import MAX_PERSON_NAME_LENGTH, OUTPUT_DIR

logger = logging.getLogger("persona_preparation")


def validate_person_name(name: str) -> tuple[bool, str]:
    """Validate person name input."""
    if not name or not name.strip():
        return False, "Name cannot be empty"
    if len(name) > MAX_PERSON_NAME_LENGTH:
        return False, f"Name exceeds maximum length of {MAX_PERSON_NAME_LENGTH} characters"
    if re.search(r'[<>{}[\]\\]', name):
        return False, "Name contains invalid characters"
    return True, ""


def sanitize_filename(name: str) -> str:
    """Sanitize a person name for use as a filename."""
    safe_name = re.sub(r'[<>:"/\\|?*]', '', name)
    safe_name = safe_name.replace(' ', '_')
    safe_name = safe_name.strip('. ')
    safe_name = safe_name[:100]
    if not safe_name:
        safe_name = "unnamed"
    return safe_name.lower()


def save_brief_to_file(
    person_name: str,
    brief_content: str,
    meeting_context: str = "",
    output_dir: Path = OUTPUT_DIR
) -> Optional[Path]:
    """Save a meeting brief to a markdown file."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_name = sanitize_filename(person_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"brief_{safe_name}_{timestamp}.md"

        generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Meeting Brief: {person_name}\n\n")
            if meeting_context:
                f.write(f"**Meeting Context:** {meeting_context}\n\n")
            f.write(f"**Generated:** {generated_time}\n")
            f.write(f"**Generated with:** Real-time web research (Tavily, Brave Search, Firecrawl)\n\n")
            f.write("-" * 70 + "\n\n")
            f.write(brief_content)

        logger.info("Brief saved to disk.")
        return filename

    except Exception as e:
        logger.error(f"Error saving file: {e}", exc_info=True)
        return None
