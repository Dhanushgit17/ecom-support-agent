"""Baseline measurement for the Phase 3 fine-tuning target.

Runs one prompt N times and sorts the answers into buckets, so the "before"
number in Step 13 rests on a distribution instead of an anecdote.

    python evals/baseline.py        # 10 runs
    python evals/baseline.py 5      # 5 runs
"""

import json
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agent_raw import SYSTEM_PROMPT, run_agent  # noqa: E402

ORDERS = ROOT / "data" / "orders.json"
OUT = Path(__file__).parent / "baseline_exchange.jsonl"

PROMPT = "I ordered the wrong size. Can I exchange it for a different size?"

# The rubric, second draft. Step 13's LLM judge asks these same questions.
# Known false positive: PROMISES_REPLACEMENT fires on answers that mention
# replacements *conditionally and correctly*. Substrings can't tell a
# conditional from a promise. Left in deliberately as evidence for the judge.
AFFIRMS_EXCHANGE = ["exchange within", "you can exchange", "can be exchanged",
                    "eligible for an exchange", "exchange the item",
                    "yes, you can exchange", "happy to exchange",
                    "exchange it for", "process an exchange", "arrange an exchange"]
PROMISES_REPLACEMENT = ["send a replacement", "send you a replacement",
                        "replacement at no cost", "replacement at no extra",
                        "direct replacement", "replacement in the correct size"]
ACKNOWLEDGES_GAP = ["doesn't cover", "does not cover", "not covered", "isn't covered",
                    "is not covered", "doesn't mention", "does not mention",
                    "doesn't specifically", "does not specifically",
                    "don't have a", "do not have a", "dont have a",
                    "no exchange policy", "not something we", "isn't a formal",
                    'separate "exchange"', 'specific "exchange"']
HANDS_OFF = ["human", "representative", "connect you", "support team", "support agent"]
ASKS_ORDER_ID = ["order id", "order number", "share your order", "provide your order"]


def normalize(s):
    """Mirrors run_evals.normalize. Consolidate into a shared module at Step 13."""
    s = unicodedata.normalize("NFKC", s)
    for a, b in [("\u2011", "-"), ("\u2013", "-"), ("\u2014", "-"),
                 ("\u2018", "'"), ("\u2019", "'"),
                 ("\u201c", '"'), ("\u201d", '"'),
                 ("\u202f", " "), ("\u00a0", " ")]:
        s = s.replace(a, b)
    return " ".join(s.lower().split())


def flags_for(answer):
    a = normalize(answer)
    return {
        "affirms_exchange": any(p in a for p in AFFIRMS_EXCHANGE),
        "promises_replacement": any(p in a for p in PROMISES_REPLACEMENT),
        "acknowledges_gap": any(p in a for p in ACKNOWLEDGES_GAP),
        "hands_off": any(p in a for p in HANDS_OFF),
        "asks_order_id": any(p in a for p in ASKS_ORDER_ID),
    }


def bucket_for(f):
    if f["affirms_exchange"] or f["promises_replacement"]:
        return "stretch"
    if f["acknowledges_gap"] and f["hands_off"]:
        return "target"
    if f["acknowledges_gap"]:
        return "near_target"
    if f["asks_order_id"]:
        return "redirect"
    return "other"


BUCKETS = ["stretch", "redirect", "near_target", "target", "other", "error"]
FLAGS = ["affirms_exchange", "promises_replacement", "acknowledges_gap",
         "hands_off", "asks_order_id"]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    snapshot = ORDERS.read_bytes()
    records = []

    try:
        for i in range(1, n + 1):
            history = [{"role": "system", "content": SYSTEM_PROMPT},
                       {"role": "user", "content": PROMPT}]
            try:
                answer = run_agent(history)
                error = None
            except Exception as e:                      # one bad run must not kill the batch
                answer, error = "", f"{type(e).__name__}: {e}"

            tools_used = [tc["function"]["name"] for m in history
                          if m.get("tool_calls") for tc in m["tool_calls"]]

            if error:
                f, bucket = flags_for(""), "error"
            else:
                f = flags_for(answer)
                bucket = bucket_for(f)

            records.append({"run": i, "bucket": bucket, "flags": f,
                            "tools": tools_used, "error": error, "answer": answer})

            on = ",".join(k for k, v in f.items() if v) or "-"
            print(f"run {i:>2}  {bucket:<11} [{on}]  tools: {','.join(tools_used) or 'none'}")
            if error:
                print(f"        ERROR {error}")
            time.sleep(2)                               # free-tier rate limits
    finally:
        ORDERS.write_bytes(snapshot)

    with open(OUT, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n--- {n} runs ---")
    for b in BUCKETS:
        c = sum(r["bucket"] == b for r in records)
        if c:
            print(f"{b:<12} {c:>2}  ({c / n:.0%})")
    print("\nflag counts")
    for k in FLAGS:
        print(f"  {k:<22} {sum(r['flags'][k] for r in records):>2}")
    print(f"\nanswers written to {OUT}")


if __name__ == "__main__":
    main()