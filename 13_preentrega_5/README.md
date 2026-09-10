# Pre-entrega 5 - Agente cíclico con memoria persistente

Agente de soporte técnico con LangGraph, OpenAI y SQLite. Consulta una base ficticia de incidentes y procedimientos. El modelo elige las herramientas según la consulta y sus descripciones; el programa no clasifica el prompt con rutas manuales.

## Archivos

| Archivo | Responsabilidad |
| --- | --- |
| `tools.py` | Dos herramientas `@tool`: consultar incidentes y procedimientos simulados. |
| `agent.py` | Estado, grafo cíclico, persistencia, ventana de contexto y traza de cada turno. |
| `config.py` | Variables de entorno validadas y clave como `SecretStr`. |
| `main.py` | Ejecutar una consulta con `thread_id` y manejo de errores. |
| `demo.py` | Ejemplo real multi-paso, error recuperable y memoria entre procesos. |
| `trace_example.json` | Acciones, observaciones y respuestas de la demostración real. |
| `INFORME_DEMO.md` | Mini informe con alcance, resultados medidos y enlaces a evidencias. |
| `tests/test_agent.py` | Pruebas locales del ciclo, memoria, aislamiento, recursión y recorte. |

## Preparación

Desde esta carpeta, con Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completá `.env` con tu clave de OpenAI:

```dotenv
OPENAI_API_KEY=tu_clave_real
OPENAI_MODEL=gpt-5.6-luna
```

El modelo predeterminado es Luna, con esfuerzo `low` y un máximo de 1600 tokens de salida por llamada. Requiere acceso a ese modelo y saldo de API. Las herramientas y SQLite son locales; no se utiliza Pinecone en esta entrega.

`.env`, `.venv` y `storage/` están ignorados por Git. Los datos del ejemplo son ficticios. No publiques trazas de consultas personales sin revisarlas.

## Consulta y memoria

```powershell
python main.py "¿Qué incidente tiene pagos y cómo se resuelve?" --thread-id soporte-1
python main.py "¿Quién es el responsable de ese incidente?" --thread-id soporte-1
```

Cada comando inicia otro proceso. El segundo recupera el historial de `soporte-1` desde `storage/checkpoints.sqlite`. Un `thread_id` distinto comienza otra conversación. Ejecutá los turnos de un mismo hilo secuencialmente.

Para guardar la traza visible de un turno:

```powershell
python main.py "¿Qué incidente tiene pedidos?" --thread-id soporte-2 --trace storage/consulta.json
```

## Grafo y persistencia

```text
START -> model -> tools -> model -> ... -> END
```

`AgentState` hereda de `MessagesState`, que incorpora el reducer `add_messages`. Cada nodo devuelve una actualización del estado. El nodo de modelo usa `llm.bind_tools()` y la arista `tools_condition` decide si ejecutar `ToolNode` o terminar según los `tool_calls` devueltos por el modelo.

El checkpointer es `AsyncSqliteSaver`, la variante asíncrona de `SqliteSaver` del paquete `langgraph-checkpoint-sqlite`. Se abre con `async with` para cerrar la conexión correctamente. Guarda los mensajes por `thread_id` después de cada paso.

El estado activo conserva los últimos seis turnos completos del usuario, sin separar llamadas y respuestas de herramientas. Los turnos anteriores se retiran usando `RemoveMessage`; los checkpoints históricos permanecen en SQLite. Si se necesita un dato fuera de esa ventana, el agente debe volver a consultarlo o pedirlo. SQLite sirve para este ejercicio local; la retención histórica no es ilimitada en un servicio real.

## Resiliencia y límites

- `recursion_limit=10` acota los pasos del grafo, no diez llamadas al modelo. El CLI captura `GraphRecursionError` y muestra un mensaje controlado.
- `ToolNode` transforma errores esperados `ToolException` en observaciones que el modelo recibe. El prompt pide reintentar una vez ante un fallo temporal.
- Un servicio desconocido devuelve `estado=incompleto` y las opciones disponibles para que el agente pida aclaración.
- El cliente OpenAI tiene timeout de 30 segundos y hasta dos reintentos del SDK ante fallos transitorios. Los errores de API agotados se capturan en el CLI sin imprimir claves ni respuestas de error completas.
- Las consultas se limitan a 8000 caracteres. Se registran tiempos del modelo, herramientas y turno completo.

## Demostración multi-paso

```powershell
python demo.py
```

La demostración inicia cinco procesos independientes. Los primeros cuatro comparten `thread_id` y archivo SQLite; el quinto utiliza otro hilo en la misma base:

1. Pregunta por el incidente de pagos y su resolución. La primera consulta a la herramienta falla deliberadamente. El modelo debe reintentar y consultar el procedimiento obtenido.
2. Pregunta quién es el responsable sin repetir el servicio ni el ID. Esto comprueba la memoria después de cerrar el proceso anterior.
3. Consulta un servicio inexistente, `envíos`, para observar la solicitud de aclaración.
4. Cambia a `pedidos` y consulta su incidente y procedimiento.
5. Pregunta por el incidente anterior desde un hilo nuevo, para comprobar que no hereda el contexto.

Para conservar los logs y las trazas de cada turno en una carpeta presentable:

```powershell
python demo.py --output-dir evidencias/otra_pasada
```

Elegí una carpeta que no exista; así no se sobrescribe evidencia anterior. La [pasada documentada](INFORME_DEMO.md) está en `evidencias/demo_2026-09-10/` y contiene cinco trazas individuales, cinco logs, la traza consolidada y el resultado de los tests. La base SQLite sigue en `storage/`.

`--simulate-failure` solo activa ese fallo controlado para la demostración; no decide qué herramienta ejecutar. La selección la realiza el modelo. Los `if` del CLI y la demo controlan argumentos y casos de prueba, no enrutan la consulta del agente.

El archivo `trace_example.json` registra una ejecución real del 10 de septiembre de 2026. La primera pregunta produjo tres llamadas: `buscar_incidente`, otro `buscar_incidente` después del error y `consultar_procedimiento`. El siguiente proceso recordó `INC-204` y `Equipo de plataforma` sin consultar herramientas. Ante `envíos` pidió aclaración.

La traza registra decisiones observables (herramienta y argumentos), resultados y respuestas. No pide ni inventa razonamiento interno privado del modelo. Volver a ejecutar la demo reemplaza la traza de ejemplo; cada ejecución usa una base y un hilo nuevos dentro de `storage/`.

## Pruebas sin API

```powershell
python -m pytest -q
```

Los tests usan respuestas de modelo simuladas y SQLite real en carpetas temporales. Verifican el comportamiento del grafo; la elección autónoma de herramientas se verifica adicionalmente con `demo.py` y la API real. Las consultas de la demo sí consumen API.

## Referencias

- [Herramientas y ToolNode](https://docs.langchain.com/oss/python/langchain/tools)
- [Memoria y gestión de mensajes en LangGraph](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [Implementación oficial de AsyncSqliteSaver](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-sqlite/langgraph/checkpoint/sqlite/aio.py)
- [Modelo GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
