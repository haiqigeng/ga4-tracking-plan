from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().casefold()


def normalize_ascii_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", normalize_text(value))
    return "".join(character for character in text if not unicodedata.combining(character))
