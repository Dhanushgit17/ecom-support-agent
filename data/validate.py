"""Validation rules for Step 11 training examples.

Written before any generation, so no rule gets softened to rescue work already done.
Self-test: every one of the 25 hand-written seeds must pass.

    python data/validate.py        # runs the self-test
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
POLICIES = (HERE / "policies.md").read_text(encoding="utf-8")
SEEDS = HERE / "seeds.md"

# Numbers that legitimately appear in answers without being policy figures.
ALLOWED_NUMBERS = {"1", "2", "3"}          # "two options", "3 weeks ago", list counts

WEBSITE_WORDS = ["my orders", "my account", "click", "button", "drop-down", "dropdown",
                 "menu", "select the order", "return/replace", "self-service",
                 "our website", "the app", "log in", "sign in", "checkout page"]

REPLACEMENT_WORDS = ["send a replacement", "send you a replacement", "arrange a replacement",
                     "replacement at no cost", "replacement at no extra",
                     "direct replacement", "ship you a replacement"]

# A replacement promise is only legitimate if the customer describes OUR error.
OUR_ERROR_WORDS = ["damaged", "crushed", "smashed", "broken", "faulty", "defect",
                   "wrong item", "wrong product", "not what i ordered", "sent me the wrong"]

HANDOFF = "connect you with a human representative"


def policy_numbers():
    """Every number that appears in policies.md, including both halves of ranges."""
    return set(re.findall(r"\d+", POLICIES))


POLICY_NUMS = policy_numbers()


def check(user, assistant, pattern):
    """Return a list of reasons this example is unusable. Empty list = valid."""
    reasons = []
    a = assistant.lower()
    u = user.lower()

    # 1. every number must come from the policy document or the customer's message
    user_nums = set(re.findall(r"\d+", user))
    for n in re.findall(r"\d+", assistant):
        if n in POLICY_NUMS or n in ALLOWED_NUMBERS or n in user_nums:
            continue
        if re.search(rf"ORD[-\u2011]?{n}", assistant, re.I):   # order ids are fine
            continue
        reasons.append(f"number {n} is not in policies.md or the question")

    # 2. no invented storefront
    for w in WEBSITE_WORDS:
        if w in a:
            reasons.append(f"describes a storefront UI: {w!r}")

    # 3. replacements only when the customer describes our error
    if any(w in a for w in REPLACEMENT_WORDS):
        if not any(w in u for w in OUR_ERROR_WORDS):
            reasons.append("promises a replacement without the customer reporting damage/wrong item")

    # 4. hand-off must match the pattern
    hands_off = HANDOFF in a
    if pattern in (1, 2, 4) and not hands_off:
        reasons.append(f"pattern {pattern} must end with the hand-off phrase")
    if pattern == 3 and hands_off:
        reasons.append("pattern 3 must not hand off")

    # 5. pattern 2 states no middle move
    if pattern == 2:
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", assistant.strip()) if s]
        if len(sentences) > 2:
            reasons.append(f"pattern 2 must be 2 sentences, got {len(sentences)}")

    return reasons


def parse_seeds():
    text = SEEDS.read_text(encoding="utf-8")
    blocks = re.split(r"### Seed ", text)[1:]
    out = []
    for b in blocks:
        num = int(re.match(r"(\d+)", b).group(1))
        pattern = int(re.search(r"pattern (\d)", b).group(1))
        user = re.search(r"\*\*User:\*\* (.+)", b).group(1).strip()
        assistant = re.search(r"\*\*Assistant:\*\* (.+)", b).group(1).strip()
        out.append((num, pattern, user, assistant))
    return out


def main():
    seeds = parse_seeds()
    print(f"parsed {len(seeds)} seeds\n")
    bad = 0
    for num, pattern, user, assistant in seeds:
        reasons = check(user, assistant, pattern)
        if reasons:
            bad += 1
            print(f"SEED {num} (pattern {pattern}) REJECTED")
            for r in reasons:
                print(f"    x {r}")
    print(f"\n{len(seeds) - bad} passed, {bad} rejected")
    if bad:
        print("\nA rejected seed means the RULE is wrong or the SEED is wrong. Decide which.")
        sys.exit(1)


if __name__ == "__main__":
    main()