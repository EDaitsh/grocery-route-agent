"""בדיקות לשרת ה-Web, בלי רשת (מצב הדגמה):  pytest -q"""
import json
import os
import time

os.environ["AGENT_MOCK"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from agent import config, server  # noqa: E402

client = TestClient(server.app)


@pytest.fixture(autouse=True)
def weekly_list_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LIST_FILE", tmp_path / "weekly.txt")


def _wait_for(run, type_, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = [e for e in run.events if e["type"] == type_]
        if found:
            return found[-1]
        time.sleep(0.05)
    raise AssertionError(f"no '{type_}' event; got {[e['type'] for e in run.events]}")


def _sse_events(run_id):
    with client.stream("GET", f"/api/runs/{run_id}/events") as r:
        body = "".join(r.iter_text())
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def test_run_streams_nodes_and_stops_for_save_approval():
    run_id = client.post("/api/runs", json={"text": "חלב, עגבניות, גלידה"}).json()["run_id"]
    run = server.S.runs[run_id]
    hitl = _wait_for(run, "hitl")
    while hitl["payload"]["kind"] != "confirm_save":   # שאלות הבהרה: בוחרים את האפשרות הראשונה
        answers = {str(q["idx"]): q["options"][0]["id"] for q in hitl["payload"]["questions"]}
        client.post(f"/api/runs/{run_id}/answer", json={"answer": answers})
        time.sleep(0.2)
        hitl = _wait_for(run, "hitl")
    assert client.post("/api/runs", json={"text": "לחם"}).status_code == 409   # משימה אחת בכל רגע
    client.post(f"/api/runs/{run_id}/answer", json={"answer": False})

    events = _sse_events(run_id)
    nodes = [e["name"] for e in events if e["type"] == "node"]
    assert nodes[0] == "Input_Guardrail" and "Plan_Route_Tool" in nodes and nodes[-1] == "HITL_Save"
    result = next(e for e in events if e["type"] == "result")
    assert result["route"]["path"] and result["route"]["stops"][-1]["node"] == "קופות"
    assert result["saved_path"] is None
    assert events[-1]["type"] == "end"
    assert client.get("/api/state").json()["busy"] is False


def test_out_of_scope_is_refused_and_cancel_works():
    run_id = client.post("/api/runs", json={"text": "כתוב לי שיר על הים"}).json()["run_id"]
    events = _sse_events(run_id)
    assert next(e for e in events if e["type"] == "result")["blocked"]

    run_id = client.post("/api/runs", json={"text": "חלב, טחינה"}).json()["run_id"]
    _wait_for(server.S.runs[run_id], "hitl")
    client.post(f"/api/runs/{run_id}/cancel")
    assert [e["type"] for e in _sse_events(run_id)][-2:] == ["cancelled", "end"]


def test_bad_settings_return_clear_error():
    r = client.post("/api/settings", json={"store": "no_such_store"})
    assert r.status_code == 400 and "לא נמצאה" in r.json()["error"]


def test_weekly_list_and_map():
    client.post("/api/list", json={"items": ["חלב, לחם", "טחינה"]})
    assert client.get("/api/list").json()["items"] == ["חלב", "לחם", "טחינה"]
    assert client.delete("/api/list/1").json()["items"] == ["חלב", "טחינה"]
    assert client.delete("/api/list").json()["items"] == []
    m = client.get("/api/map").json()
    assert m["kind"] == "grid" and m["walls"] and "קופות" in m["zones"]
