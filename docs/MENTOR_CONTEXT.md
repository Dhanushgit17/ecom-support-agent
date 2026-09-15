# Mentor context — read this first in a new chat

## Who I am
Learning to build production-grade AI agents. Background: n8n / Zapier / Make automations (no-code). New to Python beyond basics. Enrolled in a Gen AI course; doing this project alongside it. Windows 11, Python 3.14, VS Code, Git installed.

## The project
E-commerce customer-support agent. Local repo: `C:\projects\ecom-support-agent`. Branch `main`. Pushed to `https://github.com/Dhanushgit17/ecom-support-agent` (public). Free stack only.

**Built so far (Phase 1 complete, steps 1–7; Phase 2 steps 8–9 complete):**
- `tools.py`: 4 tools — `search_products` (returns matches + in-stock alternatives + a note to the model), `get_order_status`, `get_policy` (RAG), `cancel_order`. Plus `TOOL_SCHEMAS`.
- `agent_raw.py`: hand-written agent loop, no framework. `MAX_STEPS=8`, catches `groq.BadRequestError` for malformed tool calls, prints `[tool]` and `[result]` lines. System prompt requires `get_order_status` before asking to confirm a cancellation.
- `agent_langgraph.py`: same agent in LangGraph. `SqliteSaver` checkpointer (`checkpoints.db`), `interrupt_before=["tools"]`, human approval required for `cancel_order`. Its `chat()` uses `input()` — terminal only; `api.py` does not import it.
- `api.py`: FastAPI wrapper. Endpoints `/health`, `/chat`, `/approve`. FastAPI object is named `api` (not `app`) because `agent_langgraph.app` is the compiled graph, imported here as `graph`. Run with `uvicorn api:api --reload`. Sessions via `thread_id` in the request body. `NEEDS_APPROVAL = {"cancel_order"}` gate; `/chat` returns `needs_approval` + `pending_tool` and ends, `/approve` resumes or discards via `update_state(..., as_node="tools")`. `server_error()` logs the full traceback with an 8-char reference id and returns a generic 500. Every response includes `tool_calls` (all tools used on the thread, via `tool_names_used()`).
- `ui.py`: Gradio 6 chat UI on port 7860. Talks to the API **over HTTP only** — never imports the agent, so the API stays honest. `gr.State(value=new_thread_id)` (no parentheses — one thread per browser session). Approve/Reject buttons appear when `needs_approval` is true and the textbox is disabled while pending. Collapsed `gr.Accordion("Debug")` shows the thread id and tools called. Three `except` branches for ConnectionError / Timeout / HTTPError.
- `rag.py`: chunk (one per bullet, heading-prefixed) → embed (ChromaDB built-in all-MiniLM, on-device) → retrieve top-3 with distance scores. Index in `chroma_db/` (gitignored, so a fresh clone must run `python rag.py` once).
- `data/`: `products.csv` (8 SKUs), `orders.json` (3 orders), `policies.md` (4 sections incl. "Damaged or wrong items").
- `evals/cases.jsonl`: 13 cases. Fields: `input`, `tool`, `must_not_call`, `max_tool_calls`, `must_contain`, `must_contain_any`, `must_not_contain`, `expected_fail`.
- `evals/run_evals.py`: runs each case against `agent_raw.run_agent`, collects tool calls from the message list, prints PASS/FAIL/XFAIL/XPASS with a reason line per failure, exits 1 if any real case fails. Has a `normalize()` that flattens curly quotes / non-breaking hyphens / narrow spaces before substring checks, and snapshots+restores `orders.json` in a `finally`.
- Current score: **12 passed, 0 failed, 1 expected failure.** Re-verified after a full venv rebuild on fresh package versions.
- `.gitattributes`: `* text=auto eol=lf`.
- `.gitignore`: `.venv/`, `.env`, `__pycache__/`, `*.pyc`, `checkpoints.db`, `checkpoints.db-shm`, `checkpoints.db-wal`, `chroma_db/`.
- `docs/GUIDEBOOK.md`: Chapters 1–9, one per step, including every bug hit.
- `README.md`: rewritten for the API + UI — architecture diagram, two-process run instructions, four "things worth knowing" lessons, known limitations, roadmap.

**Model/provider:** Groq free tier, model `openai/gpt-oss-120b` (set in `.env` as `MODEL`). Llama 3.3 is retired on Groq; use `client.models.list()` to check. `groq` resolves to 0.37.1 because `langchain-groq` pins an older version — normal. **Gradio is 6.27.0** — newer than most tutorials and than the mentor's training data; check signatures rather than trusting examples.

## Conventions we settled on
- One step at a time. Task → "done when" checkpoint → I paste output → mentor confirms before moving on.
- Design talk in plain English *before* code, every step. Analogies used: model = new employee who can't see the warehouse, tools = phone calls to the warehouse; LangGraph = n8n flowchart in Python; FastAPI endpoint = n8n Webhook node written by hand.
- Commit after every step, message style `stepN-short-description`. Guidebook chapter per step, committed separately.
- Run `git status` before `git add .`. Push with a bare `git push` (upstream already set).
- Always log what tools return (`[result]` print).
- Prompts shape behaviour; code enforces it (interrupts for risky tools).
- Eval expected values come from the data files, never from the agent's output.
- Verify destructive actions against the file on disk (`git status`), never against what the agent says it did.
- Test that a gate *opens* as well as that it closes.
- **Ask libraries, don't guess.** `inspect.signature(SomeClass.__init__)` for Python packages, `client.models.list()` for Groq. Has caught two version mismatches so far.
- When several coordinated edits are needed across files, mentor writes out the complete files rather than patch instructions — hand-patching is where the paste failures happen.
- I sometimes use VS Code's AI agent to make edits; mentor's rule is fine, but read the diff before committing.

## Known quirks of my setup
- **Save before running.** Cost me three times now. White dot on the VS Code tab = not on disk.
- **The editor is not the disk.** In Step 8 `api.py` looked like 85 lines in VS Code but `type api.py` showed 2 — the paste never landed. When code behaves as if it doesn't exist, check with `type <file>`.
- **A venv cannot be moved.** Moving the project in Step 7 broke `pip.exe`, which has the old absolute path baked in. Never move a venv — delete it and rebuild from `requirements.txt`.
- **Three terminals now.** 1 = uvicorn, 3 = Gradio, neither ever typed into. 2 = git and everything else. Typing in a server terminal killed it three times in Step 8.
- **`--reload` does not watch `.env`.** Changing the API key needs a manual Ctrl+C and restart. Also `load_dotenv()` won't overwrite an existing environment variable — check `$env:GROQ_API_KEY` if a `.env` change seems to do nothing.
- Gradio does **not** auto-reload; restart `python ui.py` after every edit.
- Terminal sometimes drops quoted text after `git commit -m`; use single-word messages with hyphens.
- Pasting multiple commands at once causes `>>` continuation; paste one at a time. Never paste terminal *output* back into the terminal.
- Shift+Enter in VS Code sends code to an interactive `>>>` Python shell, not the file. `exit()` to leave.
- I've opened the wrong folder more than once; check the Explorer root shows `tools.py` directly.
- Windows hides file extensions; create files in VS Code, not File Explorer.
- Don't install Ollama (storage/crash concern with n8n running locally). Use ChromaDB built-in embeddings and Groq's `openai/gpt-oss-20b` as the "small model" instead.
- JSONL is unforgiving — one missing `}` kills the whole eval run. Check first: `python -c "import json; [json.loads(l) for l in open('evals/cases.jsonl') if l.strip()]; print('ok')"`
- ChromaDB takes 20–30s to load, so uvicorn is slow to reach `Application startup complete`. Not a hang.

## Full plan (15 steps)
Phase 1 Build: 1 setup ✅, 2 loop ✅, 3 tool design ✅, 4 LangGraph+memory ✅, 5 HITL ✅, 6 RAG ✅, 7 evals + GitHub + README ✅
Phase 2 Deploy: 8 FastAPI endpoint ✅, 9 Gradio UI ✅, **10 Hugging Face Spaces + Dockerfile + GitHub Actions running evals**
Phase 3 Fine-tune: 11 pick task + build 300–500 example dataset, 12 Unsloth+LoRA on free Colab, 13 eval vs base model with our harness, 14 publish adapter to HF Hub, 15 swap into deployed agent

## Phase 3 target — refined by the Step 7 evals
The original assumption was "the model stretches policy instead of saying not-covered." The evals corrected it. Far-miss uncovered questions (gift wrapping, international shipping) are handled correctly — the model declines and offers a human. The failure is narrower:

**Situation question + adjacent process → stretch.** Test case: *"I ordered the wrong size. Can I exchange it for a different size?"* Returns chunks come back at distance ~1.39 and the model applies the returns policy to exchanges, which the document doesn't cover. Distance can't separate it (gift wrapping retrieved at 1.42 and was correctly declined). Still reproducible after the Step 8 venv rebuild on fresh package versions, so the baseline is stable.

Target answer: acknowledge it isn't covered, state what the policy does allow, hand off to a human. This is the suite's one XFAIL and the Phase 3 baseline.

## Known weaknesses to address later
- **No authentication anywhere.** Now urgent rather than theoretical: Step 10 makes the URL public, and anyone who can reach it can cancel orders. Needs a decision in Step 10, not a note.
- **Gradio publishes its own API on 7860** ("Use via API" at the bottom of the page). Two APIs exist, not one.
- **Nothing tests the API or the UI.** Evals still run against `agent_raw.run_agent` only. Endpoints, sessions, the approval gate and the UI were verified by hand, once each.
- **`agent_langgraph.py` has no `groq.BadRequestError` handling**, unlike `agent_raw.py`. A malformed tool call crashes an HTTP request where the terminal agent recovers. The 500 handler stops the leak but there's no retry.
- **`/approve` assumes one pending approval per thread.** Two risky tools in one turn would report only the first name, and approving resumes both.
- **`checkpoints.db` grows one thread per browser session**, forever. No cleanup, expiry or limit.
- **The chat window empties on refresh** while the server still remembers the thread. Reloading visible history from the server on page load is possible and not done.
- Eval answer-checks are substring matching. One run had the agent invent "our shipping policy only covers deliveries within India" (not in the document) and still PASS, because the check only looks for a hand-off phrase. **Fix: LLM judge, planned for Step 13.**
- Harness is single-turn. Chapter 5's real bug (skipping confirmation on a second attempt) and "agent asks for the order ID first" can't be scored.
- No cost or latency tracking per case.
- Evals don't run automatically yet — that's Step 10 (GitHub Actions).

## Current position
**Step 9 complete.** Gradio UI working end to end: per-session threads verified isolated across two browser tabs, markdown rendering, Approve/Reject buttons wired to `/approve` with the textbox locked while pending, both approval directions verified against `data/orders.json` with `git status`, Debug accordion showing thread id and tool calls. `api.py` gained `tool_names_used()` so `tool_calls` is in every response again. Chapter 9 written, README rewritten for the API + UI.

**Next: Step 10 — Docker + Hugging Face Spaces + GitHub Actions.** The hard parts, roughly in order:
1. **Two processes into one container.** uvicorn on 8000 and Gradio on 7860 both need to run, but HF Spaces exposes one port (7860). Options: one entrypoint starting both, or have Gradio mount the FastAPI app — which would undo the HTTP-client separation deliberately built in Step 9. Worth a design conversation before code.
2. **`chroma_db/` is gitignored**, so the image build must run `python rag.py` itself.
3. **`GROQ_API_KEY` becomes a Spaces secret**, not a `.env` file.
4. **Auth.** The URL becomes public and `cancel_order` writes to disk. Decide: Gradio's built-in `auth=`, a shared token on the API, or make `cancel_order` a no-op in the deployed demo.
5. **GitHub Actions running the evals on push.** Needs the Groq key as a repo secret and `python rag.py` in the workflow. The runner restores `data/orders.json` in a `finally`, so a CI run shouldn't dirty the checkout.

## How to resume
"You're my mentor on this project. Read MENTOR_CONTEXT.md and GUIDEBOOK.md, then continue from Current position using the same step-by-step teaching style: plain-English design first, one task at a time, wait for my output before moving on."