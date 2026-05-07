"""Every HKDF label used in code must be registered in assets/v1/labels.json.

This is the v1 forward-compatibility contract: future versions cannot rename
or remove an existing label without bumping spec_version.
"""
import json
import os
import re

import pytest


_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_LABELS_PATH = os.path.join(_ROOT, "assets", "v1", "labels.json")
_LABEL_RE = re.compile(r'\.take\(\s*"([^"]+)"|\.pick\(\s*"([^"]+)"', re.MULTILINE)


def _registered_label_patterns() -> list[str]:
    with open(_LABELS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["labels"]


def _matches(used: str, pattern: str) -> bool:
    # Treat <...> in registry pattern as a wildcard.
    rx = "^" + re.escape(pattern).replace(r"\<i\>", r".+").replace(r"\<n\>", r".+") + "$"
    return bool(re.match(rx, used))


def test_registry_is_nonempty():
    assert _registered_label_patterns()


@pytest.mark.skip(reason="enable once decoder uses labeled streams beyond 'macro'")
def test_all_labels_used_in_code_are_registered():
    src_dir = os.path.join(_ROOT, "src", "soundhash")
    found: set[str] = set()
    for dirpath, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith(".py"):
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    for m in _LABEL_RE.finditer(fh.read()):
                        found.add(m.group(1) or m.group(2))
    patterns = _registered_label_patterns()
    for label in found:
        assert any(_matches(label, p) for p in patterns), \
            f"label {label!r} used in code but not in labels.json"
