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
import time
from pathlib import Path
from textwrap import dedent

from dotenv import load_dotenv
from groq import Groq

# Same directory, so this works when run as `python data/generate_questions.py`.
from validate import parse_seeds

load_dotenv()

HERE = Path(__file__).parent
POLICIES = (HERE / "policies.md").read_text(encoding="utf-8")
OUT = HERE / "generated_questions.jsonl"

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = os.environ.get("MODEL", "openai/gpt-oss-120b")

TARGETS = {3: 8, 1: 8, 2: 16, 4: 16}
BATCH = 8

# The 25 hand-written seeds count as "already written". Without them the model
# reproduced seed topics verbatim as fresh pattern 2 questions.
SEED_QUESTIONS = [(pattern, user) for _, pattern, user, _ in parse_seeds()]

# Each brief gives the model a test it can run on a question, examples of the kind,
# and near-misses that are NOT the kind. The first trial used one-line briefs that
# described the answer rather than the question, and every "pattern 1" came back
# as pattern 3.
BRIEFS = {
    3: dedent("""\
        Questions the policy document answers directly, or requests the agent can act on
        with its tools (order status, cancelling an order, searching products by price or
        type). Test: you could quote one sentence from the policy that settles it.

        Examples of this kind:
        - How long does express delivery take to Mumbai?
        - Can you ship to my PO box?
        - The box arrived crushed and the mug inside is smashed.
        - My order already shipped but I don't want it any more.
        - I ordered a 6-piece spice jar set and only 5 arrived.
          (a parcel that doesn't contain what was ordered is covered)
        - The TV I received has a broken seal, can I get a refund or an exchange?
          (the policy settles it: not returnable, exchange only for a defect)
        - Where is my order ORD-7783?
        - Do you have any wireless earbuds under Rs 3000?

        NOT this kind:
        - anything the policy never addresses (exchanges, warranties, gift wrap, store
          credit, invoices, address changes, delivery on a chosen date)
        - a customer describing their own situation where a condition blocks them and the
          policy offers no way forward (worn the shoes outside, bought it 3 weeks ago,
          opened the seal on something that works fine) - that is a separate kind"""),

    1: dedent("""\
        Questions about something the policy document never addresses, where one policy
        section nevertheless gives the customer a real alternative they could act on.
        Test: no sentence in the policy answers what the customer is asking for, but a
        nearby section offers something they could do instead. The customer's message
        contains NO detail that would disqualify them.

        Examples of this kind:
        - I ordered the wrong size. Can I exchange it for a different size?
          (no size exchanges in the policy; a return within 14 days is the alternative)
        - Do you offer a warranty on electronics?
          (no warranty; the defect route is the alternative)
        - Can I get store credit instead of a refund?
          (no store credit; the refund is the alternative)
        - Can I return a gift someone bought me without the receipt?
          (no proof-of-purchase rule; the 14-day return is the alternative)
        - The kurta fits but I don't like the colour, can I swap it?
          (no exchanges again, different product and wording)
        - Can I have this delivered on a particular date next week?
          (no scheduled delivery; express delivery is the nearest thing)

        NOT this kind:
        - Can you ship to a PO box? / How long is express to Delhi? / Is shipping free
          over Rs 999? - the policy answers these directly, leave them out
        - Can I return shoes I've worn outside? / Can I return something from 3 weeks
          ago? - the customer's own message rules them out, leave them out

        The same topic may recur (several exchange questions are welcome) but every
        message must be a different product, situation and wording."""),

    2: dedent("""\
        Questions about something the policy document does not cover at all, where no
        section comes anywhere near it. Test: nothing in the policy could even be
        offered as an alternative.

        Examples of this kind:
        - Do you do gift wrapping?
        - Can I get an invoice with my company's GST number on it?
        - Do you have a loyalty or points programme?

        This category is wide, and the obvious few topics are already used. Reach
        further: EMI and instalments, wallet and UPI support, international shipping,
        customs duties, referral codes, coupon stacking, subscriptions and repeat
        orders, product authenticity certificates, spare parts, recycling and trade-in,
        installation or assembly, app versus website accounts, marketplace sellers,
        affiliate or influencer programmes, careers, wholesale registration, custom or
        personalised items, packaging waste, delivery slot preferences by courier,
        insurance on high-value parcels, extended festival offers.

        NOT this kind: exchanges, warranties, store credit - those have a nearby
        section that could be offered instead."""),

    4: dedent("""\
        Questions where a policy section applies to the customer's item but a condition
        in it rules this customer out, and the policy offers no other route. Test: the
        customer's own message contains the disqualifying detail - the 14-day window has
        passed, the item was used or worn, the shoes went outside, the seal is broken on
        something that works fine, the order has already shipped - and the only thing
        left is asking a human for an exception.

        Examples of this kind:
        - Can I exchange these shoes? They're too tight but I've worn them outside.
        - Can I change the delivery address on an order that's already shipped?
        - I opened the box on my headphones but they work fine, can I return them?
        - Can I return something I bought 3 weeks ago?
        - I wore the dress once to a wedding, can I send it back?

        IMPORTANT - how these are worded: the customer tells you what happened and does
        not know it disqualifies them. They must NOT quote the policy, name the rule, or
        concede in advance.
        Write: "I wore them for a marathon last month and they fit fine, but I'd like to
        send them back."
        Do NOT write: "I ran a marathon in them and the 14-day period is over now, and I
        know used items aren't returnable, but is there anything you can do?"
        The disqualifying fact belongs in the story, not in a quoted rule.

        NOT this kind:
        - messages with no disqualifying detail (plain "can I exchange this?" or "do you
          offer a warranty?") - those belong elsewhere
        - a shipped order the customer wants to cancel - the policy gives a route there
          (refuse delivery, or return it), so that is answered directly
        - a broken seal where the customer hasn't said the item works - the exchange-for-
          a-defect route is still open, so that is answered directly"""),
}

PROMPT = """You are writing test data for a customer-support agent at an Indian online store.

Here is the store's complete policy document:

<policies>
{policies}
</policies>

Write {n} customer messages of this kind:

{brief}

Rules:
- Real customers, not survey questions. Vary the length: some are one blunt line, some
  ramble, some are polite, some are annoyed, some have a typo.
- Vary the products: clothing, footwear, electronics, kitchenware, accessories.
- Do NOT copy the examples above. They show the kind; write new messages.
- Do NOT reuse a topic already listed below.
- Output ONLY a JSON array of strings. No preamble, no markdown fences, no numbering.

Already written, do not repeat these topics:
{existing}
"""


def load_existing():
    if not OUT.exists():
        return []
    return [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]


def ask(pattern, n, written):
    """written: list of (pattern, question) covering seeds and generated questions."""
    same = [q for p, q in written if p == pattern]
    other = [q for p, q in written if p != pattern]
    # Same-pattern topics matter most - those are the ones the model repeats.
    sample = same[:40] + random.sample(other, min(len(other), max(0, 40 - len(same))))
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
    print(f"{len(SEED_QUESTIONS)} seeds loaded as existing topics")
    print("starting from:", {p: counts[p] for p in sorted(counts)}, "\n")

    with open(OUT, "a", encoding="utf-8") as fh:
        while any(counts[p] < TARGETS[p] for p in TARGETS):
            pattern = min(TARGETS, key=lambda p: counts[p] / TARGETS[p])
            want = min(BATCH, TARGETS[pattern] - counts[pattern])
            written = SEED_QUESTIONS + [(r["pattern"], r["question"]) for r in records]
            try:
                questions = ask(pattern, want, written)
            except Exception as e:
                print(f"  batch failed ({type(e).__name__}: {e}) - waiting 20s")
                time.sleep(20)
                continue

            seen = {q.lower().strip() for _, q in written}
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