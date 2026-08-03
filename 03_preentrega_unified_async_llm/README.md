# Pre-entrega 1 - Unified Async LLM Client

Cliente unificado para OpenAI y Anthropic con validación mediante Pydantic, generación asíncrona, streaming de tokens y manejo controlado de errores del SDK.

## Estructura

- `schemas.py`: modelos Pydantic para mensajes, configuración, secretos y respuestas.
- `clients.py`: interfaz común, implementaciones por proveedor y `AsyncLLMManager`.
- `main.py`: prueba una respuesta normal y luego streaming con la pregunta "¿Qué es la entropía?".
- `.env.example`: variables necesarias, sin secretos reales.

## Requisitos

- Python 3.12 o superior.
- Una API key válida de OpenAI o Anthropic.

## Instalación en PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Editá `.env` y configurá un único proveedor:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=tu_clave_real
```

O bien:

```dotenv
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=tu_clave_real
```

## Ejecución

```powershell
python main.py
```

El script imprime primero la respuesta completa y luego los fragmentos recibidos por streaming. Si falta una clave o el SDK devuelve un error de API, se informa un error controlado sin cerrar el event loop.
