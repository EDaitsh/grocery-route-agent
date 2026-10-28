"""מצב הדגמה (AGENT_MOCK=1): תחליף דטרמיניסטי ל-LLM.

לא מיועד לשימוש אמיתי - רק כדי שהגרף, הבדיקות וה-evals ירוצו בלי מפתח ובלי רשת,
ולצורך השוואה ("baseline") מול מודלים אמיתיים ב-eval.
"""
from __future__ import annotations

import json
import re

from . import config
from .llm import extract_json

_OUT_OF_SCOPE = re.compile(r"(מתכון|מזג|שיר|כתוב לי|ספר לי|בדיחה|תרגם|קוד|פייתון|מי זה|מי היה|למה |"
                           r"הסבר|השווה מחיר|כמה עולה|המלצה על|עצה|פוליטי|חדשות)")
_SPLIT = re.compile(r"[,\n;،]+|\s+ו(?=[א-ת]{2,})")
_MELTS = re.compile(r"(גלידה|ארטיק|קרטיב|שלגון)")


def _parts(text: str) -> list[str]:
    text = re.sub(r"^(צריך|צריכה|לקנות|רשימה|קניות)[:\s]+", "", text.strip())
    return [p.strip(" .-•*") for p in _SPLIT.split(text) if p.strip(" .-•*")]


def respond(task: str, user: str) -> str:
    data = extract_json(user)
    if task == "guardrail":
        return json.dumps(_guard(data["text"]), ensure_ascii=False)
    if task == "parse":
        return json.dumps({"items": [_parse_one(p) for p in _parts(data["text"])]}, ensure_ascii=False)
    if task == "match":
        return json.dumps({"matches": [_match(it) for it in data["items"]]}, ensure_ascii=False)
    if task == "instructions":
        return _instructions(data)
    if task == "judge":
        return json.dumps({"relevance": 4, "accuracy": 4, "completeness": 4, "format": 4,
                           "score": 4, "reason": "mock judge"})
    return "{}"


def _guard(text: str) -> dict:
    if _OUT_OF_SCOPE.search(text):
        return {"in_scope": False, "reason": "בקשה שאינה רשימת קניות"}
    from .tools import load_store
    rag, _ = load_store(config.DEFAULT_STORE)
    hits = sum(1 for p in _parts(text)
               if max([c["score"] for c in rag.search(p, 1) + rag.search_departments(p, 1)] or [0]) >= 0.45)
    if hits or text.startswith(("איפה", "באיזה מעבר")):
        return {"in_scope": True, "reason": "רשימת מוצרים"}
    return {"in_scope": False, "reason": "לא זוהו מוצרים"}


def _parse_one(part: str) -> dict:
    qty = None
    m = re.match(r"^(\d+)\s*(?:x|יח'?|יחידות)?\s*(.+)$", part)
    if m:
        qty, part = int(m.group(1)), m.group(2)
    return {"name": part.strip(), "qty": qty, "note": ""}


def _match(item: dict) -> dict:
    out = {"idx": item["idx"], "status": "not_sold", "product_id": None, "options": [], "department": None,
           "alternatives": [], "melts": bool(_MELTS.search(item["text"])), "confidence": 0.0}
    # מוצר ידוע רק בהתאמה חזקה בשם, אחרת שיוך למחלקה לפי הדוגמאות שלה
    p = item["known_products"]
    if p and p[0]["score"] >= 0.75:
        close = [x["id"] for x in p if p[0]["score"] - x["score"] < 0.1]
        if len(close) > 1:
            out.update(status="ambiguous", options=close, confidence=0.5)
        else:
            out.update(status="product", product_id=p[0]["id"], confidence=p[0]["score"])
        return out
    d = item["department_hints"]
    if d and d[0]["score"] >= 0.45:
        out.update(status="department", department=d[0]["name"], confidence=min(1.0, d[0]["score"] + 0.2),
                   alternatives=[x["name"] for x in d[1:] if d[0]["score"] - x["score"] < 0.15])
    return out


def _instructions(data: dict) -> str:
    lines, n = [f"מסלול ב{data['store']}:"], 0
    for s in data["stops"]:
        if not s["products"]:
            continue
        n += 1
        prods = ", ".join(p["name"] + (f" x{p['qty']}" if p.get("qty") else "") for p in s["products"])
        lines.append(f"{n}. {s['label']} - לאסוף: {prods}"
                     + (" (בסוף המסלול, כדי שלא יימס)" if s.get("collect_last") else ""))
    if not data["stops"][-1]["products"]:
        lines.append(f"{n + 1}. {data['stops'][-1]['label']}")
    lines.append(f"סה\"כ כ-{data['total_m']:.0f} מטר הליכה.")
    return "\n".join(lines)
