from langchain_core.language_models import BaseChatModel

from ..agents.common import run_specialist
from ..state import AnalysisRequest, Contribution
from ..tools.statistics_tool import make_statistics_tool


async def analysis(
    model: BaseChatModel,
    request: AnalysisRequest,
    instruction: str,
    max_calls: int = 3,
    research_context: Contribution | None = None,
) -> tuple[Contribution, list[dict]]:
    context = {"groups": [g.model_dump() for g in request.groups]}
    if research_context is not None and research_context.status == "complete":
        context["research"] = {
            "narrative": research_context.narrative,
            "sources": [s.model_dump() for s in research_context.sources],
        }
    return await run_specialist(
        model,
        "analysis",
        "Sos analista de estadística descriptiva. Calculá ambos grupos originales. No afirmes significancia ni causalidad.",
        instruction,
        context,
        make_statistics_tool(request.groups),
        max_calls,
    )
