import uuid

import gradio as gr
import requests

API_URL = "http://127.0.0.1:8000"


def new_thread_id():
    return f"ui-{uuid.uuid4().hex[:12]}"


def send(message, history, thread_id):
    """Post one message to /chat and append the exchange to the visible history."""
    if not message.strip():
        return history, ""

    history = history + [{"role": "user", "content": message}]

    try:
        r = requests.post(
            f"{API_URL}/chat",
            json={"message": message, "thread_id": thread_id},
            timeout=120,
        )
        r.raise_for_status()
        answer = r.json()["answer"]
    except requests.exceptions.ConnectionError:
        answer = f"Could not reach the agent at {API_URL}. Is uvicorn running?"
    except requests.exceptions.Timeout:
        answer = "The agent took too long to respond. Please try again."
    except requests.exceptions.HTTPError:
        answer = f"The agent returned an error. {r.json().get('detail', '')}"

    history = history + [{"role": "assistant", "content": answer}]
    return history, ""


with gr.Blocks(title="E-commerce Support Agent") as demo:
    gr.Markdown("# E-commerce Support Agent")

    thread_id = gr.State(value=new_thread_id)

    chatbot = gr.Chatbot(height=450, label="Conversation")
    box = gr.Textbox(
        placeholder="Ask about an order, a product, or a policy...",
        show_label=False,
        submit_btn=True,
    )

    box.submit(fn=send, inputs=[box, chatbot, thread_id], outputs=[chatbot, box])


if __name__ == "__main__":
    demo.launch()