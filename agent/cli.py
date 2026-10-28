"""ממשק CLI אינטראקטיבי.

הרצה:  python -m agent.cli      (או agent.exe אחרי בנייה ב-PyInstaller)
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from . import config, tools
from .graph import run_agent
from .llm import AgentError, CostTracker
from .nodes import set_reporter

# ---------------------------------------------------------------- תצוגה
if sys.platform == "win32":
    os.system("")  # מפעיל צבעי ANSI בטרמינל של Windows
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

# טרמינלים של Windows אינם מציגים עברית מימין לשמאל; python-bidi מסדר את השורה לתצוגה
_BIDI = os.getenv("AGENT_BIDI", "1" if sys.platform == "win32" else "0") == "1"
try:
    from bidi import get_display as _get_display
except ImportError:
    try:
        from bidi.algorithm import get_display as _get_display
    except ImportError:
        _get_display = None

C = {"info": "\033[36m", "ok": "\033[32m", "warn": "\033[33m", "err": "\033[31m", "dim": "\033[2m",
     "bold": "\033[1m", "end": "\033[0m"}


def show(text: str = "", style: str = "") -> None:
    lines = text.split("\n")
    if _BIDI and _get_display:
        lines = [_get_display(line) for line in lines]
    out = "\n".join(lines)
    print(f"{C.get(style, '')}{out}{C['end'] if style else ''}", flush=True)


def ask(prompt: str) -> str:
    show(prompt, "bold")
    try:
        return input("> ").strip()
    except EOFError:
        return "exit"


def yes_no(prompt: str) -> bool:
    while True:
        a = ask(f"{prompt} [Y/N]").lower()
        if a in ("y", "yes", "כ", "כן"):
            return True
        if a in ("n", "no", "ל", "לא", ""):
            return False


def _stream(msg: str) -> None:
    style = "err" if msg.startswith("[GUARD]") else "warn" if msg.startswith(("[GATE]", "[EVAL]")) else "info"
    show(msg, style)


HELP = """
אייג'נט מסלול קניות - מדריך קצר
--------------------------------
הרשימה השבועית (נשמרת בין הפעלות):
  add <פריטים>        הוספת פריטים לרשימה. למשל:  add 2 חלב, טחינה, לחם אחיד
  list                הצגת הרשימה
  remove <מספר>       מחיקת פריט מהרשימה
  clear               ריקון הרשימה (עם אישור)
  plan                חישוב מסלול לכל הרשימה השבועית

הרצה ישירה:
  <טקסט חופשי>        כתבו רשימה ישירות, למשל:  עגבניות, במבה, נוזל כלים
  load <נתיב לקובץ>   חישוב מסלול לרשימה מתוך קובץ טקסט מקומי

הגדרות ומידע:
  store [שם]          הצגת החנות הפעילה / החלפת חנות
  model [מזהה]        הצגת המודל הפעיל / החלפה (מזהה מ-openrouter.ai/models)
  tools               הרחבות פעילות
  cost                עלות ושימוש מצטברים בהפעלה הנוכחית
  summary             ייצוא תקציר השיחה לקובץ טקסט
  help / ?            המדריך הזה
  exit                יציאה

במהלך הריצה האייג'נט עשוי לעצור ולשאול: באיזו מחלקה לחפש פריט כשלא ברור איפה הוא,
לבחור בין מוצרים שנמצאים במקומות שונים, ולאשר שמירת המסלול לקובץ.
"""


# ---------------------------------------------------------------- HITL בטרמינל
def terminal_hitl(payload: dict):
    if payload["kind"] == "clarify":
        show("\n[HITL] נדרשת הבהרה לגבי כמה פריטים:", "warn")
        answers = {}
        for q in payload["questions"]:
            show(f"\nלמה התכוונתם ב-'{q['text']}'?" if q["type"] == "choose"
                 else f"\nבאיזו מחלקה לחפש את '{q['text']}'?")
            for i, o in enumerate(q["options"], 1):
                show(f"  {i}. {o['name']}")
            show("  0. לדלג על הפריט")
            while True:
                a = ask("בחרו מספר:")
                if a.isdigit() and 0 <= int(a) <= len(q["options"]):
                    break
            answers[str(q["idx"])] = q["options"][int(a) - 1]["id"] if int(a) else None
        return answers
    if payload["kind"] == "confirm_save":
        if not yes_no(f"\n[HITL] לשמור את המסלול לקובץ?\n  {payload['path']}"):
            return False
        custom = ask("Enter לשמירה בנתיב הזה, או הקלידו נתיב אחר:")
        return custom or payload["path"]
    return None


# ---------------------------------------------------------------- רשימה שבועית
def _read_list() -> list[str]:
    if not config.LIST_FILE.exists():
        return []
    return [l.strip() for l in config.LIST_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]


def _write_list(items: list[str]) -> None:
    config.LIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.LIST_FILE.write_text("\n".join(items) + ("\n" if items else ""), encoding="utf-8")


# ---------------------------------------------------------------- לולאה ראשית
class Session:
    def __init__(self):
        self.model = config.DEFAULT_MODEL
        self.store = config.DEFAULT_STORE
        self.tracker = CostTracker()
        self.log: list[tuple[str, str]] = []

    def run(self, text: str) -> None:
        t0 = time.perf_counter()
        task_tracker = CostTracker()
        state, _ = run_agent(text, model=self.model, store=self.store, hitl=terminal_hitl, tracker=task_tracker)
        self.tracker.records.extend(task_tracker.records)
        result = state.get("final_text", "")
        show("\n" + "=" * 50, "dim")
        show(result, "ok" if not state.get("blocked") else "warn")
        show("=" * 50, "dim")
        show(f"\nזמן: {time.perf_counter() - t0:.1f} שניות | מודל: "
             f"{'mock/heuristic' if config.mock_enabled() else self.model}", "dim")
        show(task_tracker.report(), "dim")
        self.log.append((text, result))

    def handle(self, line: str) -> bool:
        cmd, _, arg = line.partition(" ")
        cmd, arg = cmd.lower(), arg.strip()
        if cmd in ("exit", "quit", "q", "יציאה"):
            return False
        if cmd in ("help", "?", "עזרה"):
            show(HELP)
        elif cmd == "add":
            new = [p.strip() for p in arg.replace("\n", ",").split(",") if p.strip()]
            if not new:
                show("כתבו פריטים אחרי add, מופרדים בפסיקים.", "warn")
            else:
                _write_list(_read_list() + new)
                show(f"נוספו {len(new)} פריטים. ברשימה כעת {len(_read_list())} פריטים.", "ok")
        elif cmd == "list":
            items = _read_list()
            show("\n".join(f"{i}. {x}" for i, x in enumerate(items, 1)) or "הרשימה ריקה.")
        elif cmd == "remove":
            items = _read_list()
            if arg.isdigit() and 1 <= int(arg) <= len(items):
                removed = items.pop(int(arg) - 1)
                _write_list(items)
                show(f"הוסר: {removed}", "ok")
            else:
                show("מספר פריט לא תקין. השתמשו ב-list כדי לראות את המספרים.", "warn")
        elif cmd == "clear":
            if yes_no("[HITL] לרוקן את כל הרשימה השבועית?"):
                _write_list([])
                show("הרשימה רוקנה.", "ok")
        elif cmd == "plan":
            items = _read_list()
            if not items:
                show("הרשימה השבועית ריקה. הוסיפו פריטים עם add.", "warn")
            else:
                self.run("\n".join(items))
        elif cmd == "load":
            if not arg:
                show("ציינו נתיב לקובץ, למשל: load C:\\Users\\me\\list.txt", "warn")
            else:
                self.run(tools.read_list_file(arg.strip('"')))
        elif cmd == "store":
            if arg:
                tools.load_store(arg)  # זורק שגיאה ברורה אם לא קיימת
                self.store = arg
            show(f"חנות פעילה: {self.store} (זמינות: {', '.join(tools.list_stores())})")
        elif cmd == "model":
            if arg:
                self.model = arg
            show(f"מודל פעיל: {'mock/heuristic (מצב הדגמה)' if config.mock_enabled() else self.model}")
        elif cmd == "tools":
            show("הרחבות פעילות:\n  RAG - שליפה ממחלקות החנות ומרשימת המוצרים החריגים (TF-IDF על תווים, מקומי)\n"
                 "  Route Tool - כלי פנימי לחישוב מסלול (Dijkstra + 2-opt) על מפת החנות\n"
                 "  File I/O - קריאת רשימה מקובץ, שמירת מסלול (באישור)\n  MCP - לא בשימוש")
        elif cmd == "cost":
            show(self.tracker.report())
        elif cmd == "summary":
            self.export_summary()
        else:
            self.run(line)
        return True

    def export_summary(self) -> None:
        if not self.log:
            show("עדיין אין שיחה לייצא.", "warn")
            return
        path = Path.cwd() / f"session_summary_{datetime.now():%Y%m%d_%H%M}.txt"
        if not yes_no(f"[HITL] לשמור תקציר שיחה לקובץ {path}?"):
            return
        t = self.tracker.totals()
        parts = [f"תקציר שיחה - {datetime.now():%d/%m/%Y %H:%M}", f"מודל: {self.model} | חנות: {self.store}",
                 f"משימות: {len(self.log)} | טוקנים: {t['input_tokens']}/{t['output_tokens']} | "
                 f"עלות: ${t['actual_usd']:.6f} (תיאורטית ${t['theoretical_usd']:.6f})", ""]
        for i, (q, a) in enumerate(self.log, 1):
            parts += [f"--- משימה {i} ---", "קלט:", q, "", "תוצאה:", a, ""]
        tools.save_text(path, "\n".join(parts))
        show(f"נשמר: {path}", "ok")


def main() -> None:
    set_reporter(_stream)
    s = Session()
    show("אייג'נט מסלול קניות | הקלידו help לעזרה, exit ליציאה", "bold")
    if config.mock_enabled():
        show("מצב הדגמה פעיל (AGENT_MOCK=1): ללא קריאות למודל אמיתי.", "warn")
    elif not config.OPENROUTER_API_KEY:
        show("אזהרה: לא הוגדר OPENROUTER_API_KEY. ראו README.", "warn")
    while True:
        line = ask("\nמה צריך לקנות?")
        if not line:
            continue
        try:
            if not s.handle(line):
                break
        except AgentError as e:
            show(f"[ERROR] {e}", "err")
        except (FileNotFoundError, ValueError) as e:
            show(f"[ERROR] {e}", "err")
        except KeyboardInterrupt:
            show("\nהפעולה בוטלה.", "warn")
        except Exception as e:
            show(f"[ERROR] שגיאה לא צפויה ({type(e).__name__}): {e}", "err")
            if os.getenv("AGENT_DEBUG") == "1":
                traceback.print_exc()
            else:
                show("להצגת פרטים מלאים הריצו עם AGENT_DEBUG=1", "dim")
    if s.tracker.records:
        show("\nסיכום עלויות להפעלה:", "bold")
        show(s.tracker.report())
    show("להתראות!")


if __name__ == "__main__":
    main()
