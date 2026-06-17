from pathlib import Path
import sys
import os

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(REPO_ROOT))

from detection.semantic.embedding_matcher import EmbeddingMatcher
from detection.semantic.config import DETECTION_ROOT, load_model_config
from detection.semantic.fact_store import expand_fact_texts, file_sha256, load_facts
from detection.semantic.hash_embedding_client import HashEmbeddingClient
from detection.semantic.local_embedding_client import LocalEmbeddingClient
from detection.semantic.openai_compatible_client import OpenAICompatibleClient


def main() -> None:
    config = load_model_config()
    fact_path = DETECTION_ROOT / "data" / "simulated" / "confidential_facts.jsonl"
    print(f"loading facts: {fact_path}", flush=True)
    facts = load_facts(fact_path)
    rows = expand_fact_texts(facts)
    print(f"loaded {len(facts)} facts, expanded to {len(rows)} texts", flush=True)
    api_client = OpenAICompatibleClient()
    local_embedding_path = os.getenv("LOCAL_EMBEDDING_MODEL_PATH")
    if local_embedding_path:
        embedding_client = LocalEmbeddingClient(local_embedding_path)
        embedding_model = local_embedding_path
    elif api_client.embedding_configured:
        embedding_client = api_client
        embedding_model = api_client.embedding_model
    else:
        embedding_client = HashEmbeddingClient()
        embedding_model = "hash-embedding-client-v1"

    print(f"embedding model: {embedding_model}", flush=True)
    print(f"index path: {config.vector_index_path}", flush=True)
    matcher = EmbeddingMatcher(embedding_client, threshold=0.78)
    status = matcher.build_or_load_index(
        rows=rows,
        index_path=config.vector_index_path,
        source_sha256=file_sha256(fact_path),
        embedding_model=embedding_model,
    )
    print(f"index {status}: {len(rows)} texts, model={embedding_model} -> {config.vector_index_path}")


if __name__ == "__main__":
    main()
