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

### What's next

Chapter 2: the agent loop. Reading `agent_raw.py` line by line to understand how a model decides to call a tool, how the result gets fed back, and why there's a `MAX_STEPS` guard.