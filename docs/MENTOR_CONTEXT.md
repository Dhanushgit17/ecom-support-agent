# Mentor context — read this first in a new chat

## Who I am
Learning to build production-grade AI agents. Background: n8n / Zapier / Make automations (no-code). New to Python beyond basics. Enrolled in a Gen AI course; doing this project alongside it. Windows 11, Python 3.14, VS Code, Git installed.

## The project
E-commerce customer-support agent. Local repo: `C:\projects\ecom-support-agent`. Branch `main`. Pushed to `https://github.com/Dhanushgit17/ecom-support-agent` (public). Free stack only.

**Built so far (Phase 1 complete, steps 1–7; Phase 2 step 8 complete):**
- `tools.py`: 4 tools — `search_products` (returns matches + in-stock alternatives + a note to the model), `get_order_status`, `get_policy` (RAG), `cancel_order`. Plus `TOOL_SCHEMAS`.
- `agent_raw.py`: hand-written agent loop, no framework. `MAX_STEPS=8`, catches `groq.BadRequestError` for malformed tool calls, prints `[tool]` and `[result]` lines. System prompt requires `get_order_status` before asking to confirm a cancellation.
- `agent_langgraph.py`: same agent in LangGraph. `SqliteSaver` checkpointer (`checkpoints.db`), `interrupt_before=["tools"]`, human approval required for `cancel_order`. Its `chat()` uses `input()` — terminal only; the API does not import it.
- `api.py`: FastAPI wrapper. Endpoints `/health`, `/chat`, `/approve`. FastAPI object is named `api` (not `app`) because `agent_langgraph.app` is the compiled graph; imported as `graph`. Run with `uvicorn api:api --reload`. Sessions via `thread_id` in the request body. `NEEDS_APPROVAL = {"cancel_order"}` gate; `/chat` returns `needs_approval` + `pending_tool` and ends, `/approve` resumes or discards via `update_state(..., as_node="tools")`. `server_error()` logs the full traceback with an 8-char reference id and returns a generic 500.
- `rag.py`: chunk (one per bullet, heading-prefixed) → embed (ChromaDB built-in all-MiniLM, on-device) → retrieve top-3 with distance scores. Index in `chroma_db/` (gitignored, so a fresh clone must run `python rag.py` once).
- `data/`: `products.csv` (8 SKUs), `orders.json` (3 orders), `policies.md` (4 sections incl. "Damaged or wrong items").
- `evals/cases.jsonl`: 13 cases. Fields: `input`, `tool`, `must_not_call`, `max_tool_calls`, `must_contain`, `must_contain_any`, `must_not_contain`, `expected_fail`.
- `evals/run_evals.py`: runs each case against `agent_raw.run_agent`, collects tool calls from the message list, prints PASS/FAIL/XFAIL/XPASS with a reason line per failure, exits 1 if any real case fails. Has a `normalize()` that flattens curly quotes / non-breaking hyphens / narrow spaces before substring checks, and snapshots+restores `orders.json` in a `finally`.
- Current score: **12 passed, 0 failed, 1 expected failure.** Re-verified after a full venv rebuild on fresh package versions.
- `.gitattributes`: `* text=auto eol=lf` (stops the CRLF warnings, keeps Linux CI clean).
- `.gitignore`: `.venv/`, `.env`, `__pycache__/`, `*.pyc`, `checkpoints.db`, `checkpoints.db-shm`, `checkpoints.db-wal`, `chroma_db/`.
- `docs/GUIDEBOOK.md`: Chapters 1–8 in plain English, one per step, including every bug hit.
- `README.md`: what it is, what it does, how to run it, known limitations, roadmap. **Needs updating for the API.**

**Model/provider:** Groq free tier, model `openai/gpt-oss-120b` (set in `.env` as `MODEL`). Llama 3.3 is retired on Groq; use `client.models.list()` to check. `groq` resolves to 0.37.1 because `langchain-groq` pins an older version — normal, not a problem.

## Conventions we settled on
- One step at a time. Task → "done when" checkpoint → I paste output → mentor confirms before moving on.
- Design talk in plain English *before* code, every step. Analogies used: model = new employee who can't see the warehouse, tools = phone calls to the warehouse; LangGraph = n8n flowchart in Python; FastAPI endpoint = n8n Webhook node written by hand.
- Commit after every step, message style `stepN-short-description`. Guidebook chapter per step, committed separately.
- Run `git status` before `git add .`. Push with a bare `git push` (upstream already set).
- Always log what tools return (`[result]` print).
- Prompts shape behaviour; code enforces it (interrupts for risky tools).
- Eval expected values come from the data files, never from the agent's output.
- Verify destructive actions against the file on disk (`git status`), never against what the agent says it did.
- Test that a gate *opens* as well as that it closes — a gate blocking everything looks identical to a working one.
- I sometimes use VS Code's AI agent to make edits; mentor's rule is fine, but read the diff before committing.

## Known quirks of my setup
- **Save before running.** Cost me twice in Step 7 and once in Step 8. White dot on the VS Code tab = not on disk. `git status` before every run.
- **The editor is not the disk.** In Step 8 `api.py` looked like 85 lines in VS Code but `type api.py` showed 2 — the paste never landed. When code behaves as if it doesn't exist, check with `type <file>`, not the tab.
- **A venv cannot be moved.** Moving the project in Step 7 broke `pip.exe`, which has the old absolute path baked in. Never move a venv — delete it and rebuild from `requirements.txt`.
- **Two terminals.** Terminal 1 runs the server and nothing is ever typed into it; terminal 2 for git and everything else. Typing in the server terminal killed it three times in Step 8.
- **`--reload` does not watch `.env`.** Changing the API key needs a manual Ctrl+C and restart. Also `load_dotenv()` won't overwrite an existing environment variable — check `$env:GROQ_API_KEY` if a `.env` change seems to do nothing.
- Terminal sometimes drops quoted text after `git commit -m`; use single-word messages with hyphens.
- Pasting multiple commands at once causes `>>` continuation; paste one at a time. Never paste terminal *output* back into the terminal.
- Shift+Enter in VS Code sends code to an interactive `>>>` Python shell, not the file. `exit()` to leave.
- I've opened the wrong folder more than once; check the Explorer root shows `tools.py` directly. VS Code's "Recent" list can reopen an old path — type the path instead.
- Windows hides file extensions; create files in VS Code, not File Explorer.
- Don't install Ollama (storage/crash concern with n8n running locally). Use ChromaDB built-in embeddings and Groq's `openai/gpt-oss-20b` as the "small model" instead.
- Remember to restart the agent after editing any `.py` file (uvicorn `--reload` handles this for the server).
- JSONL is unforgiving — one missing `}` kills the whole eval run. Check first: `python -c "import json; [json.loads(l) for l in open('evals/cases.jsonl') if l.strip()]; print('ok')"`
- ChromaDB takes 20–30s to load, so the server is slow to reach `Application startup complete`. Not a hang.

## Full plan (15 steps)
Phase 1 Build: 1 setup ✅, 2 loop ✅, 3 tool design ✅, 4 LangGraph+memory ✅, 5 HITL ✅, 6 RAG ✅, 7 evals + GitHub + README ✅
Phase 2 Deploy: 8 FastAPI endpoint ✅, **9 Gradio UI**, 10 Hugging Face Spaces + Dockerfile + GitHub Actions running evals
Phase 3 Fine-tune: 11 pick task + build 300–500 example dataset, 12 Unsloth+LoRA on free Colab, 13 eval vs base model with our harness, 14 publish adapter to HF Hub, 15 swap into deployed agent

## Phase 3 target — refined by the Step 7 evals
The original assumption was "the model stretches policy instead of saying not-covered." The evals corrected it. Far-miss uncovered questions (gift wrapping, international shipping) are handled correctly — the model declines and offers a human. The failure is narrower:

**Situation question + adjacent process → stretch.** Test case: *"I ordered the wrong size. Can I exchange it for a different size?"* Returns chunks come back at distance ~1.39 and the model applies the returns policy to exchanges, which the document doesn't cover. Distance can't separate it (gift wrapping retrieved at 1.42 and was correctly declined). Still reproducible after the Step 8 venv rebuild on fresh package versions, so the baseline is stable.

Target answer: acknowledge it isn't covered, state what the policy does allow, hand off to a human. This is the suite's one XFAIL and the Phase 3 baseline.

## Known weaknesses to address later
- **No auth on any API endpoint.** Anyone who can reach the URL can cancel orders. Fine on `127.0.0.1`; must be fixed before or during Step 10.
- **`agent_langgraph.py` has no `groq.BadRequestError` handling**, unlike `agent_raw.py`. Chapter 6's malformed-tool-call bug can crash an HTTP request where the terminal agent recovers. The 500 handler stops the leak but there's no retry.
- **Nothing tests the API.** Evals still run against `agent_raw.run_agent`. Endpoints, sessions and the approval gate were verified by hand, once.
- **`/approve` assumes one pending approval per thread.** Two risky tools in one turn would report only the first name, and approving resumes both.
- **`checkpoints.db` grows forever.** No cleanup, expiry, or thread limit.
- Eval answer-checks are substring matching. One run had the agent invent "our shipping policy only covers deliveries within India" (not in the document) and still PASS, because the check only looks for a hand-off phrase. **Fix: LLM judge, planned for Step 13.**
- Harness is single-turn. Chapter 5's real bug (skipping confirmation on a second attempt) and "agent asks for the order ID first" can't be scored.
- No cost or latency tracking per case.
- Evals don't run automatically yet — that's Step 10 (GitHub Actions).

## Current position
**Step 8 complete.** `api.py` written and working: `/health`, `/chat`, `/approve`. Sessions via `thread_id` verified to survive a full server restart (answer came from `checkpoints.db` on disk). Threads verified isolated. Approval gate tested in both directions and checked against `data/orders.json` with `git status`, not against the agent's claim. Error handler tested with an invalid API key — browser got a 54-byte 500 with reference `bfae1768`, server log got the full traceback and the matching id. Chapter 8 written and committed.

**Next: Step 9 — Gradio UI.** A chat window in the browser that calls these endpoints. Needs to: generate a `thread_id` per browser session, render the markdown the API currently returns as escaped `\n`, and draw a real Yes/No control when `needs_approval` comes back true. The `/chat` response shape (`answer`, `thread_id`, `needs_approval`, `pending_tool`) was designed for exactly this.

Also outstanding: README needs updating for the API.

## How to resume
"You're my mentor on this project. Read MENTOR_CONTEXT.md and GUIDEBOOK.md, then continue from Current position using the same step-by-step teaching style: plain-English design first, one task at a time, wait for my output before moving on."