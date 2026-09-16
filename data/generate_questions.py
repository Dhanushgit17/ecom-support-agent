"""Pass 1 of dataset generation: customer messages only, no answers.

Questions and answers are generated separately so the model can't pattern-match
whole examples. Re-run to top up; existing questions are kept and shown to the
model so each batch differs from what's already there.

    python data/generate_questions.py
"""

import json
import os
import random
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

HERE = Path(__file__).parent
POLICIES = (HERE / "policies.md").read_text(encoding="utf-8")
OUT = HERE / "generated_questions.jsonl"

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = os.environ.get("MODEL", "openai/gpt-oss-120b")

TARGETS = {3: 8, 1: 8, 2: 8, 4: 8}
BATCH = 8

BRIEFS = {
    3: "questions the policy document fully answers, plus questions about a specific "
       "order status, cancelling an order, or searching for a product by price or type",
    1: "questions the policy document does NOT cover, but where a nearby policy section "
       "says something genuinely useful the customer could act on",
    2: "questions the policy document does NOT cover at all, where no nearby section "
       "says anything useful (loyalty schemes, invoicing, gift services, partnerships, "
       "payment methods, and similar)",
    4: "questions the policy document does NOT cover, where a nearby policy section "
       "exists but a condition in it (the 14-day window, unused and original packaging, "
       "unmarked soles, broken seals, already shipped) rules the customer out",
}

PROMPT = """You are writing test data for a customer-support agent at an Indian online store.

Here is the store's complete policy document:

<policies>
{policies}
</policies>

Write {n} customer messages of this kind: {brief}

Rules:
- Real customers, not survey questions. Vary the length: some are one blunt line, some
  ramble, some are polite, some are annoyed, some have a typo.
- Vary the products: clothing, footwear, electronics, kitchenware, accessories.
- Do NOT reuse a topic already listed below.
- Output ONLY a JSON array of strings. No preamble, no markdown fences, no numbering.

Already written, do not repeat these topics:
{existing}
"""


def load_existing():
    if not OUT.exists():
        return []
    return [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]


def ask(pattern, n, existing_texts):
    sample = random.sample(existing_texts, min(len(existing_texts), 40))
    prompt = PROMPT.format(policies=POLICIES, n=n, brief=BRIEFS[pattern],
                           existing="\n".join(f"- {t}" for t in sample) or "- (none yet)")
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0,          # variety matters more than precision here
    )
    text = r.choices[0].message.content.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    return json.loads(text)


def main():
    records = load_existing()
    counts = {p: sum(r["pattern"] == p for r in records) for p in TARGETS}
    print("starting from:", {p: counts[p] for p in sorted(counts)}, "\n")

    with open(OUT, "a", encoding="utf-8") as fh:
        while any(counts[p] < TARGETS[p] for p in TARGETS):
            pattern = min(TARGETS, key=lambda p: counts[p] / TARGETS[p])
            want = min(BATCH, TARGETS[pattern] - counts[pattern])
            existing_texts = [r["question"] for r in records]
            try:
                questions = ask(pattern, want, existing_texts)
            except Exception as e:
                print(f"  batch failed ({type(e).__name__}: {e}) - waiting 20s")
                time.sleep(20)
                continue

            seen = {r["question"].lower().strip() for r in records}
            added = 0
            for q in questions:
                q = str(q).strip()
                if not q or q.lower() in seen:
                    continue
                rec = {"pattern": pattern, "question": q}
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                records.append(rec)
                seen.add(q.lower())
                added += 1

            counts[pattern] += added
            total = sum(counts.values())
            print(f"pattern {pattern}: +{added}  (now {counts[pattern]}/{TARGETS[pattern]})  "
                  f"total {total}/{sum(TARGETS.values())}")
            time.sleep(3)

    print(f"\ndone - {sum(counts.values())} questions in {OUT}")


if __name__ == "__main__":
    main()