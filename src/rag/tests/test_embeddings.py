from django.test import SimpleTestCase

from rag.services.embeddings import Embedder


class FakeEmbeddingData:
    def __init__(self, embedding):
        self.embedding = embedding


class FakeEmbeddings:
    def __init__(self, dimension=1536):
        self.dimension = dimension

    def create(self, *, model, input):
        dim = self.dimension

        class Response:
            data = [FakeEmbeddingData([0.001] * dim) for _ in input]

        return Response()


class FakeOpenAIClient:
    def __init__(self, dimension=1536):
        self.embeddings = FakeEmbeddings(dimension=dimension)


class EmbedderTests(SimpleTestCase):
    def test_embed_returns_one_vector_per_input(self):
        client = FakeOpenAIClient(dimension=1536)
        embedder = Embedder(client=client, model="text-embedding-3-small")
        result = embedder.embed(["hello", "world"])
        self.assertEqual(len(result), 2)

    def test_embed_vectors_have_correct_dimension(self):
        client = FakeOpenAIClient(dimension=1536)
        embedder = Embedder(client=client, model="text-embedding-3-small")
        result = embedder.embed(["hello"])
        self.assertEqual(len(result[0]), 1536)

    def test_embed_handles_different_dimensions(self):
        client = FakeOpenAIClient(dimension=3072)
        embedder = Embedder(client=client, model="text-embedding-3-large")
        result = embedder.embed(["hello"])
        self.assertEqual(len(result[0]), 3072)

    def test_embed_handles_empty_input(self):
        client = FakeOpenAIClient(dimension=1536)
        embedder = Embedder(client=client, model="text-embedding-3-small")
        result = embedder.embed([])
        self.assertEqual(result, [])

    def test_embed_handles_single_input(self):
        client = FakeOpenAIClient(dimension=1536)
        embedder = Embedder(client=client, model="text-embedding-3-small")
        result = embedder.embed(["single text"])
        self.assertEqual(len(result), 1)

    def test_embed_model_name_is_passed_to_client(self):
        client = FakeOpenAIClient(dimension=1536)
        embedder = Embedder(client=client, model="custom-embed-model")
        result = embedder.embed(["test"])
        self.assertEqual(len(result), 1)
