"""selectors.yaml 로더."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

SELECTORS_PATH = Path(__file__).parent / "selectors.yaml"


@lru_cache(maxsize=1)
def load_selectors() -> dict[str, Any]:
    with SELECTORS_PATH.open(encoding="utf-8") as fp:
        return yaml.safe_load(fp) or {}


def platform_selectors(platform: str) -> dict[str, Any]:
    return load_selectors().get(platform, {})
