# E-commerce Support Agent (Phase 1 skeleton)

```
pip install -r requirements.txt
cp .env.example .env        # add your free Groq key
python agent_raw.py         # Step 2: raw loop, no framework
python agent_langgraph.py   # Step 3: LangGraph + memory + human approval
python evals/run_evals.py   # Step 5: eval harness
```

Try: "Where is ORD-7781?", "footwear under 4000", "cancel ORD-7783", "return policy for electronics".

## Your homework (in order)
1. Read `agent_raw.py` line by line until the loop is obvious. Break it on purpose (remove MAX_STEPS, return bad JSON from a tool).
2. In LangGraph, add a `SqliteSaver` so memory survives restarts.
3. Add a `recommend_similar(sku)` tool. Update evals.
4. Replace `get_policy` keyword lookup with real RAG: chunk `policies.md`, embed with Ollama `nomic-embed-text`, store in ChromaDB.
5. Swap `MODEL` to a local Ollama model via `ChatOllama` and compare eval scores. This is your fine-tuning baseline for Phase 3.
