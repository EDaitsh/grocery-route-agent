"""הגדרות כלליות: נתיבים, משתני סביבה ומודלים."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _base_dir() -> Path:
    # כשהקוד רץ מתוך exe של PyInstaller, הקבצים נפרשים לתיקייה זמנית (sys._MEIPASS)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "agent"
    return Path(__file__).resolve().parent


BASE_DIR = _base_dir()
DATA_DIR = BASE_DIR / "data"
STORES_DIR = DATA_DIR / "stores"

# .env נטען מהתיקייה שממנה מריצים (ליד ה-exe), ואם אין - משורש הפרויקט
load_dotenv(Path.cwd() / ".env")
load_dotenv(BASE_DIR.parent / ".env")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# מודל ברירת מחדל לאייג'נט. רשימת המודלים החינמיים משתנה - בדקו ב-openrouter.ai/models
DEFAULT_MODEL = os.getenv("AGENT_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
# מודל שופט קבוע ל-evals (LLM-as-judge)
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai/gpt-4o-mini")
# מודל ייחוס לחישוב "עלות תיאורטית" למודל חינמי שאין לו גרסה בתשלום
REFERENCE_PAID_MODEL = os.getenv("REFERENCE_PAID_MODEL", "openai/gpt-4o-mini")

DEFAULT_STORE = os.getenv("AGENT_STORE", "demo_store")

# מצב הדגמה ללא רשת: מחליף את ה-LLM בהיוריסטיקות דטרמיניסטיות (לבדיקות ולהדגמה)
MOCK_LLM = os.getenv("AGENT_MOCK", "0") == "1"


def mock_enabled() -> bool:
    """נקרא בזמן ריצה (ולא רק בטעינה), כדי ש-evals יוכלו להפעיל מצב הדגמה עם --mock."""
    return os.getenv("AGENT_MOCK", "0") == "1"

# קובץ הרשימה השבועית המצטברת
LIST_FILE = Path(os.getenv("AGENT_LIST_FILE", str(Path.home() / ".grocery_agent" / "weekly_list.txt")))

# ספי ביטחון ל-Gate
MATCH_CONFIDENCE_MIN = 0.7
MAX_REWRITE_ATTEMPTS = 2
