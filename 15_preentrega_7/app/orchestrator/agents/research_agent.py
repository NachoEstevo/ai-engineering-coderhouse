from pathlib import Path

from langchain_core.language_models import BaseChatModel

from ..agents.common import run_specialist
from ..state import AnalysisRequest, Contribution
from ..tools.research_tool import make_research_tool


async def research(
    model: BaseChatModel,
    request: AnalysisRequest,
    instruction: str,
    directory: Path,
    max_calls: int = 3,
) -> tuple[Contribution, list[dict]]:
    context = {
        "query": request.query,
        "groups": [
            {"name": group.name, "unit": group.unit, "n": len(group.values)}
            for group in request.groups
        ],
    }
    return await run_specialist(
        model,
        "research",
        "Sos investigador de estadística descriptiva. Recuperá conceptos y fuentes locales pertinentes y explicá sus límites. "
        "El análisis numérico corresponde al analista; no calcules ni compares resultados numéricos. "
        "Recibís metadatos de los grupos, no sus valores: no ver los valores no implica que falten datos en la solicitud.",
        instruction,
        context,
        make_research_tool(directory),
        max_calls,
    )
