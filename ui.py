import gradio as gr
import requests

API_URL = "http://127.0.0.1:8000"


def check_health():
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        return f"API says: {r.json()}"
    except requests.exceptions.RequestException as e:
        return f"Could not reach the API at {API_URL}. Is uvicorn running?\n\n{type(e).__name__}"


with gr.Blocks(title="E-commerce Support Agent") as demo:
    gr.Markdown("# E-commerce Support Agent")
    status = gr.Textbox(label="Status", interactive=False)
    check = gr.Button("Check API")
    check.click(fn=check_health, outputs=status)


if __name__ == "__main__":
    demo.launch()