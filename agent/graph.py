"""הגדרת ה-Workflow ב-LangGraph והפעלתו (כולל טיפול ב-interrupt של HITL).

START -> Input_Guardrail -+-> Refuse -> END
                          +-> Parse_List -> RAG_Lookup -> Match_Classify -> Confidence_Gate
                                Confidence_Gate -+-> HITL_Clarify -+
                                                 +-----------------+-> Plan_Route_Tool
                                Plan_Route_Tool -> Write_Instructions -> Evaluator
                                Evaluator -+-> Write_Instructions (לולאת תיקון, עד MAX_REWRITE_ATTEMPTS)
                                           +-> Finalize -> HITL_Save -> END
"""
from __future__ import annotations

import uuid
from typing import Callable, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from . import config as cfg
from . import nodes as n
from .llm import LLM, CostTracker


def build_graph():
    g = StateGraph(n.AgentState)
    g.add_node("guardrail", n.guardrail)
    g.add_node("refuse", n.refuse)
    g.add_node("parse_list", n.parse_list)
    g.add_node("rag_lookup", n.rag_lookup)
    g.add_node("match_items", n.match_items)
    g.add_node("confidence_gate", n.confidence_gate)
    g.add_node("clarify", n.clarify)
    g.add_node("plan_route", n.plan_route)
    g.add_node("write_instructions", n.write_instructions)
    g.add_node("evaluator", n.evaluator)
    g.add_node("finalize", n.finalize)
    g.add_node("confirm_save", n.confirm_save)

    g.add_edge(START, "guardrail")
    g.add_conditional_edges("guardrail", lambda s: "refuse" if s.get("blocked") else "parse_list",
                            ["refuse", "parse_list"])
    g.add_edge("refuse", END)
    g.add_edge("parse_list", "rag_lookup")
    g.add_edge("rag_lookup", "match_items")
    g.add_edge("match_items", "confidence_gate")
    g.add_conditional_edges("confidence_gate", n.route_after_gate, ["clarify", "plan_route", "finalize"])
    g.add_conditional_edges("clarify", n.route_after_clarify, ["plan_route", "finalize"])
    g.add_edge("plan_route", "write_instructions")
    g.add_edge("write_instructions", "evaluator")
    g.add_conditional_edges("evaluator", n.route_after_eval, ["write_instructions", "finalize"])
    g.add_edge("finalize", "confirm_save")
    g.add_edge("confirm_save", END)
    return g.compile(checkpointer=MemorySaver())


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


# HITL handler: מקבל את ה-payload של ה-interrupt ומחזיר את התשובה לחידוש הגרף
HitlHandler = Callable[[dict], object]


def auto_hitl(payload: dict):
    """תשובות אוטומטיות למצב לא-אינטראקטיבי (evals): בוחר את האפשרות הראשונה ולא שומר קבצים."""
    if payload["kind"] == "clarify":
        out = {}
        for q in payload["questions"]:
            out[str(q["idx"])] = q["options"][0]["id"]
        return out
    return False


def run_agent(user_input: str, model: Optional[str] = None, store: Optional[str] = None,
              hitl: HitlHandler = auto_hitl, tracker: Optional[CostTracker] = None,
              mock: Optional[bool] = None) -> tuple[dict, CostTracker]:
    """מריץ את הגרף עד הסוף. מחזיר (state סופי, מעקב עלויות)."""
    tracker = tracker or CostTracker()
    llm = LLM(model=model, tracker=tracker, mock=mock)
    run_cfg = {"configurable": {"thread_id": str(uuid.uuid4()), "llm": llm,
                                "store": store or cfg.DEFAULT_STORE},
               "run_name": "grocery-route-agent",
               "tags": [llm.model], "metadata": {"model": llm.model}}
    graph = get_graph()
    inp: object = {"user_input": user_input, "attempts": 0}
    while True:
        interrupted = None
        for chunk in graph.stream(inp, run_cfg, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupted = chunk["__interrupt__"][0].value
        if interrupted is None:
            break
        inp = Command(resume=hitl(interrupted))
    return graph.get_state(run_cfg).values, tracker
