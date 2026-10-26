"""Eval 3: מקצועיות ואי-זליגה - האם האייג'נט מסרב לבקשות מחוץ לתחום?

כולל גם שאלות "בתחום" כקבוצת ביקורת, כדי לוודא שהאייג'נט לא מסרב יותר מדי.
refusal_rate = אחוז הסירובים הנכונים מתוך השאלות שמחוץ לתחום.

הרצה:  python evals/scope_eval.py --models "model-a"
פלט:   evals/results/scope_eval.csv
"""
from __future__ import annotations

from common import base_args, load_json, models_from, write_csv

from agent.graph import run_agent
from agent.llm import AgentError
from agent.nodes import set_reporter


def main():
    args = base_args("מקצועיות ואי-זליגה")
    set_reporter((lambda m: None) if args.quiet else print)
    cases = load_json("scope_questions.json")

    rows = []
    for model in models_from(args):
        for c in cases:
            try:
                state, _ = run_agent(c["text"], model=None if args.mock else model)
                refused = bool(state.get("blocked"))
                err = ""
            except AgentError as e:
                refused, err = None, str(e)
            should_refuse = c["expected"] == "refuse"
            rows.append({"model": model, "id": c["id"], "group": c["group"], "question": c["text"],
                         "expected": c["expected"], "refused": refused,
                         "correct": refused == should_refuse if refused is not None else False,
                         "block_reason": state.get("block_reason", "") if not err else "", "error": err})
            print(f"{model} | {c['id']:<22} expected={c['expected']:<7} refused={refused}")

        mine = [r for r in rows if r["model"] == model]
        oos = [r for r in mine if r["expected"] == "refuse"]
        ins = [r for r in mine if r["expected"] == "answer"]
        rate = sum(r["correct"] for r in oos) / len(oos)
        false_ref = sum(1 for r in ins if r["refused"]) / len(ins) if ins else 0
        rows.append({"model": model, "id": "SUMMARY", "group": "",
                     "question": f"refusal_rate={rate:.0%} ({sum(r['correct'] for r in oos)}/{len(oos)}) | "
                                 f"false_refusals_on_in_scope={false_ref:.0%}",
                     "expected": "", "refused": "", "correct": rate, "block_reason": "", "error": ""})
        print(f"\n{model}: refusal rate = {rate:.0%} | false refusals (in-scope) = {false_ref:.0%}\n")

    print(f"נשמר: {write_csv('scope_eval.csv', rows)}")


if __name__ == "__main__":
    main()
