from fastapi import FastAPI
from pydantic import BaseModel

from agent_langgraph import app as graph
from langchain_core.messages import HumanMessage

api = FastAPI(title="E-commerce Support Agent")


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


@api.get("/health")
def health():
    return {"status": "ok"}


@api.post("/chat")
def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    result = graph.invoke({"messages": [HumanMessage(content=req.message)]}, config)

    # Auto-resume through interrupts. NO approval gate yet -- see Task 8.4.
    while graph.get_state(config).next:
        result = graph.invoke(None, config)

    last = result["messages"][-1]
    return {"answer": last.content, "thread_id": req.thread_id}