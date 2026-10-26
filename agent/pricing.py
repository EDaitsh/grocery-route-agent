"""תמחור מודלים ב-OpenRouter.

סדר עדיפויות:
1. תמחור חי מ-https://openrouter.ai/api/v1/models (נשמר במטמון מקומי).
2. קובץ pricing_fallback.json (לעבודה ללא רשת). הערכים בו הם הערכה בלבד -
   עדכנו אותם מול openrouter.ai/models לפני ההגשה.

המחירים נשמרים בדולר לטוקן בודד (כמו ב-API של OpenRouter).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import config

_CACHE_FILE = Path.home() / ".grocery_agent" / "pricing_cache.json"
_FALLBACK_FILE = config.DATA_DIR / "pricing_fallback.json"
_CACHE_TTL_SEC = 24 * 3600
_prices: dict[str, dict[str, float]] | None = None


def _fetch_live() -> dict[str, dict[str, float]]:
    import urllib.request

    with urllib.request.urlopen(f"{config.OPENROUTER_BASE_URL}/models", timeout=10) as r:
        data = json.load(r)
    out = {}
    for m in data.get("data", []):
        p = m.get("pricing") or {}
        try:
            out[m["id"]] = {"prompt": float(p.get("prompt", 0)), "completion": float(p.get("completion", 0))}
        except (TypeError, ValueError):
            continue
    return out


def _load() -> dict[str, dict[str, float]]:
    global _prices
    if _prices is not None:
        return _prices
    # 1) מטמון טרי
    try:
        if _CACHE_FILE.exists() and time.time() - _CACHE_FILE.stat().st_mtime < _CACHE_TTL_SEC:
            _prices = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            return _prices
    except Exception:
        pass
    # 2) תמחור חי
    if not config.mock_enabled():
        try:
            _prices = _fetch_live()
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _CACHE_FILE.write_text(json.dumps(_prices), encoding="utf-8")
            return _prices
        except Exception:
            pass
    # 3) קובץ גיבוי
    _prices = json.loads(_FALLBACK_FILE.read_text(encoding="utf-8"))["models"]
    return _prices


def price_of(model: str) -> dict[str, float]:
    return _load().get(model, {"prompt": 0.0, "completion": 0.0})


def is_free(model: str) -> bool:
    p = price_of(model)
    return model.endswith(":free") or (p["prompt"] == 0 and p["completion"] == 0)


def theoretical_price_of(model: str) -> dict[str, float]:
    """מחיר "שווה-ערך" למודל חינמי: גרסת התשלום של אותו מודל, ואם אין - מודל הייחוס."""
    if not is_free(model):
        return price_of(model)
    base = model.removesuffix(":free")
    p = price_of(base)
    if p["prompt"] > 0 or p["completion"] > 0:
        return p
    return price_of(config.REFERENCE_PAID_MODEL)


def cost(model: str, input_tokens: int, output_tokens: int) -> tuple[float, float]:
    """מחזיר (עלות בפועל, עלות תיאורטית) בדולרים."""
    p = price_of(model)
    actual = 0.0 if is_free(model) else input_tokens * p["prompt"] + output_tokens * p["completion"]
    t = theoretical_price_of(model)
    theoretical = input_tokens * t["prompt"] + output_tokens * t["completion"]
    return actual, theoretical
