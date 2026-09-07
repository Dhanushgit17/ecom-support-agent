# Mentor context — read this first in a new chat

## Who I am
Learning to build production-grade AI agents. Background: n8n / Zapier / Make automations (no-code). New to Python beyond basics. Enrolled in a Gen AI course; doing this project alongside it. Windows 11, Python 3.14, VS Code, Git installed.

## The project
E-commerce customer-support agent. Repo: local at `C:\Users\Laptop\Downloads\ecom-agent\ecom-agent` (to be moved to `C:\projects\` and pushed to GitHub as `ecom-support-agent`). Free stack only.

**Built so far (Phase 1, steps 1–6):**
- `tools.py`: 4 tools — `search_products` (returns matches + in-stock alternatives + a note to the model), `get_order_status`, `get_policy` (RAG), `cancel_order`. Plus `TOOL_SCHEMAS`.
- `agent_raw.py`: hand-written agent loop, no framework. `MAX_STEPS=8`, catches `groq.BadRequestError` for malformed tool calls, prints `[tool]` and `[result]` lines.
- `agent_langgraph.py`: same agent in LangGraph. `SqliteSaver` checkpointer (`checkpoints.db`), `interrupt_before=["tools"]`, human approval required for `cancel_order`.
- `rag.py`: chunk (one per bullet, heading-prefixed) → embed (ChromaDB built-in all-MiniLM, on-device) → retrieve top-3 with distance scores. Index in `chroma_db/`.
- `data/`: `products.csv` (8 SKUs), `orders.json` (3 orders), `policies.md` (4 sections incl. "Damaged or wrong items").
- `evals/cases.jsonl` + `evals/run_evals.py`: exists but not yet run or updated.
- `docs/GUIDEBOOK.md`: Chapters 1–6 written in plain English, one per step, including every bug hit.

**Model/provider:** Groq free tier, model `openai/gpt-oss-120b` (set in `.env` as `MODEL`). Llama 3.3 is retired on Groq; use `client.models.list()` to check.

## Conventions we settled on
- One step at a time. Task → "done when" checkpoint → I paste output → mentor confirms before moving on.
- Design talk in plain English *before* code, every step. Analogies used: model = new employee who can't see the warehouse, tools = phone calls to the warehouse; LangGraph = n8n flowchart in Python.
- Commit after every step, message style `stepN-short-description`. Guidebook chapter per step, committed separately.
- Run `git status` before `git add .`.
- Always log what tools return (`[result]` print).
- Prompts shape behaviour; code enforces it (interrupts for risky tools).
- I sometimes use VS Code's AI agent to make edits; mentor's rule is fine, but read the diff before committing.

## Known quirks of my setup
- Terminal sometimes drops quoted text after `git commit -m`; use single-word messages with hyphens.
- Pasting multiple commands at once causes `>>` continuation; paste one at a time.
- I've opened the wrong (outer) folder more than once; check the Explorer root shows `tools.py` directly.
- Windows hides file extensions; create files in VS Code, not File Explorer.
- Don't install Ollama (storage/crash concern with n8n running locally). Use ChromaDB built-in embeddings and Groq's `openai/gpt-oss-20b` as the "small model" instead.
- Remember to restart the agent after editing any `.py` file.

## Full plan (15 steps)
Phase 1 Build: 1 setup ✅, 2 loop ✅, 3 tool design ✅, 4 LangGraph+memory ✅, 5 HITL ✅, 6 RAG ✅, **7 evals + GitHub push + README**
Phase 2 Deploy: 8 FastAPI endpoint, 9 Gradio UI, 10 Hugging Face Spaces + Dockerfile + GitHub Actions running evals
Phase 3 Fine-tune: 11 pick task (candidate: "policy doesn't cover this → say so, don't stretch") + build 300–500 example dataset, 12 Unsloth+LoRA on free Colab, 13 eval vs base model with our harness, 14 publish adapter to HF Hub, 15 swap into deployed agent

## Current position
**Next: Step 7 — evals.** `evals/cases.jsonl` has 7 old cases; needs updating for the new `get_policy(question)` schema and new cases from Chapters 3 and 6 (earbuds → exactly 1 tool call; damaged parcel → answer from the new policy section; a question the policy doesn't cover → must say "not covered", which currently FAILS and is parked for fine-tuning). Then run `python evals/run_evals.py`, fix what's fixable, commit, write Chapter 7, rename branch `master`→`main`, push to GitHub, write README.

## How to resume
"You're my mentor on this project. Read MENTOR_CONTEXT.md and GUIDEBOOK.md, then continue from Current position using the same step-by-step teaching style: plain-English design first, one task at a time, wait for my output before moving on."