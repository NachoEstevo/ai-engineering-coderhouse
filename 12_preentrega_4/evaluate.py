import asyncio
import json
import logging
from pathlib import Path
from time import perf_counter

from config import BASE_DIR, Settings
from retriever import RAGSystem

logger = logging.getLogger(__name__)


def precision_at_k(
    retrieved_sources: list[str],
    relevant_sources: set[str],
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k debe ser mayor que cero")
    retrieved = list(dict.fromkeys(retrieved_sources))[:k]
    relevant_count = len(set(retrieved) & relevant_sources)
    return relevant_count / k


def recall_at_k(
    retrieved_sources: list[str],
    relevant_sources: set[str],
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k debe ser mayor que cero")
    if not relevant_sources:
        raise ValueError("Debe existir al menos una fuente relevante")
    retrieved = set(list(dict.fromkeys(retrieved_sources))[:k])
    return len(retrieved & relevant_sources) / len(relevant_sources)


def reciprocal_rank_at_k(
    retrieved_sources: list[str], relevant_sources: set[str], k: int
) -> float:
    if k < 1:
        raise ValueError("k debe ser mayor que cero")
    for rank, source in enumerate(list(dict.fromkeys(retrieved_sources))[:k], start=1):
        if source in relevant_sources:
            return 1 / rank
    return 0.0


def load_golden_set(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


async def evaluate_golden_set(
    system: RAGSystem,
    cases: list[dict],
    k: int = 5,
) -> dict[str, float]:
    started_at = perf_counter()
    if not cases:
        raise ValueError("El Golden Set debe contener preguntas")
    precisions = []
    recalls = []
    reciprocal_ranks = []

    for case in cases:
        documents = await system.retrieve(case["question"])
        retrieved_sources = [document.metadata["source"] for document in documents]
        relevant_sources = set(case["relevant_sources"])
        precision = precision_at_k(retrieved_sources, relevant_sources, k)
        recall = recall_at_k(retrieved_sources, relevant_sources, k)
        rank = reciprocal_rank_at_k(retrieved_sources, relevant_sources, k)
        precisions.append(precision)
        recalls.append(recall)
        reciprocal_ranks.append(rank)
        print(f"Pregunta: {case['question']}")
        print(f"Fuentes recuperadas: {retrieved_sources}")
        print(
            f"Precision@{k}: {precision:.2f} | Recall@{k}: {recall:.2f} | RR@{k}: {rank:.2f}\n"
        )

    result = {
        f"precision_at_{k}": sum(precisions) / len(precisions),
        f"recall_at_{k}": sum(recalls) / len(recalls),
        f"mrr_at_{k}": sum(reciprocal_ranks) / len(reciprocal_ranks),
    }
    logger.info(
        "Evaluación completada en %.3f segundos",
        perf_counter() - started_at,
    )
    return result


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    system = await RAGSystem.create(settings)
    cases = load_golden_set(BASE_DIR / "golden_set.json")
    metrics = await evaluate_golden_set(system, cases, settings.top_k)
    print("Resumen")
    for name, value in metrics.items():
        print(f"{name}: {value:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
