"""
STEP 2: The agent loop with NO framework.
This is what LangGraph / n8n AI Agent node do under the hood.

Run:  python agent_raw.py
"""
import json
import groq
import os

from dotenv import load_dotenv
from groq import Groq

from tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = os.getenv("MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """You are a support agent for an Indian online store.
Rules:
- Use tools to answer; never invent product, order, or policy details.
- Before calling cancel_order, ask the user to confirm and wait for a 'yes'.
- Before asking the customer to confirm a cancellation, always call get_order_status first. If the order's status means it cannot be cancelled, explain why instead of asking for confirmation.
- If an item is out of stock, say so and suggest an alternative from the catalog.
- get_policy returns the nearest passages with a distance score; nearest is not the same as relevant. Only apply a passage that directly addresses the question. If none does, say the policy doesn't cover it and offer a human. Never invent or stretch policy.
- Prices are in INR. Be concise and friendly."""

MAX_STEPS = 8  # guard against infinite tool loops


def run_agent(messages: list[dict]) -> str:
    """One user turn: loop until the model answers without a tool call."""
    for step in range(MAX_STEPS):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.2,
            )
        except groq.BadRequestError as e:
            if "tool_use_failed" not in str(e):
                raise
            print("  [warn] model sent a malformed tool call; asking it to retry")
            messages.append({"role": "user", "content": "Your last tool call had invalid arguments. Re-read the tool schema and try again."})
            continue

        msg = response.choices[0].message

        # No tool call -> final answer
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content})
            return msg.content

        # Model wants tools: record its request, run each tool, append results
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            print(f"  [tool] {name}({args})")
            try:
                result = TOOL_FUNCTIONS[name](**args)
            except Exception as e:  # tools fail in production; never crash the loop
                result = f"Tool error: {e}"
            print(f"  [result] {str(result)[:150]}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

    return "I'm having trouble completing that. Please try again or contact support."


if __name__ == "__main__":
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("E-commerce agent (type 'quit' to exit)\n")
    while True:
        user = input("You: ").strip()
        if user.lower() in {"quit", "exit"}:
            break
        history.append({"role": "user", "content": user})
        print("Agent:", run_agent(history), "\n")
