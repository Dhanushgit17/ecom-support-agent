from fastapi import FastAPI
from pydantic import BaseModel

from agent_raw import run_agent, SYSTEM_PROMPT

app = FastAPI(title="E-commerce Support Agent")


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": req.message},
    ]

    answer = run_agent(history)

    tool_calls = [
        tc["function"]["name"]
        for m in history
        if m.get("tool_calls")
        for tc in m["tool_calls"]
    ]

    return {"answer": answer, "tool_calls": tool_calls}