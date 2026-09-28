import asyncio
import statistics

from langchain_core.tools import StructuredTool, tool
from pydantic import BaseModel, ConfigDict

from state import GroupStatistics, SampleGroup


def compute_statistics(groups: list[SampleGroup]) -> list[GroupStatistics]:
    return [
        GroupStatistics(
            name=g.name,
            unit=g.unit,
            n=len(g.values),
            mean=statistics.mean(g.values),
            median=statistics.median(g.values),
            stdev=statistics.stdev(g.values),
        )
        for g in groups
    ]


class StatisticsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


def make_statistics_tool(groups: list[SampleGroup]) -> StructuredTool:
    captured = [g.model_copy(deep=True) for g in groups]

    @tool(args_schema=StatisticsArguments)
    async def calcular_estadisticas() -> dict:
        """Calcula n, promedio, mediana y desviación estándar muestral de los grupos originales del usuario. No acepta ni reemplaza datos."""
        results = await asyncio.to_thread(compute_statistics, captured)
        return {"stats": [r.model_dump() for r in results]}

    return calcular_estadisticas
