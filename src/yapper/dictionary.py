"""Personal dictionary for word substitutions."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class Dictionary:
    """Loads and applies personal word substitutions.

    Dictionary file format (one per line):
        wrong_word -> correct_word
        abbrev -> expansion
    """

    def __init__(self, path: str = "", enabled: bool = False) -> None:
        self._enabled = enabled
        self._subs: dict[str, str] = {}

        if not enabled:
            return

        dict_path = Path(path) if path else Path.home() / ".config" / "yapper" / "dictionary.txt"
        if dict_path.exists():
            self._load(dict_path)

    def _load(self, path: Path) -> None:
        count = 0
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if " -> " in line:
                src, dst = line.split(" -> ", 1)
                self._subs[src.strip()] = dst.strip()
                count += 1
        log.info("Loaded %d dictionary entries from %s", count, path)

    def apply(self, text: str) -> str:
        """Apply dictionary substitutions to text."""
        if not self._enabled or not self._subs:
            return text

        for src, dst in self._subs.items():
            text = text.replace(src, dst)
        return text
