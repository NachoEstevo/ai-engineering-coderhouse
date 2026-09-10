from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from agent import build_graph, recent_messages, run_turn
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatResult
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.errors import GraphRecursionError
from pydantic import Field
from tools import build_tools


class ScriptedModel(FakeMessagesListChatModel):
    seen: list[list[AnyMessage]] = Field(default_factory=list)

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedModel":
        return self

    async def _agenerate(self, messages: list[AnyMessage], **kwargs: Any) -> ChatResult:
        self.seen.append(messages)
        result = self._generate(messages)
        result.generations[0].message = result.generations[0].message.model_copy(
            update={"id": str(uuid4())}
        )
        return result


def call_tool(name: str, arguments: dict[str, str], call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": arguments, "id": call_id, "type": "tool_call"}
        ],
    )


async def test_cycle_returns_tool_error_to_model_and_recovers(tmp_path: Path) -> None:
    model = ScriptedModel(
        responses=[
            call_tool("buscar_incidente", {"servicio": "pagos"}, "first"),
            call_tool("buscar_incidente", {"servicio": "pagos"}, "retry"),
            call_tool(
                "consultar_procedimiento", {"procedimiento_id": "POOL-01"}, "procedure"
            ),
            AIMessage(content="INC-204: revisar conexiones según POOL-01."),
        ]
    )
    async with AsyncSqliteSaver.from_conn_string(
        str(tmp_path / "state.sqlite")
    ) as saver:
        graph = build_graph(model, build_tools(simulate_failure=True), saver)
        result = await run_turn(graph, "Resolvé el incidente de pagos", "support")
    assert len([event for event in result["eventos"] if event["tipo"] == "accion"]) == 3
    error = next(
        message for message in model.seen[1] if isinstance(message, ToolMessage)
    )
    assert error.status == "error"
    assert "temporalmente" in error.content
    assert "POOL-01" in result["respuesta"]


async def test_sqlite_survives_reopen_and_isolates_threads(tmp_path: Path) -> None:
    path = str(tmp_path / "state.sqlite")
    first = ScriptedModel(responses=[AIMessage(content="Recordado: pagos, INC-204.")])
    async with AsyncSqliteSaver.from_conn_string(path) as saver:
        await run_turn(
            build_graph(first, build_tools(), saver),
            "Mi incidente es INC-204 de pagos",
            "a",
        )
    second = ScriptedModel(
        responses=[AIMessage(content="Seguimos."), AIMessage(content="Otra sesión.")]
    )
    async with AsyncSqliteSaver.from_conn_string(path) as saver:
        graph = build_graph(second, build_tools(), saver)
        await run_turn(graph, "¿Y ese incidente?", "a")
        await run_turn(graph, "Hola", "b")
    assert any("INC-204" in str(message.content) for message in second.seen[0])
    assert all("INC-204" not in str(message.content) for message in second.seen[1])


async def test_model_can_answer_without_tools(tmp_path: Path) -> None:
    model = ScriptedModel(
        responses=[AIMessage(content="Hola, ¿en qué servicio necesitás ayuda?")]
    )
    async with AsyncSqliteSaver.from_conn_string(
        str(tmp_path / "state.sqlite")
    ) as saver:
        result = await run_turn(
            build_graph(model, build_tools(), saver), "Hola", "greeting"
        )
    assert not any(event["tipo"] == "accion" for event in result["eventos"])


async def test_incomplete_result_reaches_model_before_clarification(
    tmp_path: Path,
) -> None:
    model = ScriptedModel(
        responses=[
            call_tool("buscar_incidente", {"servicio": "envíos"}, "unknown"),
            AIMessage(content="¿Te referís a pagos o pedidos?"),
        ]
    )
    async with AsyncSqliteSaver.from_conn_string(
        str(tmp_path / "state.sqlite")
    ) as saver:
        result = await run_turn(
            build_graph(model, build_tools(), saver), "Revisá envíos", "unknown"
        )
    assert any(
        isinstance(message, ToolMessage) and "incompleto" in str(message.content)
        for message in model.seen[1]
    )
    assert result["respuesta"] == "¿Te referís a pagos o pedidos?"


async def test_recursion_limit_stops_repeated_tool_calls(tmp_path: Path) -> None:
    model = ScriptedModel(
        responses=[call_tool("buscar_incidente", {"servicio": "pagos"}, "loop")]
    )
    async with AsyncSqliteSaver.from_conn_string(
        str(tmp_path / "state.sqlite")
    ) as saver:
        with pytest.raises(GraphRecursionError):
            await run_turn(
                build_graph(model, build_tools(), saver),
                "Consulta",
                "loop",
                recursion_limit=4,
            )


def test_history_trimming_keeps_complete_tool_exchange() -> None:
    messages = [
        HumanMessage("Vieja consulta"),
        AIMessage(content="Vieja respuesta"),
        HumanMessage("Nueva consulta"),
        call_tool("buscar_incidente", {"servicio": "pagos"}, "current"),
        ToolMessage(content="Resultado", tool_call_id="current"),
    ]
    retained = recent_messages(messages, 1)
    assert retained == messages[2:]
    assert isinstance(retained[0], HumanMessage)


async def test_old_turns_are_removed_from_active_checkpoint(tmp_path: Path) -> None:
    model = ScriptedModel(responses=[AIMessage(content="Respuesta")])
    async with AsyncSqliteSaver.from_conn_string(
        str(tmp_path / "state.sqlite")
    ) as saver:
        graph = build_graph(model, build_tools(), saver, context_turns=2)
        for number in range(4):
            await run_turn(graph, f"Consulta {number}", "trim")
        snapshot = await graph.aget_state({"configurable": {"thread_id": "trim"}})
    human_messages = [
        message.content
        for message in snapshot.values["messages"]
        if isinstance(message, HumanMessage)
    ]
    assert human_messages == ["Consulta 2", "Consulta 3"]
