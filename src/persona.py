"""
Sovi persona loader — reads data/persona.md once and caches it.

Used by both agent_loop.py and chat_processor.py to inject the
F.R.I.D.A.Y.-style system prompt into every conversation.
"""

import logging
import os

logger = logging.getLogger(__name__)

_cached_persona: str | None = None


def _persona_path() -> str:
    """Resolve persona.md relative to the project root (two dirs up from src/)."""
    src_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(src_dir)
    return os.path.join(project_root, "data", "persona.md")


def load_persona() -> str:
    """Return the persona prompt text, cached after first read.

    Returns empty string if the file is missing (graceful degradation).
    """
    global _cached_persona
    if _cached_persona is not None:
        return _cached_persona

    path = _persona_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            _cached_persona = f.read().strip()
        logger.info("Loaded Sovi persona from %s (%d chars)", path, len(_cached_persona))
    except FileNotFoundError:
        logger.warning("Persona file not found at %s — running without persona", path)
        _cached_persona = ""
    except Exception as e:
        logger.warning("Failed to read persona file %s: %s", path, e)
        _cached_persona = ""

    return _cached_persona


def reload_persona() -> str:
    """Force re-read from disk (e.g. after editing persona.md)."""
    global _cached_persona
    _cached_persona = None
    return load_persona()
