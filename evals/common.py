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


def base_args(description: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--models", default=os.getenv(
        "EVAL_MODELS",
        "meta-llama/llama-3.3-70b-instruct:free,openai/gpt-4o-mini,google/gemini-2.0-flash-001"),
        help="רשימת מזהי מודלים מופרדת בפסיקים (לפחות אחד בתשלום)")
    p.add_argument("--mock", action="store_true", help="הרצה ללא רשת עם ה-LLM המדומה")
    p.add_argument("--quiet", action="store_true", help="בלי הדפסת שלבי הגרף")
    args = p.parse_args()
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
