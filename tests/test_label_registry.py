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
_LABEL_RE = re.compile(
    # `s.take("label", n)` / `s.pick("label", table)` from HashStream;
    # also `info = b"soundhash/v1/<label>"` and  `info = f"soundhash/v1/<label>"`
    r'\.take\(\s*"([^"]+)"'
    r'|\.pick\(\s*"([^"]+)"'
    r'|info\s*=\s*[bf]?"soundhash/v1/([^"{]+)"',
    re.MULTILINE,
)


def _registered_label_patterns() -> list[str]:
    with open(_LABELS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["labels"]


def _matches(used: str, pattern: str) -> bool:
    """Treat any `<placeholder>` in the registry pattern as a wildcard.

    Examples that should match the pattern `expression/velocity/L<n>`:
        expression/velocity/Ldrums, expression/velocity/Lcomp, …
    """
    # Replace `<anything>` (re-escaped) with `.+` for the match.
    rx = "^" + re.sub(r"\\<[a-zA-Z_]+\\>", ".+", re.escape(pattern)) + "$"
    return bool(re.match(rx, used))


def test_registry_is_nonempty():
    assert _registered_label_patterns()


def test_all_labels_used_in_code_are_registered():
    src_dir = os.path.join(_ROOT, "src", "mhash")
    found: set[str] = set()
    for dirpath, _, files in os.walk(src_dir):
        # Skip the pseudocode reference doc.
        if "_decoder_api_pseudocode.py" in files:
            files = [f for f in files if f != "_decoder_api_pseudocode.py"]
        for f in files:
            if f.endswith(".py"):
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    for m in _LABEL_RE.finditer(fh.read()):
                        # Strip an f-string template suffix like `Llayer_name`
                        # so the matcher only sees the pattern slot.
                        label = m.group(1) or m.group(2) or m.group(3)
                        if label:
                            found.add(label.rstrip("/"))
    patterns = _registered_label_patterns()
    for label in found:
        assert any(_matches(label, p) for p in patterns), \
            f"label {label!r} used in code but not in labels.json"
