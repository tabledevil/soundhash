"""MIME → mood family resolver.

Pinned implementation: python-magic 0.4.27 + frozen magic.mgc.
Fallback chain: exact MIME → prefix rule → extension → unknown.

This module is a stub; full resolution and provenance recording land in step 2.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Optional


_HERE = os.path.dirname(os.path.abspath(__file__))
_ASSETS = os.path.normpath(os.path.join(_HERE, "..", "..", "assets", "v1"))


@lru_cache(maxsize=1)
def _families() -> dict:
    with open(os.path.join(_ASSETS, "mime_families.json"), "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _family_to_moods() -> dict:
    with open(os.path.join(_ASSETS, "family_to_moods.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def detect_mime(path: str) -> Optional[str]:
    """Detect MIME via libmagic. Returns None if libmagic not available."""
    try:
        import magic  # python-magic
    except ImportError:
        return None
    return magic.from_file(path, mime=True)


def family_for_mime(mime: Optional[str]) -> str:
    """Return one of the family slugs from mime_families.json.

    Resolution order: exact match → prefix match → top-level fallback → unknown.
    """
    if not mime:
        return "unknown"
    mime = mime.split(";", 1)[0].strip().lower()
    fams = _families().get("families", [])
    # 1. Exact MIME match.
    for fam in fams:
        if mime in {m.lower() for m in fam.get("exact", [])}:
            return fam["slug"]
    # 2. Prefix match (e.g. "application/vnd.openxmlformats-..."
    #    matched by "application/vnd.openxmlformats" prefix).
    for fam in fams:
        for pre in fam.get("prefix", []):
            if mime.startswith(pre.lower()):
                return fam["slug"]
    # 3. Top-level fallback.
    top = mime.split("/", 1)[0]
    top_map = {
        "text": "text-code", "image": "image", "audio": "audio",
        "video": "video", "font": "font", "model": "model-3d",
    }
    return top_map.get(top, "unknown")


def candidate_moods(family: str) -> list[str]:
    mapping = _family_to_moods()["mapping"]
    return mapping.get(family, mapping["unknown"])["candidates"]
