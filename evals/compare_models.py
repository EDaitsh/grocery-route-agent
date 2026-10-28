"""Eval 1: השוואת מודלים - זמן, איכות, אמינות ודיוק נתונים.

הרצה:  python evals/compare_models.py --models "model-a,model-b"
       python evals/compare_models.py --mock          (ללא רשת)
פלט:   evals/results/compare_models.csv
"""
from __future__ import annotations

import json
import time
from collections import Counter

from common import ROOT, base_args, load_json, models_from, write_csv

from agent import config
from agent.graph import run_agent
from agent.llm import LLM, AgentError, CostTracker, current_node
from agent.nodes import set_reporter

RUBRIC = (ROOT / "evals" / "rubric.md").read_text(encoding="utf-8")
JUDGE_SYSTEM = ("אתה שופט קפדני שמעריך פלט של אייג'נט מסלול קניות לפי ה-rubric הבא.\n\n" + RUBRIC +
                "\n\nהחזר JSON בלבד בפורמט שהוגדר.")


def judge(judge_llm: LLM, case: dict, state: dict) -> dict:
    payload = {
        "shopping_list": case["text"],
        "expected_zones_in_list_order": case["expected"],
        "computed_route": [{"label": s["label"], "products": [p["name"] for p in s["products"]]}
                           for s in (state.get("route") or {}).get("stops", [])],
        "agent_output": state.get("final_text", ""),
    }
    token = current_node.set("Judge")
    try:
        res = judge_llm.json("judge", JUDGE_SYSTEM, json.dumps(payload, ensure_ascii=False))
    finally:
        current_node.reset(token)
    keys = ("relevance", "accuracy", "completeness", "format")
    scores = {k: int(res.get(k, 0)) for k in keys}
    scores["judge_score"] = round(sum(scores.values()) / len(keys), 2)
    scores["judge_reason"] = str(res.get("reason", ""))[:200]
    return scores


def main():
    args = base_args("השוואת מודלים")
    set_reporter((lambda m: None) if args.quiet else print)
    cases = load_json("test_lists.json")
    judge_llm = LLM(model=config.JUDGE_MODEL, tracker=CostTracker())

    rows = []
    for model in models_from(args):
        for case in cases:
            print(f"\n=== {model} | {case['id']} ===")
            row = {"model": model, "case": case["id"], "judge_model": judge_llm.model}
            t0 = time.perf_counter()
            try:
                state, tracker = run_agent(case["text"], model=None if args.mock else model)
                row["seconds"] = round(time.perf_counter() - t0, 2)
                # השוואה כ-multiset של אזורים: כמה פריטים הגיעו לאזור הנכון (שם הפריט עצמו יכול להשתנות בנרמול)
                got = Counter(r["location"] for r in state.get("resolved", []))
                exp = Counter(case["expected"])
                hit = sum((got & exp).values())
                row["recall"] = round(hit / sum(exp.values()), 3)
                row["precision"] = round(hit / sum(got.values()), 3) if got else 0.0
                row["evaluator_passed"] = not state.get("eval_feedback")
                row["rewrite_attempts"] = state.get("attempts", 0)
                row["route_m"] = (state.get("route") or {}).get("total_m")
                tot = tracker.totals()
                row.update(input_tokens=tot["input_tokens"], output_tokens=tot["output_tokens"],
                           cost_actual_usd=round(tot["actual_usd"], 6),
                           cost_theoretical_usd=round(tot["theoretical_usd"], 6))
                row.update(judge(judge_llm, case, state))
                row["error"] = ""
            except AgentError as e:
                row["seconds"] = round(time.perf_counter() - t0, 2)
                row["error"] = str(e)
            rows.append(row)
            print({k: row.get(k) for k in ("seconds", "recall", "precision", "judge_score", "error")})

    path = write_csv("compare_models.csv", rows)
    print(f"\nנשמר: {path}")
    _summary(rows)


def _summary(rows):
    print(f"\n{'model':<45}{'sec':>7}{'recall':>8}{'judge':>7}{'$ actual':>11}")
    for model in dict.fromkeys(r["model"] for r in rows):
        rs = [r for r in rows if r["model"] == model and not r["error"]]
        if not rs:
            print(f"{model:<45} כל הריצות נכשלו")
            continue
        avg = lambda k: sum(r[k] for r in rs) / len(rs)
        print(f"{model:<45}{avg('seconds'):>7.1f}{avg('recall'):>8.2f}{avg('judge_score'):>7.2f}"
              f"{sum(r['cost_actual_usd'] for r in rs):>11.5f}")


if __name__ == "__main__":
    main()
