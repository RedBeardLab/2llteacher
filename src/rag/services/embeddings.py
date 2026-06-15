import time


class Embedder:
    def __init__(self, *, client, model: str = "text-embedding-3-small", retries: int = 3) -> None:
        self._client = client
        self._model = model
        self._retries = retries

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            all_embeddings.extend(self._embed_batch(batch))
        return all_embeddings

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        last_exc = None
        for attempt in range(self._retries + 1):
            try:
                response = self._client.embeddings.create(model=self._model, input=batch)
                data = response.data
                if not data:
                    raise ValueError("No embedding data received")
                return [d.embedding for d in data]
            except Exception as exc:
                last_exc = exc
                if attempt < self._retries:
                    time.sleep(2 ** attempt)
        raise last_exc
