# Mini informe de demostración — Pre-entrega 5

**Fecha:** 10 de septiembre de 2026, 18:50 UTC / 15:50 de Argentina.

**Resultado:** los cinco escenarios de la pasada terminaron correctamente. Se verificaron seis condiciones funcionales y los siete tests locales pasaron. Es una demostración controlada del agente; una sola pasada no mide una tasa de éxito general.

## Qué se demuestra

Un agente de soporte que consulta información, recibe el resultado de una herramienta, decide su siguiente acción y conserva la conversación al reiniciar el programa. Las llamadas al modelo fueron reales, con `gpt-5.6-luna`. Los incidentes y procedimientos son ficticios, y el error temporal se inyectó deliberadamente en la herramienta.

## Datos disponibles y alcance

La pre-entrega 5 utiliza **dos registros de incidentes y dos procedimientos** definidos en `tools.py`:

| Servicio | Incidente | Procedimiento | Responsable |
| --- | --- | --- | --- |
| pagos | INC-204: agotamiento del pool de PostgreSQL | POOL-01: conexiones, liberación y concurrencia | Equipo de plataforma |
| pedidos | INC-305: consumidor detenido | QUEUE-02: diagnóstico, reinicio y confirmación del trabajo | Equipo de operaciones |

Es suficiente para demostrar consultas encadenadas, cambio de contexto, memoria y manejo de información faltante. La base de incidentes está simulada en diccionarios: SQLite almacena los checkpoints de la conversación, no una base productiva de incidentes.

La pre-entrega 4 tiene, por separado, **siete archivos Markdown sobre asyncio**, con **1883 tokens en total** medidos con `cl100k_base`. Cada archivo tiene entre 257 y 282 tokens. Sirven para una demostración pequeña de recuperación híbrida; son demasiado breves para evaluar recuperación documental a escala o el efecto real del overlap de 80 tokens, porque cada archivo cabe en un solo chunk de 600 tokens.

El agente de esta entrega no consulta esos Markdown ni Pinecone. Integrar esa búsqueda como una herramienta sería otro paso, no una capacidad demostrada aquí.

## Preparación y cambios realizados

1. Se definieron dos herramientas asíncronas con `@tool`. Sus docstrings explican cuándo usarlas, qué reciben y qué devuelven. Buscar un incidente aporta el ID del procedimiento, pero no sus pasos: el modelo debe pedirlos mediante otra herramienta.
2. Se construyó un `StateGraph` sobre `AgentState`, que hereda de `MessagesState`. El modelo recibe las herramientas mediante `bind_tools()`. `tools_condition` consulta los `tool_calls` de su respuesta para continuar al nodo de herramientas o finalizar.
3. Se conectó `tools -> model`, de modo que los resultados y errores vuelven al modelo. El programa no clasifica el texto del usuario para elegir una herramienta.
4. Se incorporó `AsyncSqliteSaver` y `thread_id`. Cada consulta de esta pasada se ejecutó en un proceso independiente y abrió nuevamente el mismo archivo SQLite.
5. Se limitaron los pasos del grafo a 10, las entradas a 8000 caracteres y el contexto activo a seis turnos completos. La ventana no separa una llamada de herramienta de su resultado. Los checkpoints históricos permanecen en disco.
6. Para esta pasada se amplió `demo.py` a cinco escenarios y se agregó `--output-dir`. Ahora conserva la salida y los logs de cada proceso, las trazas individuales y la traza consolidada. Un directorio de evidencia existente no se sobrescribe.

La traza contiene acciones observables, argumentos, resultados y respuestas finales. No contiene razonamiento interno privado del modelo.

## Resultados observados

Los primeros cuatro procesos usaron el hilo `demo-01660f69cc`. El quinto usó `demo-01660f69cc-nuevo`, dentro de la misma base SQLite.

| Escenario | Llamadas a herramientas | Tiempo del turno | Resultado observado |
| --- | ---: | ---: | --- |
| Incidente de pagos y resolución, con fallo temporal | 3 | 7,081 s | Reintentó la consulta y obtuvo INC-204 y POOL-01. |
| Responsable del incidente anterior, tras reiniciar | 0 | 1,860 s | Recordó INC-204 y Equipo de plataforma. |
| Servicio inexistente: envíos | 1 | 3,292 s | Informó las opciones válidas y pidió aclaración. |
| Cambio al servicio pedidos | 2 | 5,383 s | Consultó INC-305 y QUEUE-02, sin mezclar los datos de pagos. |
| Referencia al incidente anterior desde un hilo nuevo | 0 | 2,051 s | No asumió un incidente; pidió servicio o ID. |

La suma de los tiempos de los turnos fue **19,667 segundos**, con **seis llamadas a herramientas**. Estos tiempos se miden dentro de `run_turn`; no incluyen todo el arranque de cada proceso. No se midió una distribución de latencias ni el costo facturado de la API.

El ciclo del primer escenario fue:

```text
Usuario: consulta el incidente de pagos y sus pasos de resolución.
Modelo -> buscar_incidente(servicio="pagos")
Herramienta -> error temporal simulado.
Modelo -> buscar_incidente(servicio="pagos")
Herramienta -> INC-204, responsable y procedimiento_id="POOL-01".
Modelo -> consultar_procedimiento(procedimiento_id="POOL-01")
Herramienta -> pasos y criterio de verificación.
Modelo -> respuesta con incidente y procedimiento.
```

El segundo proceso respondió:

> El responsable del incidente **INC-204** es el **Equipo de plataforma**.

El proceso con un hilo nuevo respondió:

> No tengo identificado el incidente al que te referís. ¿Podés indicar el nombre exacto del servicio o el ID del incidente?

## Evidencias

- [Traza consolidada y seis verificaciones automáticas](evidencias/demo_2026-09-10/trace.json)
- [Turno 1: traza](evidencias/demo_2026-09-10/turn-1.json) y [log de ejecución](evidencias/demo_2026-09-10/turn-1.log)
- [Turno 2: memoria](evidencias/demo_2026-09-10/turn-2.json) y [log](evidencias/demo_2026-09-10/turn-2.log)
- [Turno 3: información incompleta](evidencias/demo_2026-09-10/turn-3.json) y [log](evidencias/demo_2026-09-10/turn-3.log)
- [Turno 4: cambio de servicio](evidencias/demo_2026-09-10/turn-4.json) y [log](evidencias/demo_2026-09-10/turn-4.log)
- [Turno 5: aislamiento](evidencias/demo_2026-09-10/turn-5.json) y [log](evidencias/demo_2026-09-10/turn-5.log)
- [Resultado de pytest: 7 tests aprobados](evidencias/demo_2026-09-10/tests.log)

Las verificaciones automáticas comprueban cantidad y nombres de herramientas, observación de error, IDs esperados, memoria sin nuevas consultas y solicitud de aclaración. Se revisaron además las respuestas completas: una comprobación de palabras o signos por sí sola no basta para evaluar calidad semántica.

Los tests usan un modelo simulado y SQLite real para comprobar ciclo, errores, persistencia al reabrir, aislamiento, respuesta sin herramientas, límite de recursión y recorte de mensajes. La demo con OpenAI aporta evidencia adicional de selección autónoma de herramientas.

## Feedback de entregas anteriores aplicado

- **Excepciones y reintentos:** errores de herramienta devueltos al modelo, reintento visible en la traza y manejo específico de errores de OpenAI en el CLI. El SDK dispone de hasta dos reintentos para fallos transitorios de API; esta pasada no provocó un fallo de red de OpenAI.
- **Tiempos de ejecución:** los logs conservan la duración de las llamadas al modelo, herramientas completadas y cada turno.
- **Tests:** siete pruebas locales guardadas como evidencia. El manejo de archivos ilegibles y las correcciones de ingesta pertenecen a la pre-entrega 4, no se atribuyen a este agente.
- **Código simple:** se mantienen dos herramientas, un grafo y una base local. Los docstrings de las herramientas son parte del contrato que lee el modelo.

## Cómo repetir la pasada

Desde `13_preentrega_5`, con `.env` configurado:

```powershell
.\.venv\Scripts\python.exe demo.py --output-dir evidencias/otra_pasada
.\.venv\Scripts\python.exe -m pytest -q
```

Usá un nombre nuevo para cada carpeta de evidencias. La demo crea nuevos hilos y un archivo SQLite bajo `storage/`, que permanece ignorado por Git. `trace_example.json` se actualiza con la última ejecución; esta carpeta fechada conserva la pasada del informe.

Entorno verificado: Python 3.12.13, LangGraph 1.2.11, langgraph-checkpoint-sqlite 3.1.1, langchain-openai 1.6.2 y OpenAI SDK 3.12.0. Modelo Luna, esfuerzo `low`, máximo de 1600 tokens de salida por llamada.

## Límites de la evidencia

Se demuestra el comportamiento en cinco escenarios conocidos, sobre datos ficticios pequeños. No se evaluaron carga concurrente, grandes volúmenes de documentos, disponibilidad de una base productiva ni persistencia multiusuario con autenticación. El cambio de `thread_id` aísla el historial, pero no constituye un mecanismo de autorización.

La demostración se ejecutó localmente. El repositorio incluye la implementación, este informe y los registros; las claves y la base SQLite quedan fuera de Git.
