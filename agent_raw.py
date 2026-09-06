"""
STEP 2: The agent loop with NO framework.
This is what LangGraph / n8n AI Agent node do under the hood.

Run:  python agent_raw.py
"""
import json
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
- If an item is out of stock, say so and suggest an alternative from the catalog.
- Prices are in INR. Be concise and friendly."""

MAX_STEPS = 8  # guard against infinite tool loops


def run_agent(messages: list[dict]) -> str:
    """One user turn: loop until the model answers without a tool call."""
    for step in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.2,
        )
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
