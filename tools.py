"""
E-commerce tools. Each tool is a plain Python function + a JSON schema.
This is the same "tool" concept as an n8n node, except you own the code.
"""
import csv
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"


# ---------- Tool implementations ----------

def search_products(query: str, category: str | None = None, max_price_inr: float | None = None) -> str:
    """Keyword search over the catalog. Always returns in-stock alternatives too."""
    q = query.lower()
    matches, in_stock_nearby = [], []
    with open(DATA / "products.csv", newline="") as f:
        for row in csv.DictReader(f):
            row["in_stock"] = int(row["stock"]) > 0
            same_cat = (not category) or row["category"] == category.lower()
            if same_cat and row["in_stock"]:
                in_stock_nearby.append(row)
            text = f"{row['name']} {row['category']} {row['description']}".lower()
            keyword_hit = q in text or any(w in text for w in q.split())
            price_ok = not max_price_inr or float(row["price_inr"]) <= max_price_inr
            if keyword_hit and same_cat and price_ok:
                matches.append(row)

    alternatives = [r for r in in_stock_nearby if r not in matches][:3]
    return json.dumps({
        "matches": matches[:5],
        "in_stock_alternatives": alternatives,
        "note": "Suggest from in_stock_alternatives if matches are empty or out of stock. Do not search again.",
    })

def get_order_status(order_id: str) -> str:
    """Look up an order by ID."""
    orders = json.loads((DATA / "orders.json").read_text())
    order = orders.get(order_id.upper().strip())
    return json.dumps(order) if order else f"Order {order_id} not found."


def get_policy(topic: str) -> str:
    """Return the store policy section for: returns, shipping, cancellations."""
    text = (DATA / "policies.md").read_text()
    sections = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current:
            sections[current].append(line)
    key = topic.lower().strip()
    if key in sections:
        return "\n".join(sections[key]).strip()
    return f"No policy for '{topic}'. Available: {', '.join(sections)}"


def cancel_order(order_id: str) -> str:
    """Cancel an order if it is still processing. (Writes to the mock DB.)"""
    path = DATA / "orders.json"
    orders = json.loads(path.read_text())
    oid = order_id.upper().strip()
    if oid not in orders:
        return f"Order {oid} not found."
    if orders[oid]["status"] != "processing":
        return f"Cannot cancel: order {oid} is already '{orders[oid]['status']}'."
    orders[oid]["status"] = "cancelled"
    path.write_text(json.dumps(orders, indent=2))
    return f"Order {oid} cancelled. Refund of Rs {orders[oid]['total_inr']} will be issued in 5-7 business days."


# ---------- Registry: name -> function ----------

TOOL_FUNCTIONS = {
    "search_products": search_products,
    "get_order_status": get_order_status,
    "get_policy": get_policy,
    "cancel_order": cancel_order,
}

# ---------- Schemas the LLM sees (OpenAI function-calling format) ----------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the product catalog by keyword, optional category and max price (INR).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords, e.g. 'running shoes'"},
                    "category": {"type": "string", "description": "footwear, electronics, apparel, home, fitness"},
                    "max_price_inr": {"type": "number"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Get status, ETA and tracking for an order ID like ORD-7781.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy",
            "description": "Fetch the store policy on a topic: returns, shipping, or cancellations.",
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_order",
            "description": "Cancel an order. Only call after the user explicitly confirms they want to cancel.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
]
