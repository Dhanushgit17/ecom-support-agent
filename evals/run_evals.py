"""
Eval harness. Run after every change:  python evals/run_evals.py

Each case in cases.jsonl may have:
  input              the user message
  tool               a tool that must have been called
  max_tool_calls     upper bound on tool calls (catches loops)
  must_contain       phrases that must ALL appear in the answer
  must_contain_any   at least ONE of these must appear
  must_not_contain   phrases that must NOT appear
  expected_fail      true = known failure; reported as XFAIL, does not break the build
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from agent_raw import SYSTEM_PROMPT, run_agent  # noqa: E402

ORDERS = ROOT / "data" / "orders.json"


def normalize(s):
    """Lowercase and flatten typographic Unicode so tests don't break on curly quotes,
    non-breaking hyphens, or narrow spaces the model likes to emit."""
    s = s.lower()
    for bad, good in {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
                      "\u2011": "-", "\u2013": "-", "\u2014": "-",
                      "\u202f": " ", "\u00a0": " "}.items():
        s = s.replace(bad, good)
    return s


def check(c, answer, tools_used):
    """Return the list of reasons this case failed. Empty list = pass."""
    reasons = []
    a = normalize(answer)
    for p in c.get("must_contain", []):
        if normalize(p) not in a:
            reasons.append(f"missing phrase: {p!r}")
    if "must_contain_any" in c and not any(normalize(p) in a for p in c["must_contain_any"]):
        reasons.append(f"none of these present: {c['must_contain_any']}")
    for p in c.get("must_not_contain", []):
        if normalize(p) in a:
            reasons.append(f"forbidden phrase present: {p!r}")
    if "tool" in c and c["tool"] not in tools_used:
        reasons.append(f"tool {c['tool']} not called (called: {tools_used or 'none'})")
    if "must_not_call" in c and c["must_not_call"] in tools_used:
        reasons.append(f"forbidden tool called: {c['must_not_call']}")
    if "max_tool_calls" in c and len(tools_used) > c["max_tool_calls"]:
        reasons.append(f"{len(tools_used)} tool calls, max allowed {c['max_tool_calls']}")
    return reasons


def main():
    cases = [json.loads(l) for l in open(Path(__file__).parent / "cases.jsonl") if l.strip()]
    snapshot = ORDERS.read_bytes()  # cancel_order writes here; restored after the run
    passed = failed = xfail = xpass = 0
    try:
        for c in cases:
            history = [{"role": "system", "content": SYSTEM_PROMPT},
                       {"role": "user", "content": c["input"]}]
            answer = run_agent(history)
            tools_used = [tc["function"]["name"] for m in history
                          if m.get("tool_calls") for tc in m["tool_calls"]]
            reasons = check(c, answer, tools_used)
            ok = not reasons
            if c.get("expected_fail"):
                tag = "XPASS" if ok else "XFAIL"
                xpass += ok
                xfail += not ok
            else:
                tag = "PASS" if ok else "FAIL"
                passed += ok
                failed += not ok
            print(f"{tag} | {c['input']}   [{len(tools_used)} tool calls]")
            for r in reasons:
                print(f"      x {r}")
            print(f"      -> {answer[:120]!r}")
    finally:
        ORDERS.write_bytes(snapshot)

    print(f"\n{passed} passed, {failed} failed, {xfail} expected failures, {xpass} unexpected passes")
    if xpass:
        print("XPASS means a known failure now passes: remove its expected_fail flag so it becomes a real test.")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()