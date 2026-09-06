"""
STEP 5: Minimal eval harness. Run after every change: python evals/run_evals.py
Scores each case on: correct tool called + required phrases present.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_raw import SYSTEM_PROMPT, run_agent  # noqa: E402

cases = [json.loads(l) for l in open(Path(__file__).parent / "cases.jsonl")]
passed = 0
for c in cases:
    history = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": c["input"]}]
    answer = run_agent(history).lower()
    tools_used = [tc["function"]["name"] for m in history if m.get("tool_calls") for tc in m["tool_calls"]]
    ok = all(p.lower() in answer for p in c.get("must_contain", []))
    ok &= not any(p.lower() in answer for p in c.get("must_not_contain", []))
    if "tool" in c:
        ok &= c["tool"] in tools_used
    passed += ok
    print(f"{'PASS' if ok else 'FAIL'} | {c['input']}\n      -> {answer[:120]}")
print(f"\n{passed}/{len(cases)} passed")
sys.exit(0 if passed == len(cases) else 1)
