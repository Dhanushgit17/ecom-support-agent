"""
STEP 3: Same agent, rebuilt in LangGraph (the production-standard way).
What you gain over agent_raw.py:
  - State is explicit (graph + typed state)
  - Checkpointer = conversation memory keyed by thread_id
  - interrupt_before = human approval before risky tools (cancel_order)
  - LangSmith tracing with two env vars

Run:  python agent_langgraph.py
"""
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent_raw import SYSTEM_PROMPT
from tools import cancel_order, get_order_status, get_policy, search_products

load_dotenv()

# Wrap plain functions as LangChain tools (schema is inferred from signature + docstring)
TOOLS = [tool(search_products), tool(get_order_status), tool(get_policy), tool(cancel_order)]

llm = ChatGroq(model=os.getenv("MODEL", "llama-3.3-70b-versatile"), temperature=0.2)
llm_with_tools = llm.bind_tools(TOOLS)


def call_model(state: MessagesState):
    msgs = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    return {"messages": [llm_with_tools.invoke(msgs)]}


# ---- Build the graph ----
graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode(TOOLS))
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", tools_condition)  # -> "tools" or END
graph.add_edge("tools", "agent")

app = graph.compile(
    checkpointer=SqliteSaver(sqlite3.connect("checkpoints.db", check_same_thread=False)),
    interrupt_before=["tools"],   # pause before ANY tool; we approve only cancel_order below
)


def chat(thread_id: str, text: str) -> str:
    config = {"configurable": {"thread_id": thread_id}}
    result = app.invoke({"messages": [HumanMessage(content=text)]}, config)

    # Resume through interrupts; ask a human only for destructive tools
    while app.get_state(config).next:
        pending = result["messages"][-1].tool_calls
        if any(tc["name"] == "cancel_order" for tc in pending):
            ok = input(f"  [approval needed] run {pending}? (y/n): ").lower().startswith("y")
            if not ok:
                return "Okay, I won't cancel anything."
        result = app.invoke(None, config)  # None = continue from checkpoint

    return result["messages"][-1].content


if __name__ == "__main__":
    print("LangGraph e-commerce agent (type 'quit' to exit)\n")
    while True:
        user = input("You: ").strip()
        if user.lower() in {"quit", "exit"}:
            break
        print("Agent:", chat("user-1", user), "\n")
