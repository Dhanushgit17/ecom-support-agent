"""
Minimal RAG over data/policies.md: chunk -> embed -> retrieve.
ChromaDB's built-in embedder (all-MiniLM, on-device) does the embedding.
"""
from pathlib import Path

import chromadb

DATA = Path(__file__).parent / "data"
_client = chromadb.PersistentClient(path=str(Path(__file__).parent / "chroma_db"))


def chunk_markdown(text: str) -> list[dict]:
    """One chunk per bullet, prefixed with its section heading."""
    chunks, heading = [], "General"
    for block in text.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("# "):
            continue
        lines = block.splitlines()
        if lines[0].startswith("## "):
            heading = lines[0][3:].strip()
            lines = lines[1:]
        for line in lines:
            line = line.strip().lstrip("-").strip()
            if line:
                chunks.append({"heading": heading, "text": f"{heading}: {line}"})
    return chunks


def build_index() -> int:
    """(Re)build the vector index from policies.md. Returns number of chunks."""
    chunks = chunk_markdown((DATA / "policies.md").read_text())
    if "policies" in [c.name for c in _client.list_collections()]:
        _client.delete_collection("policies")
    col = _client.create_collection("policies")
    col.add(
        ids=[f"chunk-{i}" for i in range(len(chunks))],
        documents=[c["text"] for c in chunks],
        metadatas=[{"heading": c["heading"]} for c in chunks],
    )
    return len(chunks)

def ensure_index() -> None:
    if "policies" not in [c.name for c in _client.list_collections()]:
        build_index()


def retrieve_policy(question: str, k: int = 3) -> str:
    """Return the k most relevant policy passages, with a distance score (lower = closer)."""
    ensure_index()
    col = _client.get_collection("policies")
    res = col.query(query_texts=[question], n_results=k, include=["documents", "distances"])
    pairs = zip(res["documents"][0], res["distances"][0])
    return "\n\n".join(f"- (distance {d:.2f}) {p}" for p, d in pairs) or "No policy found."


if __name__ == "__main__":
    n = build_index()
    print(f"Indexed {n} chunks.")
    for q in ["can I send shoes back after wearing them?", "how long does delivery take?", "I want to stop my order", "what happens if my parcel arrives damaged?"]:
        print(f"\nQ: {q}\n{retrieve_policy(q)}")