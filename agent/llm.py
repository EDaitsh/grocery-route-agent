"""שכבת LLM: חיבור ל-OpenRouter דרך LangChain, פענוח JSON, מעקב טוקנים ועלויות לכל נוד.

במצב AGENT_MOCK=1 הקריאות מוחלפות בהיוריסטיקות דטרמיניסטיות (ראו mock.py),
כך שאפשר להריץ את הגרף, הבדיקות וה-evals בלי מפתח ובלי רשת.
"""
from __future__ import annotations

import contextvars
import json
import re
import time
from dataclasses import dataclass, field

from . import config, pricing

# הנוד הנוכחי - מתעדכן ע"י הדקורטור ב-nodes.py, כדי לשייך כל קריאה לנוד
current_node: contextvars.ContextVar[str] = contextvars.ContextVar("current_node", default="-")

# ניסיונות חוזרים על 429 (מגבלת קצב): 5, 10, 20, 40 שניות
RATE_LIMIT_RETRIES = 4
RATE_LIMIT_WAIT = 5


class AgentError(Exception):
    """שגיאה עם הודעה ידידותית למשתמש."""


@dataclass
class UsageRecord:
    node: str
    model: str
    input_tokens: int
    output_tokens: int
    actual_usd: float
    theoretical_usd: float
    seconds: float


@dataclass
class CostTracker:
    records: list[UsageRecord] = field(default_factory=list)

    def add(self, rec: UsageRecord) -> None:
        self.records.append(rec)

    def totals(self) -> dict:
        return {
            "calls": len(self.records),
            "input_tokens": sum(r.input_tokens for r in self.records),
            "output_tokens": sum(r.output_tokens for r in self.records),
            "actual_usd": sum(r.actual_usd for r in self.records),
            "theoretical_usd": sum(r.theoretical_usd for r in self.records),
        }

    def by_node(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for r in self.records:
            d = out.setdefault(r.node, {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                        "actual_usd": 0.0, "theoretical_usd": 0.0})
            d["calls"] += 1
            d["input_tokens"] += r.input_tokens
            d["output_tokens"] += r.output_tokens
            d["actual_usd"] += r.actual_usd
            d["theoretical_usd"] += r.theoretical_usd
        return out

    def report(self) -> str:
        if not self.records:
            return "לא בוצעו קריאות למודל."
        lines = [f"{'נוד':<18}{'קריאות':>7}{'טוקנים (קלט/פלט)':>20}{'עלות בפועל $':>15}{'עלות תיאורטית $':>18}"]
        for node, d in self.by_node().items():
            lines.append(f"{node:<18}{d['calls']:>7}{d['input_tokens']:>12}/{d['output_tokens']:<7}"
                         f"{d['actual_usd']:>15.6f}{d['theoretical_usd']:>18.6f}")
        t = self.totals()
        lines.append(f"{'סה״כ':<18}{t['calls']:>7}{t['input_tokens']:>12}/{t['output_tokens']:<7}"
                     f"{t['actual_usd']:>15.6f}{t['theoretical_usd']:>18.6f}")
        return "\n".join(lines)


def extract_json(text: str):
    """מוציא את אובייקט ה-JSON הראשון מתשובת המודל (גם אם עטוף ב-```json)."""
    text = re.sub(r"```(?:json)?", "", text)
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON found")


class LLM:
    def __init__(self, model: str | None = None, tracker: CostTracker | None = None, mock: bool | None = None):
        self.model = model or config.DEFAULT_MODEL
        self.tracker = tracker or CostTracker()
        self.mock = config.mock_enabled() if mock is None else mock
        self._client = None
        if self.mock:
            self.model = "mock/heuristic"

    def _get_client(self):
        if self._client is None:
            if not config.OPENROUTER_API_KEY:
                raise AgentError("חסר מפתח OPENROUTER_API_KEY. צרו קובץ .env לפי .env.example, "
                                 "או הריצו במצב הדגמה עם AGENT_MOCK=1.")
            from langchain_openai import ChatOpenAI
            self._client = ChatOpenAI(
                model=self.model,
                base_url=config.OPENROUTER_BASE_URL,
                api_key=config.OPENROUTER_API_KEY,
                temperature=0,
                timeout=60,
                max_retries=2,
                default_headers={"X-Title": "Grocery Route Agent"},
            )
        return self._client

    # ------------------------------------------------------------ קריאה בסיסית
    def _call(self, task: str, system: str, user: str) -> str:
        t0 = time.perf_counter()
        if self.mock:
            from . import mock
            text = mock.respond(task, user)
            in_tok, out_tok = (len(system) + len(user)) // 4, len(text) // 4
        else:
            from langchain_core.messages import HumanMessage, SystemMessage
            for attempt in range(RATE_LIMIT_RETRIES + 1):
                try:
                    resp = self._get_client().invoke([SystemMessage(system), HumanMessage(user)])
                    break
                except AgentError:
                    raise
                except Exception as e:  # רשת, הרשאות, מכסה, מודל לא קיים
                    # 429 במודלים חינמיים הוא לרוב זמני - ממתינים ומנסים שוב (backoff)
                    if "429" in str(e) and attempt < RATE_LIMIT_RETRIES:
                        time.sleep(RATE_LIMIT_WAIT * 2 ** attempt)
                        continue
                    raise AgentError(_friendly_api_error(e)) from e
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
            usage = resp.usage_metadata or {}
            in_tok, out_tok = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        actual, theoretical = pricing.cost(self.model, in_tok, out_tok)
        self.tracker.add(UsageRecord(current_node.get(), self.model, in_tok, out_tok,
                                     actual, theoretical, time.perf_counter() - t0))
        return text

    def text(self, task: str, system: str, user: str) -> str:
        return self._call(task, system, user).strip()

    def json(self, task: str, system: str, user: str):
        """קריאה שמחזירה JSON; ניסיון חוזר אחד עם תזכורת אם הפלט לא תקין."""
        raw = self._call(task, system, user)
        try:
            return extract_json(raw)
        except ValueError:
            raw = self._call(task, system, user + "\n\nהחזר JSON תקין בלבד, בלי טקסט נוסף.")
            try:
                return extract_json(raw)
            except ValueError as e:
                raise AgentError(f"המודל {self.model} לא החזיר JSON תקין בשלב '{task}'.") from e


def _friendly_api_error(e: Exception) -> str:
    msg = str(e)
    if "401" in msg or "Unauthorized" in msg:
        return "המפתח של OpenRouter לא תקין (401). בדקו את OPENROUTER_API_KEY בקובץ .env."
    if "402" in msg:
        return "אין מספיק קרדיט בחשבון OpenRouter עבור המודל הזה (402). נסו מודל חינמי (:free)."
    if "404" in msg:
        return "המודל לא נמצא ב-OpenRouter (404). בדקו את שם המודל ב-openrouter.ai/models."
    if "429" in msg:
        return "חרגתם ממגבלת הקצב של OpenRouter (429). המתינו מעט או החליפו מודל."
    if "timed out" in msg.lower() or "connection" in msg.lower():
        return "אין חיבור ל-OpenRouter (בעיית רשת או timeout). בדקו את החיבור לאינטרנט."
    return f"שגיאה בקריאה למודל: {msg[:300]}"
