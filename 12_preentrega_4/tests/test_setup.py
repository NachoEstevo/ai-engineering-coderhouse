import asyncio


class IndexList:
    def __init__(self, names):
        self._names = names

    def names(self):
        return self._names


class Description:
    def __init__(self, dimension=1536):
        self.dimension = dimension
        self.status = {"ready": True}


class FakePinecone:
    def __init__(self, names=None, dimension=1536):
        self.names = names or []
        self.dimension = dimension
        self.created = []

    def list_indexes(self):
        return IndexList(self.names)

    def create_index(self, **kwargs):
        self.created.append(kwargs)
        self.names.append(kwargs["name"])

    def describe_index(self, name):
        return Description(self.dimension)


def test_ensure_index_creates_missing_serverless_index():
    from config import Settings
    from pinecone_setup import ensure_index

    settings = Settings(
        pinecone_api_key="pc",
        openai_api_key="oa",
        index_name="asyncio-rag-test",
    )
    client = FakePinecone()

    asyncio.run(ensure_index(settings, client=client, poll_interval=0))

    assert len(client.created) == 1
    assert client.created[0]["dimension"] == 1536
    assert client.created[0]["metric"] == "cosine"


def test_ensure_index_rejects_dimension_mismatch():
    from config import Settings
    from pinecone_setup import ensure_index

    settings = Settings(
        pinecone_api_key="pc",
        openai_api_key="oa",
        index_name="asyncio-rag-test",
    )
    client = FakePinecone(names=["asyncio-rag-test"], dimension=768)

    try:
        asyncio.run(ensure_index(settings, client=client, poll_interval=0))
    except ValueError as error:
        assert "768" in str(error)
        assert "1536" in str(error)
    else:
        raise AssertionError("El mismatch de dimensiones debía fallar")
