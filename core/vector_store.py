"""
Persistent vector store for user confidential libraries.
Uses ChromaDB for vector storage and similarity search.
"""
import asyncio
import os
import time
from typing import Any

import chromadb
from chromadb.config import Settings

from detection.semantic.fact_store import expand_fact_texts
from detection.semantic.hash_embedding_client import HashEmbeddingClient
from detection.semantic.local_embedding_client import LocalEmbeddingClient
from detection.semantic.openai_compatible_client import OpenAICompatibleClient

# ChromaDB client singleton
_chroma_client: chromadb.ClientAPI | None = None


def _get_embedding_client():
    """Get the configured embedding client."""
    local_path = os.getenv("LOCAL_EMBEDDING_MODEL_PATH")
    if local_path:
        return LocalEmbeddingClient(local_path)
    api_client = OpenAICompatibleClient()
    if api_client.embedding_configured:
        return api_client
    return HashEmbeddingClient()

# Debounce timers for single additions
_debounce_timers: dict[str, float] = {}
_debounce_lock = asyncio.Lock()

VECTOR_STORE_DIR = os.getenv("VECTOR_STORE_DIR", "data/vector_store")
DEBOUNCE_SECONDS = int(os.getenv("VECTOR_DEBOUNCE_SECONDS", "60"))


def _get_chroma_client() -> chromadb.ClientAPI:
    """Get or create ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=VECTOR_STORE_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


def _get_collection(user_id: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection for a user."""
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=f"user_{user_id.replace('-', '_')}",
        metadata={"hnsw:space": "cosine"},
    )


def _generate_embedding(texts: list[str], embedding_client) -> list[list[float]]:
    """Generate embeddings for texts using the configured embedding client."""
    return embedding_client.embed(texts)


def vectorize_user_facts_sync(user_id: str, facts: list[dict[str, Any]], embedding_client):
    """Synchronously vectorize and store user's confidential facts in ChromaDB."""
    rows = expand_fact_texts(facts)
    if not rows:
        # Clear the collection if no facts
        try:
            client = _get_chroma_client()
            client.delete_collection(f"user_{user_id.replace('-', '_')}")
        except Exception:
            pass
        return

    collection = _get_collection(user_id)

    # Clear existing data
    try:
        collection.delete(where={})
    except Exception:
        pass

    # Prepare data
    ids = [f"{row['fact_id']}_{row['text_type']}" for row in rows]
    texts = [row["text"] for row in rows]
    metadatas = [
        {
            "fact_id": row["fact_id"],
            "fact_type": row["fact_type"],
            "text_type": row["text_type"],
            "confidential_level": row.get("confidential_level", "high"),
        }
        for row in rows
    ]

    # Generate embeddings
    embeddings = _generate_embedding(texts, embedding_client)

    # Store in ChromaDB
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )


def search_user_vectors_sync(user_id: str, text: str, embedding_client, top_k: int = 3) -> dict[str, Any]:
    """Search user's vector store in ChromaDB."""
    try:
        collection = _get_collection(user_id)
    except Exception:
        return {"matched": False, "top_hit": None, "top_k": []}

    if collection.count() == 0:
        return {"matched": False, "top_hit": None, "top_k": []}

    # Generate query embedding
    query_embedding = _generate_embedding([text], embedding_client)[0]

    # Search
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    if not results["ids"][0]:
        return {"matched": False, "top_hit": None, "top_k": []}

    hits = []
    for i, doc_id in enumerate(results["ids"][0]):
        # ChromaDB returns distances (lower = more similar for cosine)
        # Convert to similarity: 1 - distance
        distance = results["distances"][0][i]
        similarity = max(0, 1 - distance)

        hits.append({
            "fact_id": results["metadatas"][0][i].get("fact_id", ""),
            "fact_type": results["metadatas"][0][i].get("fact_type", ""),
            "text_type": results["metadatas"][0][i].get("text_type", ""),
            "confidential_level": results["metadatas"][0][i].get("confidential_level", "high"),
            "similarity": round(similarity, 6),
            "text": results["documents"][0][i],
        })

    best = hits[0] if hits else None
    return {
        "matched": bool(best and best["similarity"] >= 0.78),
        "top_hit": best,
        "top_k": hits,
    }


async def vectorize_user_facts(user_id: str, facts: list[dict[str, Any]], embedding_client):
    """Immediately vectorize and store user's confidential facts."""
    await asyncio.to_thread(vectorize_user_facts_sync, user_id, facts, embedding_client)


async def debounce_vectorize(user_id: str, facts: list[dict[str, Any]], embedding_client):
    """Debounce vectorization for single additions."""
    async with _debounce_lock:
        _debounce_timers[user_id] = time.time()

    await asyncio.sleep(DEBOUNCE_SECONDS)

    async with _debounce_lock:
        if user_id in _debounce_timers:
            elapsed = time.time() - _debounce_timers[user_id]
            if elapsed >= DEBOUNCE_SECONDS - 1:
                del _debounce_timers[user_id]
                await vectorize_user_facts(user_id, facts, embedding_client)


def search_user_vectors(user_id: str, text: str, embedding_client, top_k: int = 3) -> dict[str, Any]:
    """Search user's vector store."""
    return search_user_vectors_sync(user_id, text, embedding_client, top_k)
