# Mentor context — read this first in a new chat

## Who I am
Learning to build production-grade AI agents. Background: n8n / Zapier / Make automations (no-code). New to Python beyond basics. Enrolled in a Gen AI course; doing this project alongside it. Windows 11, Python 3.14, VS Code, Git installed. **No Docker locally** — storage constraint, n8n runs locally full-time.

## The project
E-commerce customer-support agent. Local repo: `C:\projects\ecom-support-agent`. Branch `main`. GitHub: `https://github.com/Dhanushgit17/ecom-support-agent` (public). **Live: `https://ecom-support-agent.onrender.com`**. Free stack only.

**Built so far — Phases 1 and 2 complete (steps 1–10); Step 11 in progress:**
- `tools.py`: 4 tools — `search_products` (returns matches + in-stock alternatives + a note to the model), `get_order_status`, `get_policy` (RAG), `cancel_order`. Plus `TOOL_SCHEMAS`.
- `agent_raw.py`: hand-written agent loop, no framework. `MAX_STEPS=8`, catches `groq.BadRequestError` for malformed tool calls, prints `[tool]` and `[result]` lines. System prompt requires `get_order_status` before asking to confirm a cancellation.
- `agent_langgraph.py`: same agent in LangGraph. `SqliteSaver` (`checkpoints.db`), `interrupt_before=["tools"]`, human approval for `cancel_order`. Its `chat()` uses `input()` — terminal only; `api.py` does not import it.
- `api.py`: FastAPI. `/health`, `/chat`, `/approve`. FastAPI object named `api` (the graph is imported as `graph`). `uvicorn api:api`. Sessions via `thread_id`. `NEEDS_APPROVAL = {"cancel_order"}`; `/chat` returns `needs_approval` + `pending_tool` and ends, `/approve` resumes or discards via `update_state(..., as_node="tools")`. `server_error()` logs the traceback with an 8-char id, returns a generic 500. All responses include `tool_calls` from `tool_names_used()`.
- `ui.py`: Gradio 6 chat UI. Talks to the API **over HTTP only**. `gr.State(value=new_thread_id)` (no parentheses — one thread per browser session). Approve/Reject buttons when `needs_approval`; textbox disabled while pending. Collapsed `gr.Accordion("Debug")` with thread id + tools called. Binds `0.0.0.0` on `int(os.environ.get("PORT", 7860))`.
- `Dockerfile`: python:3.12-slim, requirements layer first for caching, `RUN python rag.py` to build the index (gitignored so not in the repo), `CMD ["bash", "start.sh"]`. Nothing provider-specific.
- `start.sh`: uvicorn on `127.0.0.1:8000` backgrounded, a Python loop polling `/health` for up to 60s, then `python ui.py` in the foreground. The wait matters — ChromaDB takes 20–30s and Gradio would otherwise serve "could not reach the agent".
- `.dockerignore`: `.venv/`, `chroma_db/`, `checkpoints.db*`, `__pycache__/`, `.git/`, `.env`, `docs/`.
- `.github/workflows/evals.yml`: on push/PR to main + `workflow_dispatch`. Checkout → Python 3.12 → install → validate `cases.jsonl` → `python rag.py` → `python evals/run_evals.py` → `git diff --exit-code data/orders.json`. Uses `${{ secrets.GROQ_API_KEY }}` and sets `MODEL` inline.
- `rag.py`: chunk (one per bullet, heading-prefixed) → embed (ChromaDB built-in all-MiniLM, on-device) → retrieve top-3 with distances. Paths use `Path(__file__).parent`, so they work in the container unchanged.
- `data/`: `products.csv` (8 SKUs), `orders.json` (3 orders), `policies.md` (4 sections incl. "Damaged or wrong items").
- `evals/cases.jsonl`: 13 cases. `evals/run_evals.py`: runs against `agent_raw.run_agent`, PASS/FAIL/XFAIL/XPASS with reasons, exits 1 on real failures, `normalize()` for typographic characters, snapshots+restores `orders.json` in a `finally`.
- Current score: **12 passed, 0 failed, 1 expected failure** — green in CI on a clean Linux runner.
- Step 11 so far: `evals/baseline.py`, `data/seeds.md`, `data/validate.py`, `data/generate_questions.py`. See the Step 11 section below.
- `docs/GUIDEBOOK.md`: Chapters 1–10.
- `README.md`: live URL, architecture diagram, deployment section, five "things worth knowing", known limitations, roadmap.

**Deployment:** Render free tier, region Singapore, Docker runtime, auto-deploys from `main`. Env vars set in the dashboard: `GROQ_API_KEY`, `MODEL`. Sleeps after ~15 min idle (30–60s cold start) and the filesystem resets with it, so `checkpoints.db` and any `cancel_order` writes are ephemeral. **No auth — deliberate**, documented in the README.

**Model/provider:** Groq free tier, `openai/gpt-oss-120b` (via `MODEL`). Llama 3.3 is retired on Groq. `groq` resolves to 0.37.1 because `langchain-groq` pins an older version. **Gradio is 6.27.0** — newer than most tutorials and than the mentor's training data.

**Platform facts the mentor's training data got wrong (checked Sep 2026):**
- **Hugging Face Spaces now requires a paid plan** (PRO for personal) for Docker *and* Gradio SDKs. Only Static Spaces are free. Changed ~July 2026. The HF **Hub** (models, datasets, adapter publishing) is still free — Phase 3 steps 11/12/14 are unaffected.
- Fly.io: no free tier for new accounts. Railway: $5 trial credit only. Koyeb: sources disagree on whether free compute still exists.
- Render still has a real free Docker tier, no credit card.

## Conventions we settled on
- One step at a time. Task → "done when" checkpoint → I paste output → mentor confirms before moving on.
- Design talk in plain English *before* code. Analogies used: model = new employee who can't see the warehouse, tools = phone calls to the warehouse; LangGraph = n8n flowchart in Python; FastAPI endpoint = n8n Webhook node by hand; Dockerfile = a written recipe for a computer.
- Commit after every step, `stepN-short-description`. Guidebook chapter per step, committed separately.
- `git status` before `git add .`. Bare `git push`.
- Always log what tools return.
- Prompts shape behaviour; code enforces it.
- Eval expected values come from the data files, never from the agent's output.
- Verify destructive actions against the file on disk (`git status`), never against what the agent says it did.
- Test that a gate *opens* as well as that it closes.
- **When a prompt asks the model to classify or generate by category, give it a test it can run, worked examples, and near-misses that are explicitly not that category.** A one-line description of a category produces confident mislabelling.
- **Ask, don't guess.** `inspect.signature(SomeClass.__init__)` for libraries, `client.models.list()` for Groq, and web-search anything about a third party's pricing or free tier before planning around it.
- **Check a credential exists before theorising about why it's rejected.** An empty secret fails at the connection layer, not with a clean 401.
- When several coordinated edits are needed across files, mentor writes out the complete files rather than patch instructions.
- No local Docker, so every container change costs a 3–5 minute remote build. Read carefully rather than iterating.

## Known quirks of my setup
- **A missing package in a project that worked yesterday means the venv isn't active.** Fresh terminal = system Python 3.14 with none of the project's packages. `python -c "import sys; print(sys.executable)"` before theorising; `.\.venv\Scripts\Activate.ps1` to fix. Same family as the white dot: the environment isn't what you think it is.
- **Save before running.** White dot on the VS Code tab = not on disk. Has cost real time three times.
- **The editor is not the disk.** `api.py` once looked like 85 lines in VS Code while `type api.py` showed 2.
- **`type` mangles UTF-8** on Windows (em-dashes show as `â€”`), so it's reliable for checking structure but not content. `Get-Content -Encoding UTF8` reads it properly.
- **A venv cannot be moved.** `pip.exe` has the old absolute path baked in. Delete and rebuild from `requirements.txt`.
- **Three terminals.** 1 = uvicorn, 3 = Gradio, neither ever typed into. 2 = git and everything else.
- **`--reload` does not watch `.env`.** Manual restart needed. `load_dotenv()` won't overwrite an existing env var — check `$env:GROQ_API_KEY` if a `.env` change seems to do nothing.
- Gradio does not auto-reload; restart `python ui.py` after every edit.
- Line endings: `.sh` and `.yml` files need **LF**. Status bar bottom-right toggles it. `.gitattributes` converts on commit as a backstop.
- Terminal sometimes drops quoted text after `git commit -m`; single-word hyphenated messages.
- Paste one command at a time (`>>` continuation). Never paste terminal *output* back in.
- Shift+Enter in VS Code sends code to a `>>>` shell, not the file. `exit()` to leave.
- Windows hides file extensions; create files in VS Code.
- Don't install Ollama or Docker Desktop — storage.
- JSONL check: `python -c "import json; [json.loads(l) for l in open('evals/cases.jsonl') if l.strip()]; print('ok')"`
- ChromaDB takes 20–30s to load, so uvicorn is slow to reach `Application startup complete`. Not a hang.

## Full plan (15 steps)
Phase 1 Build: 1 setup ✅, 2 loop ✅, 3 tool design ✅, 4 LangGraph+memory ✅, 5 HITL ✅, 6 RAG ✅, 7 evals+GitHub+README ✅
Phase 2 Deploy: 8 FastAPI ✅, 9 Gradio UI ✅, 10 Docker + public URL + CI ✅
Phase 3 Fine-tune: **11 pick task + build 300–500 example dataset**, 12 Unsloth+LoRA on free Colab, 13 eval vs base model with our harness, 14 publish adapter to HF Hub, 15 swap into deployed agent

## Phase 3 target — and an important new finding
The original assumption was "the model stretches policy instead of saying not-covered." The Step 7 evals narrowed it: far-miss questions (gift wrapping at distance 1.42, international shipping at 1.13) are declined correctly with a hand-off. The failure is **situation question + adjacent process → stretch**.

The XFAIL case: *"I ordered the wrong size. Can I exchange it for a different size?"* Returns chunks retrieve at ~1.39 and the model applies the returns policy to exchanges, which the document doesn't cover.

**New finding from the first CI run (Step 10):** the failure mode is **not stable**. Three local runs all stretched the returns policy. The CI run did something different — *"Could you please share your order ID so I can check its status and see if it's eligible for..."* — treating an exchange question as an order question. Still XFAIL (no hand-off phrase), but a different wrong behaviour.

**Consequence for Step 11:** measure the baseline across several runs before writing a single training example, and make sure the dataset covers both failure modes, not just the stretch. A baseline measured once is noise. **Done — see the Step 11 section: 10 runs on the base prompt, 10 more with the rule stated in the prompt.**

Target answer: acknowledge it isn't covered, state what the policy does allow, hand off to a human.

## Step 11 in progress — the fine-tuning dataset

**Commits:** `step11-baseline-measurement`, `step11-prompt-ceiling-experiment`, `step11-first-four-seeds`, `step11-25-seeds`, `step11-seeds-cleanup`, `step11-validator`, `step11-question-generator`, `step11-briefs-with-examples`.

### Baseline — measured, not guessed
`evals/baseline.py` runs one prompt N times and buckets each answer (stretch / redirect / near_target / target / other / error), writing every answer to `evals/baseline_exchange.jsonl`. `--rules` appends `EXTRA_RULES` to the system prompt and writes to `baseline_exchange_rules.jsonl`.

- Base system prompt, 10 runs: **8 stretch, 1 redirect, 1 target.**
- Base prompt + the rule stated plainly in English, 10 runs: **7 stretch, 2 target, 1 other.**

That second number is the whole justification for fine-tuning: *telling* the model the rule gets it right 20% of the time. The prompt ceiling is real and now measured.

Two bucketing false negatives, kept as evidence for Step 13's LLM judge — substring matching cannot see either:
- base run 2 says "we can arrange a size exchange" → bucketed `redirect`, because the phrase list has "arrange an exchange" and not "a size exchange".
- rules run 6 is a target-quality answer → bucketed `other`, because "doesn't provide a specific exchange-for-a-different-size option" matches no `ACKNOWLEDGES_GAP` phrase.

### The four patterns
- **1** — not covered, but a nearby section offers a real alternative, and nothing in the customer's message disqualifies them. *This is the actual target behaviour.*
- **2** — not covered, nothing adjacent worth offering.
- **3** — covered: the policy answers it, or a tool can act on it. No hand-off.
- **4** — a section applies, but a condition in the customer's own message rules them out and no other route exists. Human exception only.

### Boundary rulings, settled against `policies.md` — keep these for the Step 13 judge
- **Broken seal on electronics:** if the customer says the item *works*, they have closed the exchange-for-a-defect route themselves → pattern 4. If they haven't said it works, that route is open and the policy answers it → pattern 3. One volunteered fact moves the same situation between buckets.
- **A missing piece from a set** → the parcel didn't contain what was ordered, so "Damaged or wrong items" applies → pattern 3.
- **The damaged section is about what arrived** (broken, missing, not what was ordered). **The seal clause is about the item's condition.** A working item in a tampered box is the seal clause's business, not the damaged section's.
- **A shipped order the customer wants to cancel** → pattern 3: the policy gives a route (refuse delivery, or return it).
- **Pattern 4 wording:** the customer tells the story and does *not* know it disqualifies them. They must never quote the policy or concede the rule in advance — otherwise the model learns to spot a confession rather than to apply a condition.

### Files
- `data/seeds.md` — 25 hand-written examples, **3/7/11/4** across patterns 1/2/3/4. Answer template: name the gap plainly → state what the policy *does* allow → never imply the workaround resolves the request → offer a human.
- `data/validate.py` — 5 rules, written *before* any generation so no rule could be softened to rescue work already done: every number must come from `policies.md` or the customer's message; no invented storefront UI; replacements only when the customer reports damage or a wrong item; hand-off present for 1/2/4 and absent for 3; pattern 2 capped at two sentences. Self-test = all 25 seeds must pass. Green.
- `data/generate_questions.py` — pass 1, **questions only**. Questions and answers are generated separately so the model can't pattern-match whole examples. Appends, tops up to `TARGETS`, and shows the model everything already written (seeds included, via `parse_seeds()` imported from `validate.py`).
- `data/generated_questions.jsonl` — **48 questions, 8/16/8/16. Untracked, deliberately**: generated questions need a human pass before they earn a place in the repo.

### What the trial runs taught
The first 32-question trial mislabelled pattern 1 completely — all eight were really pattern 3. The one-line briefs described the shape of the *answer* rather than giving a test that could be run on a *question*. The rewritten briefs give each pattern a test, worked examples, and near-misses explicitly marked as not that pattern. On the re-run, pattern 1 came back clean and the model even found a boundary by itself: seed 21 with "already shipped" removed, which correctly flips 4 → 1.

Second fix: `load_existing()` read only the generated file, so the 25 seed topics were invisible and pattern 2 reproduced them almost verbatim (7 of 8). With seeds counted as already-written, 16 pattern-2 topics across two batches came back with zero repeats.

**Pending:** cut the scratched-frying-pan pattern-4 line. "Used once, now looks a bit scratched" is a customer edging toward a defect claim, so it has two defensible answers — which makes it a poor training example.

### Next
1. **Pass 2 — the answers.** The hard half. `validate.py` has only ever seen hand-written answers; the design question is how generated answers get past those five rules without hand-editing 400 of them.
2. Merge and dedupe seeds with generated questions.
3. Scale to 300–500 once pass 2 is trustworthy.
4. Decide whether the dataset lives on HF Datasets (free) or just in the repo.

## Known weaknesses to address later
- **No auth on the live URL.** Deliberate and documented, but real.
- **Nothing tests the API, the UI, or the deployment.** CI covers `agent_raw.run_agent` only — it can be green while the deployed app is a blank page.
- **Eval answer-checks are substring matching.** One run had the agent invent "our shipping policy only covers deliveries within India" and still PASS, because the check only looks for a hand-off phrase. **Fix: LLM judge, Step 13.**
- **Harness is single-turn.** Chapter 5's real bug (skipping confirmation on a second attempt) can't be scored.
- **`agent_langgraph.py` has no `groq.BadRequestError` handling**, unlike `agent_raw.py`.
- **`/approve` assumes one pending approval per thread.**
- **State is ephemeral in production** — the container resets on every sleep cycle, so Chapter 4's persistence has nowhere durable to live on a free tier.
- **512MB RAM on Render.** It fits today; one more heavy dependency might not.
- No cost or latency tracking per eval case.

## Current position
**Step 10 complete. Phases 1 and 2 done.** Live at `https://ecom-support-agent.onrender.com` — verified in production: all four tools working, RAG index built during the image build, approval gate tested end to end over the public internet (warning → buttons → Approve → cancellation). CI green on GitHub Actions: 12 passed, 0 failed, 1 expected failure, plus the `git diff` check confirming the runner restores `orders.json`. Chapter 10 written, README updated with the live URL.

Mid-step, Hugging Face Spaces stopped being free for Docker. Moving the whole deployment to Render cost two lines (dropping the HF-specific `useradd` block, and reading `PORT` from the environment).

**Step 11 is roughly half done.** Baseline measured, target behaviour settled as a four-pattern rubric, 25 seeds hand-written, validator green, question generator working and trusted at 48 questions. What's left is pass 2 — the answers — then scaling to 300–500. Details in the Step 11 section above.

## How to resume
"You're my mentor on this project. Read MENTOR_CONTEXT.md and GUIDEBOOK.md, then continue from Current position using the same step-by-step teaching style: plain-English design first, one task at a time, wait for my output before moving on."