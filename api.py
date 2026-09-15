import logging
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent_langgraph import app as graph
from langchain_core.messages import HumanMessage

logger = logging.getLogger("api")

api = FastAPI(title="E-commerce Support Agent")

NEEDS_APPROVAL = {"cancel_order"}


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


class ApproveRequest(BaseModel):
    thread_id: str
    approved: bool


def pending_tool_names(config):
    """Names of the tool calls the graph is paused before, or [] if not paused."""
    state = graph.get_state(config)
    if not state.next:
        return []
    return [tc["name"] for tc in state.values["messages"][-1].tool_calls]


def run_until_done_or_approval(config, first_input):
    """Resume the graph, stopping if a tool needs human approval."""
    result = graph.invoke(first_input, config)

    while True:
        pending = pending_tool_names(config)
        if not pending:
            break
        risky = [n for n in pending if n in NEEDS_APPROVAL]
        if risky:
            return {
                "answer": f"I need your approval before I run: {', '.join(risky)}.",
                "thread_id": config["configurable"]["thread_id"],
                "needs_approval": True,
                "pending_tool": risky[0],
            }
        result = graph.invoke(None, config)

    return {
        "answer": result["messages"][-1].content,
        "thread_id": config["configurable"]["thread_id"],
        "needs_approval": False,
        "pending_tool": None,
    }


def server_error(where: str, thread_id: str):
    """Log the full traceback, return a generic message with a lookup id."""
    error_id = uuid.uuid4().hex[:8]
    logger.exception("%s failed [%s] thread=%s", where, error_id, thread_id)
    return HTTPException(
        status_code=500,
        detail=f"Something went wrong. Reference: {error_id}",
    )


@api.get("/health")
def health():
    return {"status": "ok"}


@api.post("/chat")
def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    try:
        return run_until_done_or_approval(
            config, {"messages": [HumanMessage(content=req.message)]}
        )
    except Exception:
        raise server_error("chat", req.thread_id)


@api.post("/approve")
def approve(req: ApproveRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    try:
        pending = pending_tool_names(config)
        if not pending:
            return {
                "answer": "There is nothing waiting for approval on this thread.",
                "thread_id": req.thread_id,
                "needs_approval": False,
                "pending_tool": None,
            }

        if not req.approved:
            graph.update_state(
                config,
                {"messages": [HumanMessage(content="I do not approve that action. Do not run it.")]},
                as_node="tools",
            )

        return run_until_done_or_approval(config, None)
    except Exception:
        raise server_error("approve", req.thread_id)