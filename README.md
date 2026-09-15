---
title: E-commerce Support Agent
emoji: 🛒
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# E-commerce Support Agent

A customer-support agent for an online store, built from scratch to learn how production AI agents actually work. Every part is written out rather than pulled from a template, and every bug hit along the way is documented in [`docs/GUIDEBOOK.md`](docs/GUIDEBOOK.md).

Free stack throughout: Groq's free tier for the LLM, on-device embeddings, SQLite for memory.

## What it does

Answers customer questions about orders, products and store policy, and cancels orders — but never without a human saying yes first.

- **Order lookup** — status, carrier, tracking number, ETA
- **Product search** — returns matches *and* in-stock alternatives in one call, so an out-of-stock item doesn't send the agent into a loop
- **Policy questions** — semantic search over the policy document, so "I want to stop my order" finds the Cancellations section without sharing a single word with it
- **Cancellations** — gated by a hard code-level interrupt, not just a polite instruction in the prompt

## Architecture

```
Browser (Gradio, :7860)
        │  HTTP
        ▼
FastAPI (:8000)  ──  /health  /chat  /approve
        │
        ▼
LangGraph agent  ──  SqliteSaver ──► checkpoints.db   (conversation memory)
        │
        ├── search_products    ──► data/products.csv
        ├── get_order_status   ──► data/orders.json
        ├── get_policy   ─ RAG ──► ChromaDB ◄── data/policies.md
        └── cancel_order       ──► data/orders.json   (writes; needs approval)
```

The UI talks to the API over HTTP rather than importing it. That keeps the API honest — if it breaks, the UI notices — and means either half can be replaced without touching the other.

| File | What it is |
|---|---|
| `tools.py` | The four tools plus their JSON schemas |
| `agent_raw.py` | The agent loop written by hand, no framework. Start here to understand what an agent *is* |
| `agent_langgraph.py` | The same loop as a graph: checkpointed memory, human-in-the-loop interrupts |
| `rag.py` | Chunk → embed → retrieve, with distance scores |
| `api.py` | FastAPI wrapper. Sessions, approval endpoints, error handling |
| `ui.py` | Gradio chat window |
| `evals/` | 13 behavioural test cases and a runner |
| `docs/GUIDEBOOK.md` | Chapter per step, in plain English, including every bug |

## Running it

**Requirements:** Python 3.11+, a free [Groq API key](https://console.groq.com).

```bash
git clone https://github.com/Dhanushgit17/ecom-support-agent.git
cd ecom-support-agent

python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt

cp .env.example .env              # then put your Groq key in it
python rag.py                     # builds the vector index (gitignored, so this is required once)
```

Then pick an interface.

**Terminal only:**

```bash
python agent_raw.py          # the hand-written loop
python agent_langgraph.py    # the graph version, with approval prompts
```

**Web UI** — two processes, two terminals:

```bash
# terminal 1
uvicorn api:api --reload     # wait for "Application startup complete"

# terminal 2
python ui.py                 # http://127.0.0.1:7860
```

The API alone is at `http://127.0.0.1:8000/docs`, which gives you an interactive page for every endpoint.

**Evals:**

```bash
python evals/run_evals.py    # 12 passed, 0 failed, 1 expected failure
```

## The API

| Endpoint | Body | Returns |
|---|---|---|
| `GET /health` | — | `{"status": "ok"}` |
| `POST /chat` | `{"message": "...", "thread_id": "user-1"}` | `answer`, `thread_id`, `needs_approval`, `pending_tool`, `tool_calls` |
| `POST /approve` | `{"thread_id": "user-1", "approved": true}` | same shape |

`thread_id` names the conversation. The same id continues a conversation — across server restarts, because state lives in SQLite. A different id is a different customer.

When the agent wants to run a risky tool, `/chat` returns `needs_approval: true` and stops. The half-finished conversation stays frozen on disk until `/approve` resumes or discards it. Nothing blocks and nothing waits, so the pause can last five seconds or five hours.

## Things worth knowing

**Prompts shape behaviour; code enforces it.** The system prompt asks the model to confirm before cancelling, and it usually does. It has also been observed skipping that confirmation on a second attempt in the same session. `interrupt_before=["tools"]` is what actually stops the tool running — the model has no say in it.

**The model can't be smarter than what the tools return.** An early version of `search_products` answered "No products matched" and the agent looped eight times looking for a synonym. Returning matches *and* alternatives in one call fixed it in a single tool call. Most "the model is behaving badly" bugs are "the tool starved the model" bugs.

**Nearest is not relevant.** RAG returns the closest passages whether or not they answer the question. Asked about a damaged parcel with no such policy in the document, the model stretched the returns policy to fit — confidently, and entirely from real source text. The fix was to write the missing policy section, not to tune the retrieval.

**Evals check behaviour, not wording.** An LLM says it differently every run, so the tests check which tools were called, how many calls it took, and whether key facts from the data files appear. Checking exact wording fails for cosmetic reasons and teaches you nothing.

## Known limitations

- **No authentication on any endpoint.** Anyone who can reach the URL can cancel orders. Fine on localhost, not fine deployed.
- **The evals only cover `agent_raw.py`.** Nothing tests the API, the sessions, the approval gate or the UI. Those were verified by hand.
- **The eval answer-checks are substring matching**, so a confident invention can pass if it contains the right phrase. An LLM judge is planned.
- **The harness is single-turn**, so multi-turn bugs (like the skipped confirmation above) can't be scored.
- **`agent_langgraph.py` doesn't retry malformed tool calls** the way `agent_raw.py` does. Over HTTP that becomes a clean 500 rather than a recovery.
- **`checkpoints.db` grows forever.** No cleanup, expiry or thread limit.
- One eval case is a deliberate, documented failure: asked about exchanging a wrong-size item, the agent applies the returns policy to a situation the document doesn't cover. It's the target for the fine-tuning phase.

## Roadmap

**Phase 1 — Build** ✅
Setup · agent loop · tool design · LangGraph + memory · human-in-the-loop · RAG · evals

**Phase 2 — Deploy**
FastAPI ✅ · Gradio UI ✅ · Docker + Hugging Face Spaces + CI

**Phase 3 — Fine-tune**
Build a dataset for the policy-stretching failure · LoRA on free Colab · measure against the base model with this same eval harness · publish the adapter · swap it into the deployed agent

## Stack

Groq (`openai/gpt-oss-120b`) · LangGraph · ChromaDB with on-device all-MiniLM embeddings · FastAPI · Gradio · SQLite
