import asyncio

from langchain_core.documents import Document


class FakeRAGSystem:
    async def retrieve(self, query):
        return [
            Document(page_content="a", metadata={"source": "tasks.md"}),
            Document(page_content="b", metadata={"source": "queues.md"}),
            Document(page_content="c", metadata={"source": "streams.md"}),
            Document(page_content="d", metadata={"source": "timeouts.md"}),
            Document(page_content="e", metadata={"source": "subprocess.md"}),
        ]


def test_precision_and_recall_at_k():
    from evaluate import precision_at_k, recall_at_k

    retrieved = ["tasks.md", "queues.md", "streams.md", "timeouts.md", "subprocess.md"]
    relevant = {"tasks.md", "queues.md"}

    assert precision_at_k(retrieved, relevant, 5) == 0.4
    assert recall_at_k(retrieved, relevant, 5) == 1.0


def test_evaluate_golden_set_returns_average_metrics():
    from evaluate import evaluate_golden_set

    cases = [
        {
            "question": "¿Qué administra TaskGroup?",
            "relevant_sources": ["tasks.md"],
        },
        {
            "question": "¿Cómo funciona Queue?",
            "relevant_sources": ["queues.md"],
        },
    ]

    result = asyncio.run(evaluate_golden_set(FakeRAGSystem(), cases, k=5))

    assert result["precision_at_5"] == 0.2
    assert result["recall_at_5"] == 1.0


def test_metrics_ignore_duplicate_sources_and_reward_rank():
    from evaluate import precision_at_k, recall_at_k, reciprocal_rank_at_k

    sources = ["a.md", "a.md", "b.md", "c.md"]
    relevant = {"b.md", "c.md"}
    assert precision_at_k(sources, relevant, 3) == 2 / 3
    assert recall_at_k(sources, relevant, 3) == 1.0
    assert reciprocal_rank_at_k(sources, relevant, 3) == 0.5
    assert reciprocal_rank_at_k(["b.md", "a.md"], relevant, 3) == 1.0
