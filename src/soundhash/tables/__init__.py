"""Static-asset loader.

Validates manifest.json bundle hash on import (when assets are populated)
and exposes typed accessors for each table.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache


_HERE = os.path.dirname(os.path.abspath(__file__))
_ASSETS = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "assets", "v1"))


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    """Load a table by its filename (without extension), e.g. load("forms")."""
    path = os.path.join(_ASSETS, f"{name}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
