import asyncio

from langchain_core.documents import Document


class FakeEnsembleRetriever:
    async def ainvoke(self, query):
        return [
            Document(page_content=str(number), metadata={"source": f"doc-{number}.md"})
            for number in range(8)
        ]


def test_rag_system_returns_only_top_five_documents():
    from retriever import RAGSystem

    system = RAGSystem(FakeEnsembleRetriever(), top_k=5)
    documents = asyncio.run(system.retrieve("asyncio TaskGroup"))

    assert len(documents) == 5
    assert documents[0].metadata["source"] == "doc-0.md"
