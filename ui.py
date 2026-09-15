import uuid

import gradio as gr
import requests

API_URL = "http://127.0.0.1:8000"

NO_TOOLS = "*No tools called yet.*"


def new_thread_id():
    return f"ui-{uuid.uuid4().hex[:12]}"


def call_api(path, payload):
    """POST to the agent. Returns (answer, needs_approval, pending_tool, tool_calls)."""
    try:
        r = requests.post(f"{API_URL}{path}", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return (
            data["answer"],
            data.get("needs_approval", False),
            data.get("pending_tool"),
            data.get("tool_calls", []),
        )
    except requests.exceptions.ConnectionError:
        return f"Could not reach the agent at {API_URL}. Is uvicorn running?", False, None, []
    except requests.exceptions.Timeout:
        return "The agent took too long to respond. Please try again.", False, None, []
    except requests.exceptions.HTTPError:
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except ValueError:
            pass
        return f"The agent returned an error. {detail}", False, None, []


def render(history, answer, needs_approval, pending_tool, tool_calls):
    """Append the answer and set every control to match the approval state."""
    if needs_approval:
        note = f"⚠️ Approval needed to run **{pending_tool}**."
        history = history + [{"role": "assistant", "content": note}]
    else:
        history = history + [{"role": "assistant", "content": answer}]

    if tool_calls:
        tools_md = "**Tools called:** " + ", ".join(f"`{n}`" for n in tool_calls)
    else:
        tools_md = NO_TOOLS

    return (
        history,
        "",
        gr.update(visible=needs_approval),
        gr.update(interactive=not needs_approval),
        tools_md,
    )


def send(message, history, thread_id, tools_md):
    if not message.strip():
        return history, "", gr.update(visible=False), gr.update(interactive=True), tools_md

    history = history + [{"role": "user", "content": message}]
    answer, needs_approval, pending_tool, tool_calls = call_api(
        "/chat", {"message": message, "thread_id": thread_id}
    )
    return render(history, answer, needs_approval, pending_tool, tool_calls)


def decide(approved, history, thread_id):
    history = history + [
        {"role": "user", "content": "Approved." if approved else "Rejected."}
    ]
    answer, needs_approval, pending_tool, tool_calls = call_api(
        "/approve", {"thread_id": thread_id, "approved": approved}
    )
    return render(history, answer, needs_approval, pending_tool, tool_calls)


with gr.Blocks(title="E-commerce Support Agent") as demo:
    gr.Markdown("# E-commerce Support Agent")

    thread_id = gr.State(value=new_thread_id)

    chatbot = gr.Chatbot(height=450, label="Conversation")

    with gr.Row(visible=False) as approval_row:
        approve_btn = gr.Button("Approve", variant="primary")
        reject_btn = gr.Button("Reject", variant="stop")

    box = gr.Textbox(
        placeholder="Ask about an order, a product, or a policy...",
        show_label=False,
        submit_btn=True,
    )

    with gr.Accordion("Debug", open=False):
        thread_label = gr.Markdown()
        tools_label = gr.Markdown(NO_TOOLS)

    demo.load(fn=lambda t: f"`thread_id: {t}`", inputs=thread_id, outputs=thread_label)

    outputs = [chatbot, box, approval_row, box, tools_label]

    box.submit(
        fn=send,
        inputs=[box, chatbot, thread_id, tools_label],
        outputs=outputs,
    )

    approve_btn.click(
        fn=lambda h, t: decide(True, h, t),
        inputs=[chatbot, thread_id],
        outputs=outputs,
    )
    reject_btn.click(
        fn=lambda h, t: decide(False, h, t),
        inputs=[chatbot, thread_id],
        outputs=outputs,
    )


if __name__ == "__main__":
    demo.launch()