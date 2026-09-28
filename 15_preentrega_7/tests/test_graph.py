import json

import httpx
import pytest
from langchain_core.messages import AIMessage
from openai import APIError

from app.orchestrator.graph import build_graph, run_analysis
from app.orchestrator.state import AnalysisRequest, SupervisorDecision, SynthesisDecision
from app.orchestrator.tools.research_tool import search_documents


async def test_research_context_has_metadata_not_raw_values(
    analysis_request, documents, monkeypatch
):
    import app.orchestrator.agents.research_agent as research_module

    captured = {}

    async def capture_specialist(
        model, agent, role, instruction, context, selected_tool, max_calls
    ):
        captured.update(role=role, context=context)
        return None, []

    monkeypatch.setattr(research_module, "run_specialist", capture_specialist)
    await research_module.research(
        ScriptedModel([]), analysis_request, "Investigar conceptos", documents
    )
    assert captured["context"]["query"] == analysis_request.query
    assert captured["context"]["groups"] == [
        {"name": "A", "unit": "ms", "n": 5},
        {"name": "B", "unit": "ms", "n": 5},
    ]
    assert "values" not in json.dumps(captured["context"])
    assert "El análisis numérico corresponde al analista" in captured["role"]
    assert "no implica que falten datos" in captured["role"]


class ScriptedModel:
    def __init__(self, routes, specialist=None, claims=("tie", "first")):
        self.routes = iter(routes)
        self.specialist = specialist or {}
        self.claims = claims
        self.calls = []
        self.structured_messages = []

    def with_structured_output(self, schema, method):
        model = self

        class Structured:
            async def ainvoke(self, messages):
                model.calls.append(schema.__name__)
                model.structured_messages.append((schema.__name__, messages))
                if schema is SupervisorDecision:
                    route = next(model.routes)
                    if isinstance(route, Exception):
                        raise route
                    return SupervisorDecision(
                        next_agent=route,
                        instruction="Comparar promedio y dispersión",
                        rubric="Fuentes y cálculos",
                    )
                return SynthesisDecision(
                    explanation="La comparación es descriptiva y debe interpretarse con cautela.",
                    lower_mean=model.claims[0],
                    lower_dispersion=model.claims[1],
                )

        return Structured()

    def bind_tools(self, tools, **kwargs):
        model = self
        selected = tools[0]
        agent = "research" if selected.name == "buscar_fuentes" else "analysis"
        script = model.specialist.get(agent)
        local_calls = 0

        class Bound:
            async def ainvoke(self, messages):
                nonlocal local_calls
                local_calls += 1
                model.calls.append(agent)
                if script:
                    response = next(script)
                    if isinstance(response, Exception):
                        raise response
                    return response
                if local_calls == 1:
                    args = (
                        {"query": "promedio dispersion"} if agent == "research" else {}
                    )
                    return AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": selected.name,
                                "args": args,
                                "id": str(len(model.calls)),
                            }
                        ],
                    )
                return AIMessage(content="Aporte respaldado por la herramienta.")

        return Bound()


async def test_supervisor_describes_actual_capabilities(analysis_request):
    from app.orchestrator.agents.supervisor import decide

    model = ScriptedModel(["clarification"])
    await decide(model, initial(analysis_request))
    system_prompt = model.structured_messages[0][1][0].content
    assert "corpus local estático" in system_prompt
    assert "no tiene búsqueda web" in system_prompt
    assert "n, promedio, mediana y desviación estándar muestral" in system_prompt
    assert "No delegues rango, varianza, p-valores" in system_prompt
    assert "no puede afirmar métricas adicionales" in system_prompt


@pytest.fixture
def analysis_request():
    return AnalysisRequest(
        query="Comparar promedio y dispersion",
        groups=[
            {"name": "A", "unit": "ms", "values": [100, 110, 90, 100, 100]},
            {"name": "B", "unit": "ms", "values": [80, 120, 100, 90, 110]},
        ],
    )


@pytest.fixture
def documents(tmp_path):
    source = {
        "id": "test",
        "title": "Promedio y dispersión",
        "source_url": "https://example.org/statistics",
        "text": "El promedio resume el centro y la dispersion describe variabilidad.",
    }
    (tmp_path / "valid.json").write_text(json.dumps(source), encoding="utf-8")
    return tmp_path


def initial(request):
    return {
        "request": request,
        "messages": [],
        "contributions": [],
        "events": [],
        "decisions": 0,
        "delegations": 0,
        "completed": False,
        "response": "",
        "feedback": "",
    }


@pytest.mark.parametrize(
    "routes",
    [["research", "analysis", "synthesis"], ["analysis", "research", "synthesis"]],
)
async def test_dynamic_success(routes, analysis_request, documents):
    request = analysis_request
    result = await build_graph(ScriptedModel(routes), data_dir=documents).ainvoke(
        initial(request)
    )
    assert result["completed"]
    assert [c.agent for c in result["contributions"]] == routes[:2]
    assert result["contributions"][1].status == "complete"
    assert "7.07107" in result["response"]
    assert "https://example.org/statistics" in result["response"]
    assert len([e for e in result["events"] if e["action"] == "tool"]) == 2


async def test_refinement_preserves_provenance(analysis_request, documents):
    request = analysis_request
    result = await build_graph(
        ScriptedModel(["research", "analysis", "research", "synthesis"]),
        data_dir=documents,
    ).ainvoke(initial(request))
    assert result["completed"]
    assert [c.agent for c in result["contributions"]] == [
        "research",
        "analysis",
        "research",
    ]
    assert len([e for e in result["events"] if e["action"] == "tool"]) == 3


async def test_premature_synthesis_feedback_can_be_repaired(
    analysis_request, documents
):
    request = analysis_request
    result = await build_graph(
        ScriptedModel(["synthesis", "analysis", "research", "synthesis"]),
        data_dir=documents,
    ).ainvoke(initial(request))
    assert result["completed"]
    assert any(e["action"] == "synthesis_blocked" for e in result["events"])


async def test_premature_synthesis_cannot_complete_and_decisions_bounded(
    analysis_request, documents
):
    request = analysis_request
    model = ScriptedModel(["synthesis"] * 10)
    result = await build_graph(model, data_dir=documents).ainvoke(initial(request))
    assert not result["completed"]
    assert model.calls == ["SupervisorDecision"] * 10
    assert any(e["action"] == "decision_limit" for e in result["events"])


async def test_last_failed_specialist_invalidates_success(analysis_request, documents):
    request = analysis_request
    research_script = iter(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "buscar_fuentes", "args": {"query": "promedio"}, "id": "1"}
                ],
            ),
            AIMessage(content="Primera investigación"),
            APIError(
                "secret should never appear",
                request=httpx.Request("GET", "https://example.org"),
                body=None,
            ),
        ]
    )
    model = ScriptedModel(
        ["research", "analysis", "research", "synthesis", "clarification"],
        {"research": research_script},
    )
    result = await build_graph(model, data_dir=documents).ainvoke(initial(request))
    assert not result["completed"]
    assert result["contributions"][0].status == "complete"
    assert result["contributions"][-1].status == "error"
    assert "secret" not in str(result)
    assert any(e["action"] == "synthesis_blocked" for e in result["events"])


async def test_delegations_bounded(analysis_request, documents):
    request = analysis_request
    result = await build_graph(
        ScriptedModel(["research"] * 7), data_dir=documents
    ).ainvoke(initial(request))
    assert not result["completed"]
    assert len(result["contributions"]) == 6
    assert any(e["action"] == "delegation_limit" for e in result["events"])


async def test_specialist_loop_exhaustion_loses_prior_tool_success(
    analysis_request, documents
):
    request = analysis_request
    response = AIMessage(
        content="",
        tool_calls=[
            {"name": "buscar_fuentes", "args": {"query": "promedio"}, "id": "1"}
        ],
    )
    model = ScriptedModel(
        ["research", "clarification"], {"research": iter([response] * 3)}
    )
    result = await build_graph(model, data_dir=documents).ainvoke(initial(request))
    assert result["contributions"][0].status == "incomplete"
    assert result["contributions"][0].sources == []
    assert model.calls.count("research") == 3


async def test_missing_groups_without_provider_call():
    model = ScriptedModel([])
    result = await run_analysis(AnalysisRequest(query="Comparar", groups=[]), model)
    assert not result["completed"]
    assert "dos grupos" in result["response"]
    assert model.calls == []


async def test_single_group_without_provider_call(analysis_request):
    model = ScriptedModel([])
    analysis_request.groups = analysis_request.groups[:1]
    result = await run_analysis(analysis_request, model)
    assert not result["completed"]
    assert "dos grupos" in result["response"]
    assert model.calls == []


async def test_runtime_error_preserves_prior_events(analysis_request):
    model = ScriptedModel(
        ["analysis", "research"],
        {"research": iter([TypeError("private error details")])},
    )
    result = await run_analysis(analysis_request, model)
    assert not result["completed"]
    assert result["contributions"][0]["agent"] == "analysis"
    assert any(e["action"] == "tool" for e in result["events"])
    assert result["events"][-1]["type"] == "TypeError"
    assert "private error details" not in str(result)


async def test_provider_error_sanitized(analysis_request):
    request = analysis_request
    result = await run_analysis(
        request,
        ScriptedModel(
            [
                APIError(
                    "sk-sensitive",
                    request=httpx.Request("GET", "https://example.org"),
                    body=None,
                )
            ]
        ),
    )
    assert not result["completed"]
    assert "sk-sensitive" not in json.dumps(result)
    assert result["events"][0]["type"] == "APIError"


async def test_numeric_claim_contradiction(analysis_request, documents):
    request = analysis_request
    result = await build_graph(
        ScriptedModel(
            ["research", "analysis", "synthesis"], claims=("first", "second")
        ),
        data_dir=documents,
    ).ainvoke(initial(request))
    assert not result["completed"]
    assert any(e["action"] == "claims_rejected" for e in result["events"])


def test_search_hits_no_result_malformed(documents, caplog):
    assert len(search_documents("PROMÉDIO", documents)["sources"]) == 1
    assert search_documents("xyzunknown", documents) == {"sources": [], "errors": []}
    (documents / "broken.json").write_text("{ sensitive", encoding="utf-8")
    result = search_documents("promedio", documents)
    assert result["errors"] == [{"file": "broken.json", "type": "JSONDecodeError"}]
    assert "sensitive" not in caplog.text


def test_missing_document_directory(tmp_path):
    assert (
        search_documents("promedio", tmp_path / "missing")["errors"][0]["type"]
        == "FileNotFoundError"
    )


async def test_no_cross_request_data_contamination(analysis_request):
    request = analysis_request
    from app.orchestrator.tools.statistics_tool import make_statistics_tool

    other = request.model_copy(deep=True)
    other.groups[0].values = [1, 3]
    first = make_statistics_tool(request.groups)
    second = make_statistics_tool(other.groups)
    assert (await first.ainvoke({}))["stats"][0]["mean"] == 100
    assert (await second.ainvoke({}))["stats"][0]["mean"] == 2


async def test_analyst_tool_rejects_replacement_arrays(analysis_request):
    request = analysis_request
    from app.orchestrator.tools.statistics_tool import make_statistics_tool

    output = await make_statistics_tool(request.groups).ainvoke({"values": [1, 2]})
    assert output["stats"][0]["mean"] == 100


async def test_model_replacement_arrays_are_controlled_error(
    analysis_request, documents
):
    response = AIMessage(
        content="",
        tool_calls=[
            {"name": "calcular_estadisticas", "args": {"values": [1, 2]}, "id": "1"}
        ],
    )
    model = ScriptedModel(
        ["analysis", "clarification"],
        {"analysis": iter([response, AIMessage(content="No calculado")])},
    )
    result = await build_graph(model, data_dir=documents).ainvoke(
        initial(analysis_request)
    )
    assert result["contributions"][0].status == "incomplete"
    assert result["contributions"][0].stats == []
    assert any(
        e["action"] == "tool_error" and e["type"] == "ValidationError"
        for e in result["events"]
    )


async def test_multiple_tool_calls_rejected(analysis_request, documents):
    calls = [
        {"name": "buscar_fuentes", "args": {"query": "promedio"}, "id": str(i)}
        for i in range(2)
    ]
    model = ScriptedModel(
        ["research", "clarification"],
        {"research": iter([AIMessage(content="", tool_calls=calls)])},
    )
    result = await build_graph(model, data_dir=documents).ainvoke(
        initial(analysis_request)
    )
    assert result["contributions"][0].status == "incomplete"
    assert any(e["action"] == "tool_limit" for e in result["events"])
    assert not any(e["action"] == "tool" for e in result["events"])


async def test_responses_reasoning_blocks_are_not_in_narrative(
    analysis_request, documents
):
    response = AIMessage(
        content="",
        tool_calls=[
            {"name": "buscar_fuentes", "args": {"query": "promedio"}, "id": "1"}
        ],
    )
    final = AIMessage(
        content=[
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "private reasoning"}],
            },
            {"type": "text", "text": "Texto visible"},
        ]
    )
    model = ScriptedModel(
        ["research", "clarification"], {"research": iter([response, final])}
    )
    result = await build_graph(model, data_dir=documents).ainvoke(
        initial(analysis_request)
    )
    assert result["contributions"][0].narrative == "Texto visible"
    assert "private reasoning" not in str(result)
