"""Pass 2 of dataset generation: answers for the questions written in pass 1.

Every answer is checked by validate.check() before it is kept. A failed answer is
retried ONCE with its own rejection reasons attached; if it fails again it is parked
in rejected_answers.jsonl for a human to read. Nothing is silently discarded - the
parked file is the only place a systematic problem will show up.

Resumable: questions already answered or parked are skipped.

    python data/generate_answers.py 8     # first 8 only, for a trial
    python data/generate_answers.py       # everything remaining
"""

import json
import os
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path
from textwrap import dedent

from dotenv import load_dotenv
from groq import Groq

from validate import check, parse_seeds

load_dotenv()

HERE = Path(__file__).parent
POLICIES = (HERE / "policies.md").read_text(encoding="utf-8")
QUESTIONS = HERE / "generated_questions.jsonl"
OUT = HERE / "training_pairs.jsonl"
REJECTS = HERE / "rejected_answers.jsonl"

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = os.environ.get("MODEL", "openai/gpt-oss-120b")

# Lower than pass 1. Variety of wording still matters, but an answer that invents a
# number is useless, and questions already carry the diversity.
TEMPERATURE = 0.7

HANDOFF = "I can connect you with a human representative"

TEMPLATES = {
    1: dedent("""\
        The policy does not cover what they asked, but a nearby section offers a real
        alternative. Three moves, in order:
        1. Say plainly that our policies don't cover the thing they asked about.
        2. State what the policy DOES allow, with its actual conditions.
        3. Offer a human.
        Never imply the alternative resolves what they actually asked for. It is a
        different thing that they may or may not want."""),

    2: dedent("""\
        The policy does not cover this and there is nothing nearby worth offering.
        Two sentences, no more: say it isn't covered, then offer a human.
        Do not reach for a loosely related policy just to have something to say."""),

    3: dedent("""\
        The policy answers this, or a tool can. Answer it confidently and completely,
        with the conditions that apply. Do NOT offer a human - there is nothing to
        hand off.

        Carry every condition across. The policy's rules come with qualifications and
        dropping one turns a correct answer into a false promise:
        - "electronics with broken seals are not returnable, only exchangeable for
          defects" does NOT mean an exchange is available on request. If the customer
          hasn't said the item is faulty, say the exchange route exists only for a
          defect, and ask whether it is faulty.
        - "express: 1-2 business days in metro cities" is not a promise of 1-2 days
          everywhere.
        - a return needs all of: within 14 days, unused, original packaging.
        If a condition decides the answer and the customer hasn't told you whether they
        meet it, ask. Do not assume in their favour.
        State only the conditions that bear on what they asked. If they asked when a
        refund arrives, tell them when it arrives - don't recite the return conditions
        at them unprompted.

        You have four tools: look up a product, check an order's status, read the policy,
        and cancel an order. You cannot arrange an exchange, process a return, issue a
        refund, or change an address. Never say you are doing one of those - say what the
        policy provides and, where a human has to act, that the team will handle it.
        If the question is about a specific order or about finding a product, say you
        will look it up. Never invent an order status, a delivery date, a product name
        or a price."""),

    4: dedent("""\
        A policy section applies to their item, but something in their own message rules
        them out, and the policy offers no other route. Three moves:
        1. Name the condition they don't meet and say so directly.
        2. Explain why that closes the route - briefly, without lecturing.
        3. Offer a human, who may be able to make an exception.
        Do not offer a workaround the policy doesn't support. A human exception is the
        only honest thing left."""),
}

RULES = dedent("""\
    - Every number in your answer must appear in the policy document above or in the
      customer's message. Never invent a figure, a window, a fee or a timeframe.
    - You cannot see the storefront. Never mention website pages, buttons, menus,
      drop-downs, "My Orders", self-service flows, logging in, or the app.
    - Never claim to be doing something yourself ("let me arrange", "I'll process",
      "I'll proceed"). You can look things up; you cannot change an order.
    - Only promise a replacement if the customer has said the parcel arrived damaged or
      contained the wrong item. Otherwise do not mention replacements at all.
    - Write like a support agent talking to one person. No headings, no bullet lists,
      no numbered steps. Two to four sentences unless the pattern says otherwise.
    - Do not copy the examples. They show the shape; write this customer's answer.""")

PROMPT = """You are a customer-support agent at an Indian online store. Here is the
complete policy document. It is the only thing you know about the store:

<policies>
{policies}
</policies>

{template}
{handoff_rule}

Rules:
{rules}

Here are examples of this kind of answer, written by hand:

{examples}

Now write the answer to this customer message. Output ONLY the answer text - no
preamble, no quotes around it, no explanation of your reasoning.

Customer: {question}
"""

RETRY = """That answer was rejected by our validator for these reasons:

{reasons}

Rewrite it so none of those apply. Keep everything that was fine; change only what the
reasons point at. Output ONLY the corrected answer text.
"""


def handoff_rule(pattern):
    if pattern == 3:
        return ("\nThis answer must NOT offer to connect the customer to a human, and must "
                "not use the word 'representative'.")
    return (f"\nThis answer must end by offering a human, using this exact wording: "
            f'"{HANDOFF}" - you may continue the sentence naturally after it.')


def seed_examples(pattern, seeds, n=3):
    pool = [(u, a) for _, p, u, a in seeds if p == pattern]
    picked = random.sample(pool, min(n, len(pool)))
    return "\n\n".join(f"Customer: {u}\nAnswer: {a}" for u, a in picked)


def ask(messages):
    r = client.chat.completions.create(model=MODEL, messages=messages,
                                       temperature=TEMPERATURE)
    text = r.choices[0].message.content.strip()
    text = re.sub(r"^```(?:\w+)?|```$", "", text, flags=re.M).strip()
    return text.strip('"').strip()


def load_done():
    """Questions already answered or parked, so a re-run doesn't redo them."""
    done = set()
    for path in (OUT, REJECTS):
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    done.add(json.loads(line)["question"])
    return done


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    seeds = parse_seeds()
    questions = [json.loads(l) for l in
                 QUESTIONS.read_text(encoding="utf-8").splitlines() if l.strip()]
    done = load_done()
    todo = [q for q in questions if q["question"] not in done]
    if limit:
        todo = todo[:limit]

    print(f"{len(questions)} questions, {len(done)} already done, {len(todo)} this run\n")

    stats = Counter()
    rule_hits = Counter()

    out_fh = open(OUT, "a", encoding="utf-8")
    rej_fh = open(REJECTS, "a", encoding="utf-8")
    try:
        for i, rec in enumerate(todo, 1):
            pattern, question = rec["pattern"], rec["question"]
            prompt = PROMPT.format(policies=POLICIES, template=TEMPLATES[pattern],
                                   handoff_rule=handoff_rule(pattern), rules=RULES,
                                   examples=seed_examples(pattern, seeds),
                                   question=question)
            messages = [{"role": "user", "content": prompt}]

            try:
                answer = ask(messages)
            except Exception as e:
                print(f"{i:>3}. p{pattern} API ERROR ({type(e).__name__}) - waiting 20s")
                time.sleep(20)
                continue

            reasons = check(question, answer, pattern)
            retried = False

            if reasons:
                for r in reasons:
                    rule_hits[r.split(":")[0].split(" is not")[0][:40]] += 1
                retried = True
                messages += [
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": RETRY.format(
                        reasons="\n".join(f"- {r}" for r in reasons))},
                ]
                try:
                    answer = ask(messages)
                except Exception as e:
                    print(f"{i:>3}. p{pattern} retry API ERROR ({type(e).__name__})")
                    time.sleep(20)
                    continue
                reasons = check(question, answer, pattern)

            row = {"pattern": pattern, "question": question, "answer": answer,
                   "retried": retried}

            if reasons:
                row["reasons"] = reasons
                rej_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                rej_fh.flush()
                stats["parked"] += 1
                print(f"{i:>3}. p{pattern} PARKED   {reasons[0]}")
            else:
                out_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                out_fh.flush()
                stats["retry" if retried else "first"] += 1
                print(f"{i:>3}. p{pattern} {'ok (retry)' if retried else 'ok'}")

            time.sleep(2)                      # free-tier rate limits
    finally:
        out_fh.close()
        rej_fh.close()

    total = sum(stats.values())
    print(f"\n--- {total} answered ---")
    print(f"passed first try   {stats['first']}")
    print(f"passed on retry    {stats['retry']}")
    print(f"parked             {stats['parked']}")
    if rule_hits:
        print("\nrules that fired on the first attempt")
        for rule, n in rule_hits.most_common():
            print(f"  {n:>3}  {rule}")
    print(f"\nkept in {OUT}")
    if stats["parked"]:
        print(f"parked in {REJECTS} - read these")


if __name__ == "__main__":
    main()