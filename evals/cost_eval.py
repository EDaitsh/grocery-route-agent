"""Eval 2: בדיקת עלויות - עלות כל נוד ועלות כוללת לכמה משימות נפוצות.

לכל מודל מוצגות גם העלות בפועל וגם העלות התיאורטית (למודלים חינמיים: לפי תעריף גרסת התשלום
של אותו מודל, או מודל הייחוס REFERENCE_PAID_MODEL).

הרצה:  python evals/cost_eval.py --models "free-model:free,paid-model"
פלט:   evals/results/cost_eval.csv
"""
from __future__ import annotations

from common import base_args, models_from, write_csv

from agent import pricing
from agent.graph import run_agent
from agent.llm import AgentError
from agent.nodes import set_reporter

TASKS = [
    ("quick_list", "חלב 3%, לחם אחיד, ביצים"),
    ("weekly_list", "עגבניות, מלפפונים, חלה, קוטג', חזה עוף, אורז, שמן קנולה, קפה נמס, "
                    "נייר טואלט, אקונומיקה, גלידה, במבה"),
    ("ambiguous_list", "חלב, לחם, שמן, גבינה"),
    ("out_of_scope", "תן לי מתכון לעוגת שוקולד"),
]


def main():
    args = base_args("בדיקת עלויות")
    set_reporter((lambda m: None) if args.quiet else print)
    models = models_from(args)
    if not args.mock and all(pricing.is_free(m) for m in models):
        print("אזהרה: לפי הדרישות יש לכלול לפחות מודל אחד בתשלום.")

    rows = []
    for model in models:
        for task_id, text in TASKS:
            print(f"\n=== {model} | {task_id} ===")
            try:
                _, tracker = run_agent(text, model=None if args.mock else model)
            except AgentError as e:
                rows.append({"model": model, "task": task_id, "node": "ERROR", "error": str(e)})
                continue
            for node, d in tracker.by_node().items():
                rows.append({"model": model, "task": task_id, "node": node, "calls": d["calls"],
                             "input_tokens": d["input_tokens"], "output_tokens": d["output_tokens"],
                             "cost_actual_usd": round(d["actual_usd"], 7),
                             "cost_theoretical_usd": round(d["theoretical_usd"], 7),
                             "is_free_model": pricing.is_free(tracker.records[0].model), "error": ""})
            t = tracker.totals()
            rows.append({"model": model, "task": task_id, "node": "TOTAL", "calls": t["calls"],
                         "input_tokens": t["input_tokens"], "output_tokens": t["output_tokens"],
                         "cost_actual_usd": round(t["actual_usd"], 7),
                         "cost_theoretical_usd": round(t["theoretical_usd"], 7), "error": ""})
            print(tracker.report())

    path = write_csv("cost_eval.csv", rows)
    print(f"\nנשמר: {path}")
    print(f"\n{'model':<45}{'$ actual (all tasks)':>22}{'$ theoretical':>16}")
    for model in models:
        tot = [r for r in rows if r["model"] == model and r["node"] == "TOTAL"]
        print(f"{model:<45}{sum(r['cost_actual_usd'] for r in tot):>22.6f}"
              f"{sum(r['cost_theoretical_usd'] for r in tot):>16.6f}")


if __name__ == "__main__":
    main()
