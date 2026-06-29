# Persistent memory using RAG.
# At session end, Gemini extracts facts about the user from the conversation.
# Each fact is embedded and stored in ChromaDB.
# On each new request, the query is embedded and the most relevant facts
# are retrieved and added to the system prompt.

import os, uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "memory_db")
TOP_K = 5


def _collection():
    import chromadb
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_or_create_collection(
        name="swift_memory",
        metadata={"hnsw:space": "cosine"},
    )


def _embed(texts: list) -> list:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model.encode(texts, convert_to_numpy=True).tolist()


def _extract_facts(history: list) -> list[str]:
    from model import model
    conversation = "\n".join(f"{e['role']}: {e['content']}" for e in history)
    raw = model(
        f"Extract factual preferences, habits, and personal details about the user from this conversation. "
        f"Return one fact per line, plain text, no bullets or numbering. "
        f"Only include concrete facts (e.g. 'User prefers jazz', 'User wakes at 7am'). "
        f"Ignore small talk, greetings, and one-off requests.\n\n{conversation}",
        0.0,
    )
    return [f.strip() for f in raw.splitlines() if f.strip()]


def save_session(history: list) -> None:
    if len(history) < 2:
        return

    facts = _extract_facts(history)
    if not facts:
        return

    session_id = str(uuid.uuid4())
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    collection = _collection()
    embeddings = _embed(facts)

    ids = [f"{session_id}_{i}" for i in range(len(facts))]
    metadatas = [{"session_id": session_id, "timestamp": ts} for _ in facts]

    collection.add(ids=ids, embeddings=embeddings, documents=facts, metadatas=metadatas)
    print(f"[Memory] Saved {len(facts)} facts from this session.")


def load_context(query: str) -> str:
    collection = _collection()
    if collection.count() == 0:
        return ""

    query_embedding = _embed([query])[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(TOP_K, collection.count()),
        include=["documents", "metadatas"],
    )

    facts = results["documents"][0]
    if not facts:
        return ""

    lines = ["Facts about the user:"]
    lines.extend(facts)
    return "\n".join(lines)
