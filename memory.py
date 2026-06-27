# Persistent memory using RAG.
# Each conversation turn gets embedded and stored in ChromaDB at session end.
# On each new request, the current query is embedded and the most similar
# past turns are pulled and added to the system prompt.

import os, uuid, time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "memory_db")
TOP_K = 5  # number of past turns to retrieve per query


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


def save_session(history: list) -> None:
    if len(history) < 2:
        return

    session_id = str(uuid.uuid4())
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    collection = _collection()

    texts = [entry["content"] for entry in history]
    embeddings = _embed(texts)

    ids, metadatas = [], []
    for i, entry in enumerate(history):
        ids.append(f"{session_id}_{i}")
        metadatas.append({
            "session_id": session_id,
            "timestamp": ts,
            "role": entry["role"],
            "index": i,
        })

    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)


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

    docs = results["documents"][0]
    metas = results["metadatas"][0]

    if not docs:
        return ""

    lines = ["Relevant past context:"]
    for doc, meta in zip(docs, metas):
        role = meta.get("role", "unknown").capitalize()
        ts = meta.get("timestamp", "")
        lines.append(f"[{ts}] {role}: {doc}")

    return "\n".join(lines)
