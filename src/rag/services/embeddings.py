class Embedder:
    def __init__(self, *, client, model: str = "text-embedding-3-small") -> None:
        self._client = client
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in response.data]
