# E-commerce Support Agent

A customer-support agent for an online store, built from scratch to understand how production AI agents actually work. It answers questions about products, orders, and policies by calling tools — and refuses to cancel an order without a human saying yes.

Built on a free stack: Groq's hosted `openai/gpt-oss-120b`, LangGraph, ChromaDB with on-device embeddings. No paid API beyond a free-tier key.

## What it does

- **Tool calling** — four tools (`search_products`, `get_order_status`, `get_policy`, `cancel_order`) over CSV and JSON mock data.
- **RAG over policy documents** — `policies.md` is chunked, embedded with all-MiniLM (runs on CPU, bundled with ChromaDB), and searched semantically. "I want to stop my order" finds the Cancellations section with zero shared keywords.
- **Human-in-the-loop** — `cancel_order` cannot run without approval. Not a prompt instruction: LangGraph's `interrupt_before` halts the graph before the tools node, so the model has no say in it.
- **Persistent memory** — `SqliteSaver` checkpoints every state change to disk, so conversations survive a restart.
- **An eval suite** — 13 cases derived from real bugs hit during the build. Checks which tools were called, how many calls it took, and what the answer contained. Exits non-zero on failure.

Two implementations of the same agent are included: `agent_raw.py` is a hand-written loop with no framework, `agent_langgraph.py` is the same logic as a graph. The raw one exists to make the loop obvious before a framework hides it.

## Running it

Requires Python 3.11+ and a free [Groq](https://console.groq.com) API key.

```bash
git clone https://github.com/Dhanushgit17/ecom-support-agent.git
cd ecom-support-agent
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
copy .env.example .env          # then add your GROQ_API_KEY
python rag.py                   # build the policy index (one time)
```

Then:

```bash
python agent_raw.py             # the loop, no framework
python agent_langgraph.py       # graph + persistent memory + approval gate
python evals/run_evals.py       # 12 passed, 0 failed, 1 expected failure
```

Things to try:

- `Where is my order ORD-7781?`
- `Do you have wireless earbuds?` — out of stock, suggests an in-stock alternative in one tool call
- `What happens if my parcel arrives damaged?`
- `Cancel order ORD-7783` — checks the order, asks you, then waits for the code-level approval gate

`cancel_order` writes to `data/orders.json`. Reset with `git checkout data/orders.json` after testing. The eval suite snapshots and restores it automatically.

## Known limitations

- **One test fails on purpose.** Ask *"I ordered the wrong size, can I exchange it?"* and the agent stretches the Returns policy to cover exchanges, which the policy doesn't mention. Prompt engineering didn't fix it. It's pinned in the eval suite as an expected failure and is the target for Phase 3 fine-tuning.
- Eval answer-checks use substring matching, which can't tell an honest refusal from a confident invention. An LLM judge is planned.
- The harness is single-turn, so multi-turn behaviour (confirmation flows, clarifying questions) can't be scored yet.
- Mock data: 8 products, 3 orders, a 4-section policy file.

## Project layout

```
tools.py              4 tools + their JSON schemas
agent_raw.py          hand-written agent loop
agent_langgraph.py    the same agent as a LangGraph graph
rag.py                chunk, embed, retrieve
evals/cases.jsonl     13 test cases
evals/run_evals.py    the eval harness
data/                 products.csv, orders.json, policies.md
docs/GUIDEBOOK.md     how every piece was built, and every bug hit along the way
```

## Roadmap

Phase 1 (build) is complete. Next: a FastAPI endpoint, a Gradio UI, deployment to Hugging Face Spaces with evals running in CI, then fine-tuning a small model on the "say it isn't covered" failure and measuring it against this baseline.

## The guidebook

[`docs/GUIDEBOOK.md`](docs/GUIDEBOOK.md) is a chapter-by-chapter record of the build in plain English — including the agent that made 8 tool calls when it needed 1, the RAG chunker that silently returned zero chunks, and the model that invented an entire damaged-parcel policy out of thin air.