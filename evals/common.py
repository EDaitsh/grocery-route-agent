"""כלים משותפים ל-evals."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS_DIR = Path(__file__).resolve().parent / "results"
DATA_DIR = Path(__file__).resolve().parent / "data"

# --append: שומר שורות של מודלים אחרים מריצה קודמת (למשל כשמודל חינמי נחסם ומריצים אותו שוב בנפרד)
APPEND = False


def base_args(description: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--models", default=os.getenv(
        "EVAL_MODELS",
        "nvidia/nemotron-3-ultra-550b-a55b:free,openai/gpt-4o-mini,google/gemini-2.5-flash-lite"),
        help="רשימת מזהי מודלים מופרדת בפסיקים (לפחות אחד בתשלום)")
    p.add_argument("--mock", action="store_true", help="הרצה ללא רשת עם ה-LLM המדומה")
    p.add_argument("--quiet", action="store_true", help="בלי הדפסת שלבי הגרף")
    p.add_argument("--append", action="store_true",
                   help="להוסיף לקובץ ה-CSV הקיים במקום לדרוס (שורות של המודלים שרצו עכשיו מוחלפות)")
    args = p.parse_args()
    global APPEND
    APPEND = args.append
    if args.mock:
        os.environ["AGENT_MOCK"] = "1"
    return args


def models_from(args) -> list[str]:
    return ["mock/heuristic"] if args.mock else [m.strip() for m in args.models.split(",") if m.strip()]


def load_json(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def write_csv(name: str, rows: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / name
    if APPEND and path.exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            current = {r["model"] for r in rows}
            rows = [r for r in csv.DictReader(f) if r["model"] not in current] + rows
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: עברית תקינה באקסל
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return path
