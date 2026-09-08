# Mentor context — read this first in a new chat

## Who I am
Learning to build production-grade AI agents. Background: n8n / Zapier / Make automations (no-code). New to Python beyond basics. Enrolled in a Gen AI course; doing this project alongside it. Windows 11, Python 3.14, VS Code, Git installed.

## The project
E-commerce customer-support agent. Local repo: `C:\projects\ecom-support-agent`. Branch `main`. Pushed to `https://github.com/Dhanushgit17/ecom-support-agent` (public). Free stack only.

**Built so far (Phase 1, steps 1–7 — Phase 1 complete):**
- `tools.py`: 4 tools — `search_products` (returns matches + in-stock alternatives + a note to the model), `get_order_status`, `get_policy` (RAG), `cancel_order`. Plus `TOOL_SCHEMAS`.
- `agent_raw.py`: hand-written agent loop, no framework. `MAX_STEPS=8`, catches `groq.BadRequestError` for malformed tool calls, prints `[tool]` and `[result]` lines. System prompt requires `get_order_status` before asking to confirm a cancellation.
- `agent_langgraph.py`: same agent in LangGraph. `SqliteSaver` checkpointer (`checkpoints.db`), `interrupt_before=["tools"]`, human approval required for `cancel_order`.
- `rag.py`: chunk (one per bullet, heading-prefixed) → embed (ChromaDB built-in all-MiniLM, on-device) → retrieve top-3 with distance scores. Index in `chroma_db/` (gitignored, so a fresh clone must run `python rag.py` once).
- `data/`: `products.csv` (8 SKUs), `orders.json` (3 orders), `policies.md` (4 sections incl. "Damaged or wrong items").
- `evals/cases.jsonl`: 13 cases. Fields: `input`, `tool`, `must_not_call`, `max_tool_calls`, `must_contain`, `must_contain_any`, `must_not_contain`, `expected_fail`.
- `evals/run_evals.py`: runs each case against `agent_raw.run_agent`, collects tool calls from the message list, prints PASS/FAIL/XFAIL/XPASS with a reason line per failure, exits 1 if any real case fails. Has a `normalize()` that flattens curly quotes / non-breaking hyphens / narrow spaces before substring checks, and snapshots+restores `orders.json` in a `finally`.
- Current score: **12 passed, 0 failed, 1 expected failure.**
- `.gitattributes`: `* text=auto eol=lf` (stops the CRLF warnings, keeps Linux CI clean).
- `docs/GUIDEBOOK.md`: Chapters 1–7 in plain English, one per step, including every bug hit.
- `README.md`: rewritten — what it is, what it does, how to run it, known limitations, roadmap.

**Model/provider:** Groq free tier, model `openai/gpt-oss-120b` (set in `.env` as `MODEL`). Llama 3.3 is retired on Groq; use `client.models.list()` to check.

## Conventions we settled on
- One step at a time. Task → "done when" checkpoint → I paste output → mentor confirms before moving on.
- Design talk in plain English *before* code, every step. Analogies used: model = new employee who can't see the warehouse, tools = phone calls to the warehouse; LangGraph = n8n flowchart in Python.
- Commit after every step, message style `stepN-short-description`. Guidebook chapter per step, committed separately.
- Run `git status` before `git add .`. Push with a bare `git push` (upstream already set).
- Always log what tools return (`[result]` print).
- Prompts shape behaviour; code enforces it (interrupts for risky tools).
- Eval expected values come from the data files, never from the agent's output.
- I sometimes use VS Code's AI agent to make edits; mentor's rule is fine, but read the diff before committing.

## Known quirks of my setup
- **Save before running.** Cost me twice in Step 7 — an unsaved `cases.jsonl` meant the old suite ran and I read the results as new. White dot on the VS Code tab = not on disk. `git status` before every run; the file you edited must show as modified.
- Terminal sometimes drops quoted text after `git commit -m`; use single-word messages with hyphens.
- Pasting multiple commands at once causes `>>` continuation; paste one at a time.
- Shift+Enter in VS Code sends code to an interactive `>>>` Python shell, not the file. `exit()` to leave.
- I've opened the wrong folder more than once; check the Explorer root shows `tools.py` directly. VS Code's "Recent" list can reopen an old path — type the path instead.
- Windows hides file extensions; create files in VS Code, not File Explorer.
- Don't install Ollama (storage/crash concern with n8n running locally). Use ChromaDB built-in embeddings and Groq's `openai/gpt-oss-20b` as the "small model" instead.
- Remember to restart the agent after editing any `.py` file.
- JSONL is unforgiving — one missing `}` kills the whole eval run. Check first: `python -c "import json; [json.loads(l) for l in open('evals/cases.jsonl') if l.strip()]; print('ok')"`

## Full plan (15 steps)
Phase 1 Build: 1 setup ✅, 2 loop ✅, 3 tool design ✅, 4 LangGraph+memory ✅, 5 HITL ✅, 6 RAG ✅, 7 evals + GitHub + README ✅
Phase 2 Deploy: **8 FastAPI endpoint**, 9 Gradio UI, 10 Hugging Face Spaces + Dockerfile + GitHub Actions running evals
Phase 3 Fine-tune: 11 pick task + build 300–500 example dataset, 12 Unsloth+LoRA on free Colab, 13 eval vs base model with our harness, 14 publish adapter to HF Hub, 15 swap into deployed agent

## Phase 3 target — refined by the Step 7 evals
The original assumption was "the model stretches policy instead of saying not-covered." The evals corrected it. Far-miss uncovered questions (gift wrapping, international shipping) are handled correctly — the model declines and offers a human. The failure is narrower:

**Situation question + adjacent process → stretch.** Test case: *"I ordered the wrong size. Can I exchange it for a different size?"* Returns chunks come back at distance ~1.39 and the model applies the returns policy to exchanges, which the document doesn't cover. Three runs, three different stretches. Distance can't separate it (gift wrapping retrieved at 1.42 and was correctly declined).

Target answer: acknowledge it isn't covered, state what the policy does allow, hand off to a human. This is the suite's one XFAIL and the Phase 3 baseline.

## Known weaknesses to address later
- Eval answer-checks are substring matching. One run had the agent invent "our shipping policy only covers deliveries within India" (not in the document) and still PASS, because the check only looks for a hand-off phrase. Can't distinguish honest refusal from confident invention. **Fix: LLM judge, planned for Step 13.**
- Harness is single-turn. Chapter 5's real bug (skipping confirmation on a second attempt) and "agent asks for the order ID first" can't be scored.
- No cost or latency tracking per case.
- Evals don't run automatically yet — that's Step 10 (GitHub Actions).

## Current position
**Step 7 complete.** Evals written and green, Chapter 7 written, project moved to `C:\projects\ecom-support-agent`, branch renamed `master`→`main`, pushed to GitHub, README rewritten.

**Next: Step 8 — FastAPI endpoint.** Wrap the agent in a web endpoint so something other than a terminal can call it: a URL that takes a question and returns JSON. This is where sessions, concurrent users, and not leaking stack traces start to matter.

## How to resume
"You're my mentor on this project. Read MENTOR_CONTEXT.md and GUIDEBOOK.md, then continue from Current position using the same step-by-step teaching style: plain-English design first, one task at a time, wait for my output before moving on."