from __future__ import annotations


class LocalEmbeddingClient:
    def __init__(self, model_path: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Local embedding requires sentence-transformers. "
                "Install dependencies with: pip install -r requirements.txt"
            ) from exc

        self.model_path = model_path
        self.model = SentenceTransformer(model_path)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vectors.tolist()
