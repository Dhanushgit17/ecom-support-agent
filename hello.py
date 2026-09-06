import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])
r = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "Reply with exactly: plumbing works"}],
)
print(r.choices[0].message.content)
print("tokens used:", r.usage.total_tokens)