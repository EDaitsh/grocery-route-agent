"""שרת FastAPI לממשק ה-Web (מסלול B): אותו גרף ואותם נודים כמו ב-CLI, עם ממשק דפדפן.

הרצה:  python run_web.py      (או agent-web.exe)

כל משימה רצה ב-thread נפרד. הודעות הנודים (Streaming) נשלחות לדפדפן ב-Server-Sent Events,
וכשהגרף עוצר ב-interrupt (HITL), השאלה נשלחת לדפדפן וה-thread ממתין לתשובה מ-POST /answer.
זו אפליקציה מקומית למשתמש אחד, ולכן רצה משימה אחת בכל רגע.
"""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, tools
from .graph import run_agent
from .llm import AgentError, CostTracker
from .nodes import set_reporter

HITL_TIMEOUT_S = 30 * 60
NODE_PREFIX = "[INFO] Entering Node: "


class Cancelled(Exception):
    pass


def _cost(tracker: CostTracker) -> dict:
    return {"totals": tracker.totals(), "by_node": tracker.by_node()}


def _error_text(e: Exception) -> str:
    if isinstance(e, (AgentError, FileNotFoundError, ValueError)):
        return str(e)
    return f"שגיאה לא צפויה ({type(e).__name__}): {e}"


# ---------------------------------------------------------------- מצב ההפעלה (משתמש יחיד)
class Session:
    def __init__(self):
        self.model = config.DEFAULT_MODEL
        self.store = config.DEFAULT_STORE
        self.tracker = CostTracker()
        self.log: list[tuple[str, str]] = []
        self.active: Run | None = None
        self.runs: dict[str, Run] = {}


class Run:
    def __init__(self, session: Session, text: str):
        self.id = uuid.uuid4().hex
        self.session = session
        self.text = text
        self.events: list[dict] = []
        self.cond = threading.Condition()
        self.answers: queue.Queue = queue.Queue()
        self.tracker = CostTracker()

    def emit(self, type_: str, **data) -> None:
        with self.cond:
            self.events.append({"type": type_, **data})
            self.cond.notify_all()

    def report(self, msg: str) -> None:
        if msg.startswith(NODE_PREFIX):
            self.emit("node", name=msg[len(NODE_PREFIX):].strip())
        else:
            self.emit("log", message=msg)

    def hitl(self, payload: dict):
        self.emit("hitl", payload=payload)
        try:
            answer = self.answers.get(timeout=HITL_TIMEOUT_S)
        except queue.Empty:
            raise Cancelled() from None
        if isinstance(answer, Cancelled):
            raise answer
        self.emit("hitl_answered")
        return answer

    def work(self) -> None:
        s, t0 = self.session, time.perf_counter()
        try:
            state, _ = run_agent(self.text, model=s.model, store=s.store, hitl=self.hitl, tracker=self.tracker)
            final = state.get("final_text", "")
            s.log.append((self.text, final))
            self.emit("result", text=final, blocked=bool(state.get("blocked")), route=state.get("route"),
                      not_found=state.get("not_found", []), saved_path=state.get("saved_path"),
                      seconds=round(time.perf_counter() - t0, 1), cost=_cost(self.tracker))
        except Cancelled:
            self.emit("cancelled")
        except Exception as e:  # כל שגיאה מוצגת בממשק, השרת ממשיך לפעול
            self.emit("error", message=_error_text(e), cost=_cost(self.tracker))
        finally:
            s.tracker.records.extend(self.tracker.records)
            s.active = None
            self.emit("end", session_cost=_cost(s.tracker))

    def stream(self, start: int):
        i = start
        while True:
            with self.cond:
                self.cond.wait_for(lambda: len(self.events) > i, timeout=15)
                batch = self.events[i:]
            if not batch:
                yield ": ping\n\n"
                continue
            for ev in batch:
                i += 1
                yield f"id: {i}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if ev["type"] == "end":
                    return


S = Session()
set_reporter(lambda msg: S.active.report(msg) if S.active else None)

app = FastAPI(title="Grocery Route Agent")


@app.exception_handler(AgentError)
@app.exception_handler(FileNotFoundError)
@app.exception_handler(ValueError)
async def _user_errors(request: Request, e: Exception):
    return JSONResponse({"error": _error_text(e)}, status_code=400)


@app.exception_handler(Exception)
async def _unexpected_errors(request: Request, e: Exception):
    return JSONResponse({"error": _error_text(e)}, status_code=500)


# ---------------------------------------------------------------- מידע והגדרות
TOOLS = [
    {"name": "RAG", "active": True, "description": "שליפה ממחלקות החנות ומרשימת המוצרים החריגים (TF-IDF על תווים, מקומי)"},
    {"name": "Route Tool", "active": True, "description": "כלי פנימי לחישוב מסלול (Dijkstra + 2-opt) על מפת החנות"},
    {"name": "File I/O", "active": True, "description": "טעינת רשימה מקובץ, שמירת מסלול לקובץ (באישור)"},
    {"name": "MCP", "active": False, "description": "לא בשימוש"},
]


@app.get("/api/state")
def get_state():
    return {"model": S.model, "store": S.store, "stores": tools.list_stores(), "mock": config.mock_enabled(),
            "has_key": bool(config.OPENROUTER_API_KEY), "busy": S.active is not None,
            "active_run": S.active.id if S.active else None, "tools": TOOLS,
            "suggested_models": [config.DEFAULT_MODEL, "openai/gpt-4o-mini", "google/gemini-2.5-flash-lite"],
            "cost": _cost(S.tracker), "tasks": len(S.log)}


class Settings(BaseModel):
    model: str | None = None
    store: str | None = None


@app.post("/api/settings")
def set_settings(body: Settings):
    if body.store:
        tools.load_store(body.store)  # שגיאה ברורה אם החנות לא קיימת או שקובץ האקסל שבור
        S.store = body.store
    if body.model and body.model.strip():
        S.model = body.model.strip()
    return get_state()


@app.get("/api/map")
def get_map():
    _, smap = tools.load_store(S.store)
    return smap.drawing()


# ---------------------------------------------------------------- הרצת משימה + HITL
class RunRequest(BaseModel):
    text: str


@app.post("/api/runs")
def start_run(body: RunRequest):
    if not body.text.strip():
        raise HTTPException(400, "כתבו רשימת קניות.")
    if S.active:
        raise HTTPException(409, "משימה אחרת עדיין רצה. המתינו לסיומה או בטלו אותה.")
    run = Run(S, body.text.strip())
    S.active = S.runs[run.id] = run
    threading.Thread(target=run.work, daemon=True).start()
    return {"run_id": run.id}


def _run(run_id: str) -> Run:
    if run_id not in S.runs:
        raise HTTPException(404, "המשימה לא נמצאה.")
    return S.runs[run_id]


@app.get("/api/runs/{run_id}/events")
def run_events(run_id: str, request: Request):
    run = _run(run_id)
    last = request.headers.get("last-event-id", "0")
    return StreamingResponse(run.stream(int(last) if last.isdigit() else 0), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class Answer(BaseModel):
    answer: Any = None


@app.post("/api/runs/{run_id}/answer")
def answer(run_id: str, body: Answer):
    _run(run_id).answers.put(body.answer)
    return {"ok": True}


@app.post("/api/runs/{run_id}/cancel")
def cancel(run_id: str):
    # ביטול אפשרי כשהגרף ממתין לתשובת משתמש; קריאה למודל שכבר נשלחה תסתיים קודם
    _run(run_id).answers.put(Cancelled())
    return {"ok": True}


# ---------------------------------------------------------------- רשימה שבועית
class Items(BaseModel):
    items: list[str]


@app.get("/api/list")
def get_list():
    return {"items": tools.read_weekly_list()}


@app.post("/api/list")
def add_to_list(body: Items):
    new = [p.strip() for line in body.items for p in line.replace("\n", ",").split(",") if p.strip()]
    tools.write_weekly_list(tools.read_weekly_list() + new)
    return get_list()


@app.delete("/api/list/{index}")
def remove_from_list(index: int):
    items = tools.read_weekly_list()
    if not 0 <= index < len(items):
        raise HTTPException(400, "מספר פריט לא תקין.")
    items.pop(index)
    tools.write_weekly_list(items)
    return get_list()


@app.delete("/api/list")
def clear_list():
    tools.write_weekly_list([])
    return get_list()


# ---------------------------------------------------------------- תקציר שיחה
@app.get("/api/summary")
def summary():
    if not S.log:
        raise HTTPException(400, "עדיין אין שיחה לייצא.")
    t = S.tracker.totals()
    parts = [f"תקציר שיחה - {datetime.now():%d/%m/%Y %H:%M}", f"מודל: {S.model} | חנות: {S.store}",
             f"משימות: {len(S.log)} | טוקנים: {t['input_tokens']}/{t['output_tokens']} | "
             f"עלות: ${t['actual_usd']:.6f} (תיאורטית ${t['theoretical_usd']:.6f})", ""]
    for i, (q, a) in enumerate(S.log, 1):
        parts += [f"--- משימה {i} ---", "קלט:", q, "", "תוצאה:", a, ""]
    name = f"session_summary_{datetime.now():%Y%m%d_%H%M}.txt"
    return PlainTextResponse("\n".join(parts), headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------------------------------------------------------------- קבצי הממשק
if config.WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def index(path: str):
        return FileResponse(config.WEB_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def no_ui():
        return PlainTextResponse("ממשק ה-Web לא נבנה. הריצו: cd web && npm install && npm run build",
                                 status_code=503)
