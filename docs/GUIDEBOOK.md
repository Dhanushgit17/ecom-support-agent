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

## Chapter 7 — Evals: turning every bug into a test

**Goal:** make it impossible for the agent to regress silently. Every failure from Chapters 2–6 becomes a test case, the suite runs in one command, and a non-zero exit code means something broke.

### Why an agent needs a different kind of test

An n8n workflow is deterministic: same input, same output, so "did it work" is a yes/no. An LLM agent gives different words every run. Across four runs of this suite, "order not found" came back as *couldn't find*, *couldn't locate*, *couldn't find any order*. A test that checks the exact wording fails for cosmetic reasons and teaches you nothing.

So the tests check **behaviour**, cheapest first:

1. **Which tools were called.** Pure data. `get_order_status` was either in the list or it wasn't.
2. **How many calls it took.** Chapter 3's fix went from 8 tool calls to 1. Nothing else would notice if it crept back to 6, because the *answer* would still be right. `max_tool_calls: 1` on every product and order case is that fix, locked in.
3. **What the answer contains.** Substrings from the source data (`products.csv`, `orders.json`, `policies.md`). Crude, but free and instant.

Checks 1 and 2 are the ones that tell you *where in the loop* it went wrong. Most people only write check 3 and then can't diagnose a failure.

### Files

- `evals/cases.jsonl`: 13 cases, one JSON object per line. Fields: `input`, `tool`, `must_not_call`, `max_tool_calls`, `must_contain`, `must_contain_any`, `must_not_contain`, `expected_fail`.
- `evals/run_evals.py`: runs each case against `agent_raw.run_agent` with a fresh history, collects the tool calls from the message list, and prints PASS / FAIL / XFAIL / XPASS with a reason line for every failure. Exits 1 if any real case fails.

Evals run against `agent_raw.py`, not the LangGraph version, because `interrupt_before` would sit waiting for a human on every cancel case.

### Three things the runner does that a first draft wouldn't

**Reasons, not booleans.** `check()` returns a list of reasons instead of True/False. `FAIL | Cancel order ORD-7782` on its own means re-reading the answer and guessing. `x tool get_order_status not called (called: none)` means you know.

**Unicode normalisation.** The model emits typographic characters freely: `ORD‑7781` with a non-breaking hyphen (U+2011), `couldn’t` with a curly apostrophe (U+2019), `under ₹4,000` with a narrow no-break space (U+202F). None of these match their ASCII equivalents in a substring test. A 10-line `normalize()` flattens both sides before comparing, and the whole class of bug goes away. Chasing each one in the cases would never end.

**Expected failures.** A case marked `expected_fail: true` reports as XFAIL and does not break the build. If it ever passes, it reports XPASS with a message to remove the flag. A test you keep *because* it fails is a written spec for work you haven't done, plus the before-number you'll measure against later.

Also: `orders.json` is snapshotted before the run and restored in a `finally`, because `cancel_order` writes to it. A suite that mutates its own fixtures is worse than no suite.

### When a test fails, ask which one is wrong

The first run gave 5/7. One failure of each kind:

- **The test was wrong.** "ETA for ORD-9999" demanded the literal phrase `not found`. The agent had called the right tool, got `not found` back, and told the customer *I couldn't find an order with that ID*. Correct behaviour, paraphrased. Fixed the case (`must_contain_any` with several phrasings), not the agent.
- **The agent was wrong.** "Cancel order ORD-7782" made zero tool calls and asked *would you like to cancel?* — for an order that's already delivered. In Chapter 5 the same prompt had looked the order up first. Same prompt, different run, different behaviour. Fix: one prompt line, *check the order before asking to confirm; if it can't be cancelled, say why*. Test now requires `get_order_status` and forbids `cancel_order`. This was the first eval-driven fix: red → change → green, with a permanent guard.

### The suite corrected the plan

The Phase 3 fine-tuning target was "the model stretches policy instead of saying not-covered". Two uncovered questions went in as expected failures — gift wrapping, international shipping — and **both passed**. The model declined cleanly and offered a human.

Compared with Chapter 6's damaged-parcel failure, the difference wasn't distance (gift wrapping retrieved at 1.42 and was declined; the exchange question below retrieved at 1.39 and was stretched). The difference is whether the retrieved text hands the model a *plausible story*. "Do you ship internationally?" gives it nothing to work with. A customer **in a situation** next to an existing process does:

> *I ordered the wrong size. Can I exchange it for a different size?*
> → Returns chunks retrieved. Run 1: *"Yes — you can exchange within 14 days, unused, original packaging."* Run 2: *"You can return the item and place a new order."*

Every clause is from the Returns section; none of it is an exchange policy. That case is now the suite's one XFAIL and the first training example for Phase 3. Refined target: **situation question + adjacent process → stretch.** Target answer: acknowledge it isn't covered, state what the policy does allow, hand off to a human.

A second situational case (order 3 days past ETA) was deleted. The agent didn't call any tool; it asked for the order ID. Reasonable customer service, but the case had been written assuming a policy question and the model treated it as an order question. A test that can fail for two unrelated reasons is noise. Lesson: one case, one behaviour.

### Where the checks are weakest

The "not covered" cases are checked by a proxy: did the answer hand off to a human (`human`, `representative`, `connect you`, `support team`)? A stretched answer doesn't hand off; a decline does. It survived four runs but it's still pattern-matching wording. The honest fix is a second model call that grades the answer against a rubric — an LLM judge. That arrives in Step 13, where the whole before/after comparison rests on this one behaviour.

The harness is also single-turn. Chapter 5's real bug (skipping confirmation the second time) and "ask for the order ID first" can't be scored without multi-turn cases. Parked.

### Mistakes made

1. **Edited `cases.jsonl` and didn't save.** The suite ran the old 7 cases and I read the results as if they were the new ones. Caught because 7 ran instead of 11. *Rule:* `git status` before every run; the file you edited must be listed as modified.
2. **Pasted the prompt into the Python REPL.** Shift+Enter in VS Code sends selected code to an interactive `>>>` shell, not the file. Harmless — nothing on disk changed — but confusing. `exit()` gets out.
3. **Three lines missing their closing `}`.** JSONL has no forgiveness; one bad line kills the run before any case executes. Cheap check before running the agent: `python -c "import json; [json.loads(l) for l in open('evals/cases.jsonl') if l.strip()]; print('ok')"`.
4. **Dropped `expected_fail` while editing a line.** Would have turned a known failure into a build breaker.
5. **Filled a `must_contain` from the agent's output instead of the policy file.** Nearly — the `[result]` line showed the chunk straight from `policies.md`, so `48 hours` was source data after all. *Rule:* expected values come from the data files, never from the answer. Otherwise you're asserting "the agent does what the agent does."

### Verify

```powershell
python -c "import json; [json.loads(l) for l in open('evals/cases.jsonl') if l.strip()]; print('ok')"
python evals/run_evals.py     # 12 passed, 0 failed, 1 expected failures, 0 unexpected passes
git status                    # orders.json must NOT appear as modified after a run
```

## Chapter 8 — FastAPI: the agent becomes a URL

**Goal:** wrap the agent in a web endpoint so something other than a terminal can call it. A URL that takes a question and returns JSON.

**Time taken:** two sessions. Roughly a third of it was a broken virtual environment that had nothing to do with FastAPI.

### Why this step exists

Everything up to Chapter 7 only works if a human is sitting at the keyboard typing into `input()`. That agent cannot be put on the internet, cannot be called by a web page, and cannot be used by anyone else. Step 9 (Gradio UI) and Step 10 (Hugging Face Spaces) both need something that speaks HTTP.

The n8n equivalent: a workflow on a laptop is useless to anyone else, but a **Webhook node** gives it a URL and suddenly anything can trigger it. This chapter is that node, written by hand in Python.

### What was built

| File | Purpose |
|---|---|
| `api.py` | Three endpoints: `/health`, `/chat`, `/approve`. Imports the LangGraph agent; changes nothing inside it. |
| `requirements.txt` | Added `fastapi` and `uvicorn[standard]`. |
| `.gitignore` | Added `checkpoints.db-shm` and `checkpoints.db-wal`. |

The agent itself was not modified. `tools.py`, `agent_raw.py`, `agent_langgraph.py`, and `rag.py` are untouched by this chapter. That's the point: the API is a wrapper, not a rewrite.

### Concepts, in plain English

**Server vs script.** `python agent_raw.py` runs, does a thing, and exits. `uvicorn api:api --reload` starts and *does not return the terminal* — it sits there listening on port 8000 until killed. That's the whole difference between a script and a server. Ctrl+C stops it, and here Ctrl+C is what you actually want (unlike Chapter 1, where it cancelled a pip install by accident).

**`api:api` means "in the file `api.py`, find the variable named `api`."** The command changed from `api:app` to `api:api` mid-step because the FastAPI object had to be renamed: `agent_langgraph.py` already uses `app` for the compiled graph, and importing it as `app` into a file that also had a FastAPI `app` would collide. So the graph is imported as `graph` and the FastAPI object is `api`.

**GET vs POST.** A browser URL bar can only send GET requests, and GET puts its data in the URL itself. Customer questions can be long, contain `?` and `&`, and shouldn't sit in browser history and server logs. POST carries data in the request *body*. Rule of thumb: GET to read something, POST to do something. Running an agent is doing something. This is also why `/docs` became the testing tool instead of the address bar.

**`/docs` is free.** FastAPI generates an interactive test page from the code itself. Expand an endpoint, click "Try it out", fill in the body, Execute. It also shows the raw `curl` command it sent, which is exactly what Gradio will be doing in Step 9. Be careful: the Curl box shows the request that *will* be sent, not the result. The result is further down under **Server response**.

**Status codes seen, in order of how often they'll matter:**

| Code | Meaning | Where it turned up |
|---|---|---|
| 200 | Worked | Every successful request |
| 404 | No route matches that path | The browser silently asking for `/favicon.ico` on every page load — never a bug |
| 422 | Route exists, request body was the wrong shape | Sent an approval body to `/chat` by accident |
| 500 | Route exists, body was fine, the code blew up | Deliberately, with a broken API key |

Knowing 404 from 422 from 500 means knowing whether the problem is the URL, the caller, or the code — from the one log line, before reading anything else.

### The four problems, and what each fix was

Four things break the moment the caller stops being a human at a keyboard.

#### 1. The conversation gets forgotten

The first version of `/chat` built a fresh `history` list inside the function on every request. Python creates it, `run_agent` fills it, the function returns, Python throws it away.

The result was worth seeing:

> **Q:** "Where is my order ORD-7781?" → correct answer, `tool_calls: ["get_order_status"]`
> **Q:** "What did I just ask you?" → *"You just asked me, 'What did I just ask you?'"*

The model isn't confused there. It's answering honestly — that one message is the entire conversation it can see.

**Fix:** switch from `agent_raw` to the LangGraph app and add one field to the request body.

```json
{"message": "...", "thread_id": "user-1"}
```

`thread_id` is the conversation's name. Chapter 4 already built every part of this — `SqliteSaver`, `checkpoints.db`, threads — it just had never been called by anything but a terminal. In Step 9 the UI will generate a thread id per browser session; in a real system it's the logged-in user's id. The API doesn't care, it's just a string.

**Proof it works:** killed the server completely, restarted it, asked *"What was that order number again?"* on `user-1` → **"The order you were asking about is ORD-7781."** That answer came off the disk. The process that learned it was dead.

#### 2. Two customers at once

Same question, `thread_id: "user-2"` → total amnesia. `user-2` has never spoken to this agent.

No code handles concurrency here. It works because **nothing is stored in the Python process at all** — state lives in SQLite, keyed by thread. The tempting wrong fix (a `conversations = {}` dictionary at the top of `api.py`) would work on a laptop for about a day, then die on restart, break with two server processes, and grow until memory ran out. Chapter 4's `MemorySaver` lesson, one layer up.

#### 3. Nobody is there to type "y"

The interesting one. `agent_langgraph.chat()` contains:

```python
ok = input(f"  [approval needed] run {pending}? (y/n): ")
```

In a terminal that's fine. In a web server there is **nobody at that keyboard** — the request blocks until it times out. So `api.py` doesn't import `chat()`; it has its own resume logic. The terminal version and the web version genuinely need different behaviour at the interrupt.

**The fix:** an HTTP request cannot pause and wait for a human, so the conversation splits across two requests.

1. `POST /chat` → the graph hits `interrupt_before=["tools"]` and freezes → the response says `needs_approval: true` and **the request ends**. Server goes idle.
2. *(time passes — five seconds or five hours, it doesn't matter)*
3. `POST /approve` with `{"approved": true/false}` → the frozen conversation resumes or the pending call is discarded.

Between those two requests the half-finished conversation is sitting in `checkpoints.db` on disk. Chapter 4 listed "pausing — a hard stop before a risky tool, resumable later" as a reason to use a graph. This is the first place it's actually load-bearing.

**Response shape**, designed before the code was written, so Step 9's UI has something to switch on:

```json
{
  "answer": "I need your approval before I run: cancel_order.",
  "thread_id": "approve-test",
  "needs_approval": true,
  "pending_tool": "cancel_order"
}
```

`needs_approval` is a boolean the UI checks to decide "render a message" or "render a Yes/No prompt". A UI parsing English text to work that out would be a bug waiting to happen.

**The rejection path** is the subtle bit:

```python
graph.update_state(config, {"messages": [...refusal...]}, as_node="tools")
```

That writes a message into the graph *as if the tools node had produced it*, which discards the pending tool call. The graph then continues to the agent node, the model sees the refusal, and explains itself to the customer. Chapter 5's `n` answer, expressed over HTTP.

#### 4. Bad input and crashes reach the caller

**Bad input** is handled by Pydantic for free. `class ChatRequest(BaseModel)` declares that the body must have a `message` string; FastAPI validates against it and rejects mismatches with a 422 **before the endpoint function runs**, naming the exact field:

```json
{"detail": [{"type": "missing", "loc": ["body", "message"], "msg": "Field required"}]}
```

**Crashes** needed real work. Without a handler, an exception returns a full stack trace to whoever asked: file paths, folder structure, package versions, sometimes local variable contents. On a public server that's an information leak.

The rule: **the server sees everything, the caller sees almost nothing, and an id links the two.**

```python
def server_error(where: str, thread_id: str):
    error_id = uuid.uuid4().hex[:8]
    logger.exception("%s failed [%s] thread=%s", where, error_id, thread_id)
    return HTTPException(
        status_code=500,
        detail=f"Something went wrong. Reference: {error_id}",
    )
```

Tested by setting `GROQ_API_KEY=gsk_invalid` and restarting. The browser got 54 bytes:

```json
{"detail": "Something went wrong. Reference: bfae1768"}
```

The server log got the full traceback, headed `chat failed [bfae1768] thread=err-test-5` and ending in `groq.AuthenticationError: Error code: 401 - 'Invalid API Key'`. A customer reads eight characters down the phone; you search the logs for them and land on the exact failure.

`logger.exception()` only works inside an `except` block — that's how it knows which traceback to print.

### Prompts shape, code enforces — confirmed again

The first cancel attempt over HTTP came back `needs_approval: false`, with the agent saying:

> *"I see that order ORD-7783 is still processing, so it can be cancelled. Please reply with **yes** if you'd like me to go ahead and cancel it."*

The **model** asked for confirmation, following the system prompt, and never requested the tool — so the graph never paused and the code gate never fired. It took a second message ("yes") before `cancel_order` was actually requested, and only then did `needs_approval: true` come back.

That's Chapter 5's rule surviving the move to HTTP intact: a prompt is a request the model usually honours; `interrupt_before` is physics. Chapter 5 already showed the model skipping its own confirmation on a second attempt in the same session. The gate is what doesn't depend on the model's cooperation.

### Testing the gate in both directions

A gate that blocks everything looks identical to a working gate, right up until a real customer needs a real cancellation. So both paths were run, and **both were verified against the file on disk, not against what the agent said**:

| Test | Agent said | `git status` |
|---|---|---|
| `{"approved": false}` | *"Understood—I won't cancel the order."* | `data/orders.json` **not** modified |
| `{"approved": true}` | *"Your order ORD-7783 has been cancelled successfully."* | `data/orders.json` **modified** |

Chapter 6's lesson is why this matters: the model will say plausible things regardless of what actually happened. `git checkout data/orders.json` resets the mock DB afterwards, as always.

### Mistakes made, and the lesson from each

1. **A virtual environment cannot be moved.** Moving the project to `C:\projects\` in Step 7 broke `pip` with an error naming the *old* Downloads path. On Windows, installing a CLI tool into a venv creates a tiny `.exe` launcher with the absolute path to that venv's `python.exe` baked inside it. Move the folder and every launcher points at a path that no longer exists. Activation still worked, because `Activate.ps1` computes its own location at runtime; only the `.exe` shims are frozen.
   *Rule:* never move a venv. Delete it and rebuild: `deactivate`, `Remove-Item -Recurse -Force .venv`, `py -m venv .venv`, activate, `pip install -r requirements.txt`.
   *Silver lining:* the rebuild proved `requirements.txt` can reconstruct the project from nothing — which is exactly what Step 10's Dockerfile will do on a Linux machine that has never seen this laptop. Running the eval suite afterwards returned **12 passed, 0 failed, 1 expected failure**, unchanged, on a fresh set of package versions. That's the Chapter 7 suite paying for itself on something that wasn't an agent bug.

2. **`Ctrl+C` is "kill", not "copy".** Cancelled a `pip install` halfway through (`ERROR: Operation cancelled by user`). Second time this has happened; it also appears in Chapter 1. Use Ctrl+Shift+C, or select and right-click.

3. **The editor is not the disk.** `api.py` looked like 85 lines in VS Code. `/docs` said **"No operations defined in spec!"** — meaning zero routes were registered. `type api.py` in the terminal showed the file was **two lines long**; the paste had never landed.
   *Rule:* when code behaves as though it doesn't exist, check the disk with `type <file>`, not the editor tab. Same family as the Step 7 unsaved-`cases.jsonl` bug, and it will not be the last.
   *Corollary:* "No operations defined in spec" almost always means routes didn't register — truncated file, typo'd decorator, or uvicorn pointing at the wrong object.

4. **One terminal for the server, one for everything else.** The server was killed three separate times by typing into its terminal — once by Ctrl+C to clear a bad paste, once by pasting `Activate.ps1` into it, once by a stray command. A dead server shows up in `/docs` as **"Failed to fetch"** with no status code at all. Ignore the CORS suggestions it offers; those are generic guesses. No status code means nothing is listening.
   *Rule:* server in terminal 1, never touched. Git and everything else in terminal 2 (the `+` button in the VS Code terminal panel).

5. **Pasted terminal output back into the terminal.** PowerShell tried to execute git's output as code, hit `PS` and the prompt text, and threw `Unexpected token 'PS'`. The `>>` continuation problem from Chapter 1's notes. Nothing ran, nothing was harmed, but several minutes were lost working out what had happened.

6. **`--reload` does not watch `.env`.** Editing `.env` and waiting for a reload does nothing — uvicorn watches `.py` files, and the Groq client is built at import time anyway. Three separate attempts to test the error handler came back 200 because the server was never actually restarted.
   *Rule:* `.env` changes need a manual Ctrl+C and restart. Also worth knowing: `load_dotenv()` does **not** overwrite an environment variable that already exists, so a stale system-level variable would silently win over the file. Checked with `$env:GROQ_API_KEY` — empty, so not the cause here, but it's the first thing to check next time a `.env` change appears to do nothing.

7. **SQLite writes side files.** `checkpoints.db-shm` and `checkpoints.db-wal` appeared as untracked once a long-running server held the database open continuously — they're the write-ahead log and shared memory, holding recent changes before they fold into the main file. They're runtime data like `checkpoints.db` itself. Gitignored (a single `checkpoints.db*` would cover all three).

8. **The real API key ended up in a chat window** while debugging the `.env` file. It was never committed — `.gitignore` did its job — but it was still exposed. Rotated at console.groq.com: revoke the old key, generate a new one, update `.env`. A leaked key is leaked regardless of how it leaked.

### Known limitations (carried into Step 9 / 10)

- **No auth on any endpoint.** Anyone who can reach the URL can cancel orders. Fine on `127.0.0.1`; not fine the moment this is deployed in Step 10.
- **`agent_langgraph.py` has no `groq.BadRequestError` handling**, unlike `agent_raw.py`. Chapter 6's malformed-tool-call bug can still crash a request over HTTP where the terminal agent would recover and retry. The error handler turns it into a clean 500 rather than a leak, but the retry is missing.
- **The eval suite still runs against `agent_raw.py`.** Nothing tests the API at all — not the endpoints, not the session behaviour, not the approval gate. Both approval paths were verified by hand, once. That's not a regression guard.
- **`/approve` assumes one pending approval per thread.** If a model ever requested two risky tools in one turn, only the first name is reported, and approving resumes all of them.
- **`checkpoints.db` grows forever.** No cleanup, no expiry, no limit on thread count.

### How to verify

```powershell
# terminal 1 — server only, nothing else typed in here
uvicorn api:api --reload
# wait for "Application startup complete" (20-30s while ChromaDB loads)

# terminal 2 — everything else
curl http://127.0.0.1:8000/health      # {"status":"ok"}
```

Then at `http://127.0.0.1:8000/docs`:

```json
// memory survives a restart: run, Ctrl+C the server, restart, run the second one
{"message": "Where is my order ORD-7781?", "thread_id": "user-1"}
{"message": "What was that order number again?", "thread_id": "user-1"}   // -> ORD-7781

// threads are isolated
{"message": "What did I just ask you?", "thread_id": "user-2"}            // -> no idea

// the approval gate, both directions
{"message": "Cancel order ORD-7783", "thread_id": "gate-test"}            // agent asks first
{"message": "yes", "thread_id": "gate-test"}                             // -> needs_approval: true
// then POST /approve with {"thread_id": "gate-test", "approved": false}
```

```powershell
git status                      # after approved:false -> orders.json NOT modified
                                # after approved:true  -> orders.json modified
git checkout data/orders.json   # reset the mock DB after testing
```

### Commits

`step8-add-fastapi-deps`, `step8-chat-endpoint`, `step8-sessions`, `step8-approval-endpoint`, `step8-gitignore-sqlite-wal`, `step8-error-handling`.

## Chapter 9 — Gradio: a face for the API

**Goal:** a chat window in a browser that talks to the endpoints from Chapter 8. Type a question, read a formatted answer, click a button to approve a cancellation.

**Time taken:** one session, and it went smoothly — which is itself worth noting. Chapter 8 did the hard thinking; this chapter mostly spends it.

### The one architectural decision

Gradio could reach the agent two ways:

**A. Import it.** `from api import chat` and call it as a Python function. One process, least code.
**B. Make HTTP requests** to `http://127.0.0.1:8000/chat`, exactly as Swagger's `/docs` page does.

**B**, and the reason matters more than the code. If the UI imports the agent, the API becomes decorative — it could break and nothing would notice. If the UI speaks HTTP, it is a real client: it proves the API works on every single message, it could run on a different machine, and the UI can be replaced without touching the agent.

The price is two processes. `uvicorn` on port 8000, `python ui.py` on port 7860, and the UI has to behave sensibly when the other one isn't running.

### What was built

| File | Purpose |
|---|---|
| `ui.py` | Gradio app. Chat box, per-session thread id, Approve/Reject buttons, a collapsed Debug panel. Talks to the API over HTTP only. |
| `api.py` | Added `tool_names_used()`; `tool_calls` is back in every response. |
| `requirements.txt` | Added `gradio` and `requests`. |

Three terminals from here on: **1** uvicorn (never typed into), **2** git and everything else, **3** Gradio (never typed into).

### Concepts, in plain English

**`gr.Blocks`** is a layout container. Everything inside the `with` block becomes part of the page, top to bottom. There's a simpler `gr.Interface` for one-function demos, but `Blocks` is what allows buttons that appear and disappear, so the chapter starts there rather than migrating later.

**The event model is three things:** `fn` (the Python function to run), `inputs` (components whose values get passed in, in order), `outputs` (components that receive what the function returns, in order). `box.submit(fn=send, inputs=[...], outputs=[...])` is the whole wiring.

**`gr.State`** is a variable Gradio keeps **per browser session**. This is what makes threads work:

```python
thread_id = gr.State(value=new_thread_id)
```

Passing the *function* — no parentheses — is the important detail. Gradio calls it once per connected browser, so every tab gets its own id. Write `value=new_thread_id()` and every visitor on earth shares a single conversation. It would look fine in testing with one tab open and be a nasty bug to find later.

**The chatbot is a view, not the truth.** `gr.Chatbot` holds the visible transcript, but the real conversation lives in `checkpoints.db` on the server, keyed by thread. Refresh the page and the chat window empties while the agent still remembers everything — because memory travels with the `thread_id`, not with the UI.

**`gr.update(...)`** changes a component's *properties* from inside a handler, rather than its value. `gr.Row(visible=False)` starts hidden; returning `gr.update(visible=True)` reveals it. Same mechanism disables the textbox.

### The approval buttons — where Chapter 8's design pays off

The `/chat` response shape was designed in Chapter 8 specifically for this moment:

```json
{"answer": "...", "thread_id": "...", "needs_approval": true, "pending_tool": "cancel_order"}
```

The UI checks **one boolean**. It never reads the English text and guesses. When `needs_approval` is true:

- a warning line goes into the chat naming the tool
- the Approve / Reject row becomes visible
- **the textbox is disabled**

That third one isn't cosmetic. Before the buttons existed, the agent said *"I need your approval before I run: cancel_order"* and the natural next move was to type a guess — `cancel_order` was the guess actually tried — which went to `/chat` as an ordinary message and did nothing, because the approval doesn't live in the conversation at all. It lives in `checkpoints.db` as a frozen graph state that only `/approve` can unfreeze.

Disabling the box is the same principle as `interrupt_before` one layer up: don't rely on the user choosing correctly, remove the wrong path.

Clicking a button calls `/approve` instead of `/chat`, and writes "Approved." or "Rejected." into the visible transcript so the page records what happened. The server already knows; that line is for the human reading it.

**Verified both directions, against the file on disk:**

| Action | Agent said | `git status` |
|---|---|---|
| Reject | *"Understood—I won't proceed with the cancellation."* | `data/orders.json` untouched |
| Approve | *"Your order ORD-7783 has been cancelled successfully."* | `data/orders.json` modified |

### Errors the agent isn't responsible for

`call_api()` has three separate `except` branches, because three different failures need three different sentences:

| Exception | Cause | Message |
|---|---|---|
| `ConnectionError` | uvicorn isn't running | "Could not reach the agent... Is uvicorn running?" |
| `Timeout` | agent took over 120s | "The agent took too long to respond." |
| `HTTPError` | a 4xx or 5xx came back | "The agent returned an error." + the `detail` field |

`r.raise_for_status()` is what turns a 500 response into an exception, which means Chapter 8's error reference finally reaches a human who could read it out: *"Something went wrong. Reference: bfae1768."*

`timeout=120` matters — `requests` waits **forever** by default, and an agent making several tool calls genuinely takes 10–20 seconds. Generous but bounded.

### Two things that came free

**Markdown renders.** The API returns `"**ORD-7781** has been shipped\n\n- **Carrier:** Delhivery"`. In `/docs` that's literal asterisks and escaped newlines; in `gr.Chatbot` it's bold text and bullet points, because `render_markdown` defaults to `True`.

**Thread isolation became visible.** Chapter 8 proved it with a JSON field. Here it's two browser tabs: ask ORD-7781 in one, ask "what did I just ask?" in the other, get a blank stare. Same mechanism, but now it's something you can show someone.

### The Debug panel

A `gr.Accordion("Debug", open=False)` at the bottom holds the `thread_id` and the list of tools called. Closed by default, so a customer never sees it, and nothing has to be stripped out before Step 10.

Getting the tool list back required a change to `api.py`. Chapter 8's first version of `/chat` returned `tool_calls`; the field was dropped when the endpoint moved to LangGraph in 8.3 and nobody noticed until the UI wanted it. A small, healthy pattern: **building the client reveals what the API should have exposed.**

```python
def tool_names_used(config):
    names = []
    for m in graph.get_state(config).values["messages"]:
        for tc in getattr(m, "tool_calls", None) or []:
            names.append(tc["name"])
    return names
```

Note this returns every tool called on the **whole thread**, not just the last turn — the graph state holds the full conversation. For a debug panel that's arguably more useful, but it will confuse the counts if you forget.

Why bother: Chapter 3's fix took the earbuds question from 8 tool calls down to 1, and Chapter 7 locked that in with `max_tool_calls: 1`. The Debug panel shows the same signal live. If `search_products` ever appears six times for one question, the tool has started starving the model again — visible immediately, without opening a log file.

### Mistakes made, and the lesson from each

1. **Wrote code against a library version that doesn't exist yet.** `gr.Chatbot(type="messages", ...)` threw `TypeError: got an unexpected keyword argument 'type'`. The installed Gradio was **6.27.0**, where the messages format is the only format and the parameter has been removed entirely.

   The fix was not to guess again. Ask the library what it accepts:

   ```powershell
   python -c "import gradio as gr, inspect; print(inspect.signature(gr.Chatbot.__init__))"
   ```

   That printed every parameter, confirmed `type` was gone, and also confirmed `render_markdown=True` was already the default. A second check on `gr.Textbox` confirmed `submit_btn` still existed, catching the *next* mismatch before it crashed.

   *Rule:* `inspect.signature(SomeClass.__init__)` is to a Python library what `client.models.list()` is to Groq — the way to ask instead of assume. This is Chapter 1's retired-model-name lesson in a different costume, and it will keep coming back. Fast-moving libraries move fast.

2. **Typed a guess at the approval prompt.** With no buttons yet, the agent said *"I need your approval before I run: cancel_order"*, so `cancel_order` got typed into the box. It went to `/chat` as an ordinary message and achieved nothing. Not really a mistake — it's the correct instinct, and it's precisely why the buttons exist and why the textbox now locks. A UI that requires the user to guess a magic word is a broken UI.

3. **Reused one browser session for both approval tests.** Thread `ui-294e1728c73e` cancelled ORD-7783 and then declined a cancellation, so the transcript reads oddly. Harmless in testing; worth using a fresh tab per scenario when the transcript is evidence.

### Known limitations (carried into Step 10)

- **Still no auth anywhere.** Now more pressing: `demo.launch(share=True)` would hand anyone a public URL that can cancel orders.
- **Gradio publishes its own API on 7860** (the "Use via API" link at the bottom of the page). So there are now two APIs, not one. Worth knowing before anything goes on the public internet.
- **The chat window empties on refresh** while the server still remembers the thread. Reloading the visible history from the server on page load is possible and not done.
- **`checkpoints.db` now grows one thread per browser session**, and nothing ever cleans it up.
- **Nothing tests the UI**, and the evals still run only against `agent_raw.py`.

### How to verify

```powershell
# terminal 1 - the API
uvicorn api:api --reload      # wait for "Application startup complete"

# terminal 3 - the UI
python ui.py                  # serves http://127.0.0.1:7860
```

At `http://127.0.0.1:7860`:

1. *"Where is my order ORD-7781?"* → formatted answer, real bold and bullets
2. *"What did I just ask?"* → it remembers
3. Open a **second tab**, ask the same → no idea who you are
4. *"Cancel order ORD-7783"* → *"yes"* → warning line, buttons appear, textbox greys out
5. Click **Reject** → declines, buttons vanish, textbox unlocks
6. **Debug** accordion → `thread_id` and the list of tools called

```powershell
# terminal 2
git status                      # after Reject -> orders.json NOT modified
                                # after Approve -> orders.json modified
git checkout data/orders.json   # reset the mock DB after testing
```

Also worth doing once: stop uvicorn, send a message, and confirm the UI says *"Could not reach the agent"* instead of showing a traceback.

### Commits

`step9-gradio-health-check`, `step9-chat-ui`, `step9-approval-buttons`, `step9-tool-calls-debug-panel`.

## Chapter 10 — Docker, a public URL, and evals that run themselves

**Goal:** stop the agent being something that only exists while a laptop is on. Put it on the internet at a URL anyone can open, and make the eval suite run on every push instead of when somebody remembers.

**Time taken:** one long session, including a mid-step change of hosting provider that turned out to be the most useful thing in the chapter.

### What was built

| File | Purpose |
|---|---|
| `Dockerfile` | The recipe: clean Linux box → Python → requirements → code → build the RAG index → run |
| `start.sh` | Starts uvicorn in the background, waits for it, then starts Gradio |
| `.dockerignore` | Keeps `.venv/`, `chroma_db/` and friends out of the image |
| `.github/workflows/evals.yml` | Runs the 13 eval cases on every push to `main` |

Live at `https://ecom-support-agent.onrender.com`. `api.py`, `ui.py`, `tools.py`, `rag.py` — all unchanged except one line in `ui.py`.

### The thing that happened halfway through

The plan, written in Chapter 9, said Hugging Face Spaces. It had been the standard free answer for hosting a demo like this for years, and it's in every tutorial.

It isn't any more. Hugging Face now requires a paid plan (PRO for personal accounts) for any Space that runs compute — both the Docker and Gradio SDKs. Only Static Spaces remain free. The change landed around July 2026 and there was a formal community complaint about it.

Checking the alternatives turned up more of the same. Fly.io has no free tier for new signups, just a 2-VM-hour trial. Railway gives a one-time $5 credit. Koyeb's status is genuinely unclear — sources disagree about whether the free compute tier still exists. Render still has a real free tier for Docker web services with no credit card, and that's where it went.

**Here's the part worth keeping.** Changing hosting provider mid-step cost **two lines**:

- deleted the `useradd` / `USER` block (an HF-specific uid-1000 requirement)
- changed `demo.launch()` to read a `PORT` environment variable

That's it. The Dockerfile, `start.sh`, `.dockerignore`, and the entire application moved to a completely different company's infrastructure without touching anything else.

This is the actual argument for containers, and it arrived by accident rather than as a lecture. The recipe describes a machine, not a vendor. Whoever runs it is a detail.

*Lesson beyond Docker:* deployment platforms' free tiers evaporate. Heroku killed its free tier in 2022, Fly.io in 2024, Hugging Face in 2026. Anything that pins a project to one provider's specific magic is a liability. Anything portable survives.

### Concepts, in plain English

**A container is a written recipe for a computer.** Start from a clean Linux box with Python on it, install these packages, copy this code in, run this command. Anyone who follows the recipe gets an identical machine.

The venv breaking in Chapter 8 was this problem in miniature: a project that secretly depended on one folder on one laptop. `requirements.txt` fixed it for packages; the Dockerfile fixes it for everything else.

**Layers and caching.** Each line in a Dockerfile makes a layer, and Docker caches them. Hence:

```dockerfile
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
```

Requirements change rarely, code changes constantly. In this order, editing `ui.py` doesn't reinstall 110 packages. Reverse the two `COPY` lines and every build is a full reinstall.

**The index has to be built, not copied.** `chroma_db/` is gitignored, so it's not in the repo the platform clones. `RUN python rag.py` builds it during the image build, so it's baked in and startup is fast. The `.gitignore` habit that's protected the project all along finally needed a deliberate workaround.

**`.dockerignore` is not `.gitignore`.** Docker doesn't read `.gitignore`, so `COPY . .` would happily copy `.venv/` — hundreds of megabytes — into the image. On a 512MB free tier that matters. `.env` is in there too as a belt-and-braces measure.

### Two processes, one container

HF Spaces and Render both expose a single port. The app needs two: uvicorn on 8000, Gradio on 7860.

Two ways to solve it:

**A. Two processes, one entrypoint.** A shell script starts uvicorn in the background and Gradio in the foreground. Port 8000 stays private inside the container; the outside world only sees the UI port.

**B. Mount Gradio inside FastAPI.** One process, `gradio.mount_gradio_app()`, uvicorn serves both.

**A was chosen**, and the reason is Chapter 9's reason. The UI talks to the API over HTTP precisely so the API stays honest. B would turn every message into the server calling itself — works, but it throws away the separation and can deadlock under load. A costs a three-line script and changes no application code at all.

The script has one non-obvious piece:

```bash
uvicorn api:api --host 127.0.0.1 --port 8000 &

python -c "
import time, requests
for i in range(60):
    try:
        requests.get('http://127.0.0.1:8000/health', timeout=2)
        print('API is up', flush=True)
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('API never started')
"

python ui.py
```

The `&` backgrounds uvicorn. The loop then **waits for it to actually be ready** — ChromaDB takes 20–30 seconds to load, and without the wait Gradio would start instantly and the first visitor would get "Could not reach the agent." That error path, written in Chapter 9 for a laptop where uvicorn might not be running, turns out to describe a real production race condition.

This is also the first real use of `/health`. It exists precisely to answer "are you alive?" without involving the agent, the API key, or ChromaDB.

**Two opposite bind addresses, both correct:**

| Process | Binds to | Why |
|---|---|---|
| uvicorn | `127.0.0.1` | Private. Only reachable from inside the container. |
| Gradio | `0.0.0.0` | Public. Accepts connections from outside. |

`0.0.0.0` means "any network interface." Gradio's default of `127.0.0.1` inside a container means the container talking to itself, which produces a Space that builds perfectly and then shows nothing.

### Render specifics

- **`PORT` environment variable.** Render tells the app which port to bind. `int(os.environ.get("PORT", 7860))` uses it in production and falls back to 7860 locally, so nothing changes on the laptop.
- **`GROQ_API_KEY` and `MODEL`** go in the dashboard as environment variables. `load_dotenv()` finds no `.env` and falls through to the real environment, which is exactly right. `MODEL` matters: without it the code falls back to `llama-3.3-70b-versatile`, which Groq retired — and that failure only appears when a user sends a message.
- **The free tier sleeps** after ~15 minutes idle. First visit after a quiet spell waits 30–60 seconds for a cold start.
- **The filesystem resets** on every restart. `checkpoints.db` and any `cancel_order` writes vanish. For a public demo that's a feature: nobody can permanently break the mock data.

### Auth: the decision that was made deliberately

The URL is public and `cancel_order` writes to disk. Three options were on the table: a Gradio login, a demo mode where `cancel_order` reports success without writing, or leaving it open.

**Left open, on purpose.** The whole point of the project is the approval gate working, and a fake `cancel_order` would make the most interesting feature a lie. The data is mock, the container resets, and a visitor cancelling ORD-7783 costs nothing. It's documented loudly in the README rather than hidden.

### Evals on every push

`.github/workflows/evals.yml` runs on every push to `main`, on pull requests, and on a manual button (`workflow_dispatch`). Seven steps: checkout, Python, install, validate `cases.jsonl`, build the index, run the evals, check the mock data was restored.

Chapter 7 built a suite so the agent couldn't regress silently, then left the running of it to human memory. This closes that gap. It also tests `requirements.txt` on a clean Linux machine continuously — the thing the venv rebuild proved once, by accident.

Two steps are worth pointing at.

**The JSONL check runs before the expensive steps.** It's the same one-liner from Chapter 7, promoted into CI, so a missing `}` fails in 30 seconds instead of after four minutes of installs.

**The last step verifies a claim:**

```yaml
- name: Check the mock data was restored
  run: git diff --exit-code data/orders.json
```

Chapter 7 said the runner snapshots and restores `orders.json` in a `finally`. That was trusted. Now it's checked, automatically, on every push, forever. A suite that quietly mutates its own fixtures is worse than no suite — and this is how you know it doesn't.

**Secrets.** `${{ secrets.GROQ_API_KEY }}` in the YAML is a placeholder; GitHub substitutes the real value at run time and masks it in logs. The workflow file is public and gives nothing away. The key now lives in three places, none of them in a readable file:

| Where | How |
|---|---|
| Laptop | `.env`, gitignored |
| Render | Dashboard environment variable |
| GitHub Actions | Repository secret, injected at run time |

Same pattern everywhere: code names the variable, the platform supplies the value.

### What the first green run showed

```
12 passed, 0 failed, 1 expected failures, 0 unexpected passes
```

Timings: install 43s, build the index 6s, run the evals 51s.

Two things in the log worth noting.

**Every single case used exactly 1 tool call.** Chapter 3's earbuds question — once 8 calls and a step-limit failure — and everything else. `max_tool_calls: 1` holding across the whole suite, on someone else's machine.

**The XFAIL failed differently.** Three earlier runs all stretched the returns policy to cover exchanges. This one didn't:

> *"Sure, I can help with that! Could you please share your order ID so I can check its status and see if it's eligible for..."*

It treated an exchange question as an order question instead. Still XFAIL, because the check looks for a hand-off phrase and there isn't one — but the **failure mode itself varies between runs**. That matters for Phase 3: the training data has to cover both behaviours, and the "before" number needs several runs to mean anything. A baseline measured once isn't a baseline.

### Mistakes made, and the lesson from each

1. **Planned against a free tier that no longer exists.** The Chapter 9 plan named HF Spaces. That was correct information when every tutorial about it was written, and wrong by the time it was needed. *Lesson:* for anything involving a third party's pricing, check the current page before building a plan on it. Free tiers are the least stable thing in software.

2. **`WORKDIR /app` after `USER user`.** The first HF Dockerfile switched to a non-root user and then tried to create a directory at the filesystem root, which that user can't do. Caught by reading it rather than by a failed build — worth the two minutes, because each remote build costs five. *Lesson:* with no local Docker, reading carefully replaces iterating quickly.

3. **`COPY . .` with no `.dockerignore`.** Docker doesn't read `.gitignore`. Would have copied `.venv/` into a 512MB container.

4. **Added the GitHub secret… except it never saved.** The first CI run failed in 51 seconds with `groq.APIConnectionError: Connection error.` The instinct was to suspect a wrong key, or a regional network problem. The Settings page said plainly: *"This repository has no secrets."*
   *Lesson:* an empty secret doesn't produce a clean 401 — the client builds a malformed request and dies at the connection layer instead. When credentials fail, **check the credential exists before theorising about why it's rejected.** Also: GitHub secret names are case-sensitive and a name that doesn't exist substitutes silently as an empty string, with no warning anywhere.

5. **Enabled debug logging when it couldn't help.** GitHub's debug output describes GitHub's own machinery — action resolution, caches, permissions. The failure was a traceback from `run_evals.py`, already complete in the normal log. Harmless, just noise.

### Known limitations

- **No auth.** Deliberate, documented, but real: anyone with the URL can cancel orders.
- **The free tier sleeps**, so a cold visitor waits 30–60 seconds.
- **512MB RAM.** It fits today. ChromaDB plus onnxruntime plus Gradio plus FastAPI is not a lot of headroom, and one more dependency might not fit.
- **State is ephemeral.** `checkpoints.db` dies with every restart, so a conversation can't outlive a sleep cycle. The persistence built in Chapter 4 works — it just has nowhere durable to live on a free tier.
- **CI tests `agent_raw.py` only.** Nothing tests `api.py`, `ui.py`, the sessions, or the approval gate. The deployed thing is not the tested thing.
- **Nothing checks the deployment actually works.** A push could turn the Space into a blank page and the evals would still go green.

### How to verify

```powershell
# locally, unchanged
uvicorn api:api --reload     # terminal 1
python ui.py                 # terminal 3
```

Deployed:

1. Open `https://ecom-support-agent.onrender.com` (allow 30–60s if it's been idle)
2. *"Where is my order ORD-7781?"* → confirms Groq is reachable and `MODEL` is set
3. *"What's your returns policy?"* → confirms `RUN python rag.py` built the index during the image build
4. *"What did I just ask?"* → confirms `checkpoints.db` is writable in the container
5. *"Cancel order ORD-7783"* → *"yes"* → buttons → Approve → confirms the full gate over the public internet
6. Debug accordion → should list all four tools across the session

CI: push anything, then the **Actions** tab. Green tick, and `12 passed, 0 failed, 1 expected failures`.

### Commits

`step10-dockerfile-and-start-script`, `step10-render-dockerfile`, `step10-github-actions-evals`.

### What's next

**Phase 2 is complete.** Chapter 1 was a script printing to a terminal; this is a URL with a human-approval gate and a test suite that runs itself.

Phase 3 is fine-tuning, and Step 11 is the dataset: 300–500 examples teaching the model to say "the policy doesn't cover this" instead of reaching for the nearest adjacent process. The XFAIL's varying behaviour in CI means the first job is measuring the baseline properly — several runs, not one — before writing a single training example.