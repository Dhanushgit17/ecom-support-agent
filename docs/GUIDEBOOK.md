# E-commerce Support Agent — Build Guidebook

A step-by-step record of how this project was built, what each piece does, and what went wrong along the way. Written to be readable by someone who has never coded an AI agent before.

---

## Chapter 1 — Setting up the workshop

**Goal:** get a clean Python environment, prove we can talk to a hosted LLM from code, and put the project under version control.

**Time taken:** about one hour, most of it spent on setup mistakes worth remembering.

### What was built

| File | Purpose |
|---|---|
| `.venv/` | A private "toolbox" of installed Python packages for this project only. Not committed to Git. |
| `requirements.txt` | The shopping list of packages: `groq`, `python-dotenv`, `langchain-core`, `langchain-groq`, `langgraph`. |
| `.env` | Holds the secret API key. Never committed. |
| `.env.example` | A template showing which variables `.env` needs, with placeholder values. Safe to commit. |
| `.gitignore` | Tells Git which files to skip: `.venv/`, `.env`, `__pycache__/`, `*.pyc`. |
| `hello.py` | Sends one message to the model and prints the reply plus token count. |

### Concepts, in plain English

**Virtual environment (`.venv`).** Python packages installed "globally" affect every project on the computer. A venv is a folder with its own copy of Python and its own packages, so projects can't break each other. The `(.venv)` prefix in the terminal prompt means the venv is active. If the prefix is missing, run `.\.venv\Scripts\Activate.ps1` first; forgetting this is the number one cause of "it worked yesterday."

**API key.** A password that identifies your Groq account. It's stored in `.env` and read at runtime with `load_dotenv()` and `os.environ["GROQ_API_KEY"]`. It lives outside the code because the code is going to be public on GitHub, and bots scan GitHub for leaked keys within minutes.

**API call.** `client.chat.completions.create(...)` bundles your message into JSON, sends it over HTTPS to Groq's servers, a 120-billion-parameter model generates a reply, and the response comes back as JSON. `r.choices[0].message.content` is the text.

**Token.** The unit LLMs measure everything in: rate limits, cost, and how much context the model can hold. Roughly 1 token ≈ ¾ of an English word. A 10-word prompt and 2-word reply used 154 tokens because the model also produced hidden reasoning and formatting tokens. This number matters for agents because every tool call re-sends the whole conversation.

**Git commit.** A snapshot of every tracked file at a moment in time. Commits are local (on the laptop) until pushed to GitHub. The first commit here was `0962623`, 13 files.

### Mistakes made, and the lesson from each

1. **Opened the wrong folder in VS Code.** Unzipping created `ecom-agent\ecom-agent\`. Opening the outer one meant terminal commands couldn't find `requirements.txt`. *Rule:* open the folder that directly contains the files you run. Check by running `ls` in the terminal; if `requirements.txt` isn't listed, you're one level too high.

2. **Ctrl+C cancelled the install.** In a terminal, Ctrl+C means "kill the running command," not "copy." The fix was simply to run `pip install` again.

3. **Model name was retired.** `llama-3.3-70b-versatile` returned a 404. Hosted model names change every few months. *Rule:* don't guess; ask the provider with `client.models.list()`. Switched to `openai/gpt-oss-120b`.

4. **Nearly created `hello.py.txt`.** Windows File Explorer hides extensions, so "New Text Document" silently adds `.txt`. *Rule:* create code files inside the IDE, and turn on "File name extensions" in Explorer.

Also hit: the terminal dropping quoted text after `git commit -m`. Workaround was a message without spaces (`step1-setup`) or using VS Code's Source Control panel.

### How to verify Chapter 1 is working

```powershell
.\.venv\Scripts\Activate.ps1
python hello.py          # prints "plumbing works" and a token count
git status               # "nothing to commit, working tree clean"
git ls-files             # must NOT include .env
```

---

## Chapter 2 — The agent loop

**Goal:** understand what an "agent" actually is by reading and running `agent_raw.py`, which has no framework in it.

### The loop in plain English

An agent is a model inside a loop with tools. One turn works like this:

1. Send the whole conversation (system prompt + every message so far) to the model, along with a list of tools it may ask for.
2. Read the reply. If it contains **no tool calls**, the model is done: return its text to the user. Loop ends.
3. If it contains tool calls, the model is saying "I need information first." For each one, **your Python code** runs the matching function and appends the result to the conversation as a `tool` message.
4. Go back to step 1. The model now sees the tool results and decides again: answer, or call more tools.

The `MAX_STEPS` guard (8 here) stops the loop if the model never reaches a final answer. It's insurance against runaway loops, which cost money and time.

### Three things that surprised me

- **The model never runs anything.** It only sends back a small JSON note like `{"name": "get_order_status", "arguments": {"order_id": "ORD-7781"}}`. The line `TOOL_FUNCTIONS[name](**args)` in my code is what executes. This is why tools are safe: the model can only request, and I decide what's runnable.
- **Every loop iteration re-sends the entire conversation.** Tokens add up fast. A question that takes 6 tool calls costs roughly 6× a question that takes 1.
- **The model extracted `ORD-7781` from my sentence on its own** and put it in the right argument. Nothing in my code parses order IDs; the model does that from the schema description.

### What the first run showed

Order lookup: 1 tool call, correct answer. Cancel flow: the model asked me to confirm before calling `cancel_order`, waited for "yes", then called it. That behaviour came entirely from one line in the system prompt.

Earbuds question: **8 tool calls, then the step limit, then a generic error.** See Chapter 3.

Note: `cancel_order` writes to `data/orders.json`. After testing, reset it with `git checkout data/orders.json`.

---

## Chapter 3 — Tool design: the model only knows what your tools tell it

**Goal:** fix the earbuds failure by changing the tool, not the model or the prompt.

### What went wrong

`search_products("wireless earbuds")` found the SoundPod earbuds, which are out of stock. The system prompt says "suggest an alternative," so the model searched again: headphones, earphones, Bluetooth speaker. Each search returned `"No products matched."`. That string gives the model nothing to work with, so it kept trying until `MAX_STEPS` stopped it.

Analogy: the model is a new employee at the service desk who can't see the warehouse. Tools are phone calls to the warehouse. If the warehouse only ever says "no," the employee keeps calling with different words.

### The fix, in two rounds

**Round 1:** when a search finds nothing and a category was given, return the whole category instead of "No products matched." Result: 6 tool calls and a correct answer. Better, but still slow, because an *out-of-stock hit* never reached the fallback, and searches with no category had no fallback at all.

**Round 2:** rewrite `search_products` to always return two lists in one pass over the CSV: `matches` (what was asked for, in or out of stock) and `in_stock_alternatives` (up to 3 in-stock items in the same category). Also add a `note` field in the JSON telling the model to suggest from the alternatives and not search again. Result: **1 tool call and a correct answer.**

### The principle

The model cannot be smarter than what the tools return. When an agent loops, hallucinates, or gives up, check the tool output first. Most "the model is behaving badly" bugs are "the tool starved the model" bugs. A good tool answers the question *and* the obvious follow-up in a single call.

Two techniques used here that are standard practice:
- Return structured JSON with named fields, not free text, so the model can't misread it.
- Put short instructions inside tool output (`"note": "..."`). Models read tool results as carefully as the prompt.

### Mistakes made

- My first test query, `'bluetooth speaker'`, accidentally matched "Bluetooth 5" in a product description, so it didn't test the no-match path at all. Lesson: confirm the test actually exercises the case you think it does. A clean no-match query was `'laptop'`.
- An `IndentationError` from pasting the block at the wrong indent level. Fixed by aligning it with the line above.
- Ran the agent without restarting it after editing `tools.py`, so the old code was still loaded. Python reads a file once at startup; every code change needs a restart.

### How to verify

```powershell
python -c "from tools import search_products; print(search_products('laptop', category='electronics'))"
# expect: matches: [], in_stock_alternatives: [PulseBand]
python agent_raw.py   # "Do you have wireless earbuds?" -> exactly one [tool] line
```

---

## Chapter 4 — Rebuilding the loop in LangGraph, and memory that survives

**Goal:** understand why a working 40-line loop gets rebuilt as a graph, and give the agent memory that outlives the process.

### Why a graph

Three things production needs that a plain loop can't give cleanly:

1. **Memory that survives** restarts and works across multiple servers. Needs a database behind the conversation.
2. **Pausing.** A hard stop before a risky tool, resumable later. A loop can't freeze mid-iteration.
3. **Branching.** Routing to sub-agents, running tools in parallel, retries. That's a flowchart, not a loop.

LangGraph: you draw the flowchart, it runs it. Nodes are boxes (`agent`, `tools`), edges are arrows, a conditional edge is the diamond that decides `tools` or `END`, state is the data on the arrows (the message list), and a checkpointer saves state after every node. It's n8n's mental model, written in Python, with the model choosing the arrow.

### Mapping the raw loop to the graph

| `agent_raw.py` | `agent_langgraph.py` |
|---|---|
| `client.chat.completions.create(...)` | `agent` node |
| `if not msg.tool_calls: return` | conditional edge → `END` |
| `for tc in msg.tool_calls: TOOL_FUNCTIONS[name](**args)` | `tools` node (`ToolNode`) |
| the outer `for step in range(MAX_STEPS)` | edge `tools → agent` |
| the `messages` list | `MessagesState` |

Nothing new happens. Same loop, drawn as boxes so it can be saved, paused, and branched.

### Memory: two experiments

1. With `MemorySaver`: asked about ORD-7781, then "what did I ask?" — it remembered. Restarted the program and asked again — **it had no idea.** `MemorySaver` keeps checkpoints in RAM; the process dies, memory dies.
2. Swapped one line to `SqliteSaver(sqlite3.connect("checkpoints.db", ...))`. Restarted and asked — **it remembered.** Every state change is written to disk, and `thread_id="user-1"` points the new process at the same thread.

The graph code didn't change at all. That swappability is the point. Production uses the same pattern with Postgres.

Housekeeping: `checkpoints.db` is data, so it went into `.gitignore`; `langgraph-checkpoint-sqlite` went into `requirements.txt` so the project stays reproducible.

---

## Chapter 5 — Human-in-the-loop: prompts shape, code enforces

**Goal:** see the difference between the model *choosing* to ask permission and the code *requiring* it.

### What happened

First cancel attempt: the model checked the order, asked me to confirm, insisted on "yes" rather than "y" (model quirk), and only then tried to call `cancel_order`. At that moment the code paused with `[approval needed] ... (y/n)`. I said `n`. Nothing was cancelled.

Second cancel attempt, same session: **the model skipped the confirmation entirely.** It remembered I'd already said yes, so it went straight to the tool. On Sunday's raw agent that would have cancelled instantly. Today the code gate caught it anyway, I said `y`, and only then did the cancellation run.

### The mechanism

`graph.compile(..., interrupt_before=["tools"])` makes the graph stop before the `tools` node and save a checkpoint. `chat()` inspects the pending tool call; if it's `cancel_order`, a human must answer. Anything else is auto-resumed with `app.invoke(None, config)`, which means "continue from the checkpoint."

### The rule

- A line in the system prompt is a **request**. The model usually complies, and sometimes has a reason not to.
- `interrupt_before` is **physics**. The `tools` node cannot run until something resumes the graph. The model has no say.

Anything that must never happen without a human — refunds, deletions, payments, outbound emails — gets a code gate. Prompts handle the 99%; interrupts handle the 1% that costs money.

### Verify

```powershell
python agent_langgraph.py
# "Cancel order ORD-7783" -> eventually an [approval needed] prompt; answer n -> nothing cancelled
git checkout data/orders.json   # reset the mock DB after testing
```

---

---

## Chapter 6 — RAG: retrieval, and where it fails

**Goal:** replace the keyword policy lookup with semantic search, wire it into the agent, and see two kinds of hallucination up close.

### Why keyword lookup wasn't enough

`get_policy("returns")` only worked because the policy file had three neat headings and the model guessed the heading name. "Send it back" contains neither "return" nor any heading. And real policy docs are 40 pages; you can't paste them into every prompt.

### The three moves

1. **Chunk.** Split the document into small passages. After a bug, one chunk per bullet, prefixed with its section heading (`"Returns: Footwear must be tried on carpet only..."`). The prefix gives both the embedder and the LLM context that a bare bullet lacks.
2. **Embed.** Each chunk goes through an embedding model (all-MiniLM, 79 MB, runs on CPU, bundled with ChromaDB) and becomes a vector of numbers. Similar meaning → nearby vectors. No Ollama needed.
3. **Retrieve.** Embed the question the same way, return the 3 nearest chunks. ChromaDB is a database whose one job is "find the nearest vectors fast."

Proof it works: "I want to stop my order" retrieved the Cancellations section with zero shared words.

### Files

- `rag.py`: `chunk_markdown`, `build_index`, `ensure_index`, `retrieve_policy`. Index stored on disk in `chroma_db/` (gitignored).
- `tools.py`: `get_policy(question)` now just calls `retrieve_policy`. Schema updated from `topic` to `question`.
- `agent_raw.py`: API call wrapped in `try/except` for malformed tool calls; `[result]` print added.

### Bugs, in order

1. **Chunker returned zero chunks.** It split on blank lines and assumed a blank line after each heading; the file had none, so every block started with `## ` and was skipped. *Lesson: chunking is where most RAG systems quietly fail. Print the chunks before indexing.*
2. **Schema and function disagreed.** Schema said `question`, function still said `topic`. Every call returned `Tool error: unexpected keyword argument`. Invisible until the `[result]` print was added. *Lesson: always log what tools return.*
3. **Model emitted a malformed tool call** (`query` instead of `question`). Groq rejected it with a 400 and the agent crashed. Fixed by catching `groq.BadRequestError` with `tool_use_failed`, telling the model to retry. *Lesson: malformed tool calls happen; the loop must survive them.*

### Two hallucinations

**Hard hallucination.** While `get_policy` was broken, the model invented a complete damaged-parcel policy: 48-hour window, photos, replacement or refund. Plausible, confident, entirely made up. Cause: tools gave it nothing, so it filled the gap.

**Soft hallucination.** With RAG working, the same question retrieved three Returns bullets (distance ~1.18) because they were the *nearest* chunks. The model stretched the returns policy to cover damaged parcels. Everything it said was in the document; none of it applied.

### What was tried, and what worked

- **Distance threshold:** looked at the numbers. Covered questions scored 0.90, 0.92, 1.15; the uncovered one scored 1.18. A gap of 0.03 can't be thresholded. Kept the scores in the tool output as a signal, dropped the idea of a cutoff.
- **Sharper prompt rule** ("nearest is not the same as relevant"): the model still stretched the policy. Prompt engineering hit its ceiling here.
- **Fix the document:** added a "Damaged or wrong items" section, rebuilt the index. Distance dropped from 1.18 to 0.64 and the answer was correct. This is what happens in real companies: RAG logs reveal unanswered questions, the content team fills the gap.

Two options parked for later: a grading step (a cheap second model call that drops irrelevant passages, sometimes called corrective RAG), and fine-tuning a model to say "not covered" instead of stretching. The damaged-parcel case becomes training data for Phase 3.

### Verify

```powershell
python rag.py             # rebuilds index, prints 13 chunks with distances
python agent_raw.py       # "What happens if my parcel arrives damaged?" -> distance ~0.64, correct answer
```

### What's next

Chapter 7: evals. Turning every failure from Chapters 2–6 into a test case, so the agent can't silently regress.