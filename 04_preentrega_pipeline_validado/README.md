# Pre-entrega 2 - Pipeline de procesamiento validado

Pipeline LCEL que extrae entidades técnicas desde un texto y devuelve un objeto Pydantic validado.

## Componentes

- `schemas.py`: contrato `ExtraccionTecnica` con tecnologías obligatorias, criticidad (`baja`, `media`, `alta`) y resumen técnico.
- `chain.py`: `ChatPromptTemplate | ChatOpenAI.with_structured_output(ExtraccionTecnica)` con `.with_retry(stop_after_attempt=2)`. El prompt recibe separadamente el texto y las instrucciones de extracción.
- `main.py`: ejemplo asíncrono con `.ainvoke()` a través de `process_text()`.
- `.env.example`: configuración requerida, sin secretos.

## Instalación

Desde esta carpeta, en PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Editá `.env` y cargá una clave válida de OpenAI:

```dotenv
OPENAI_API_KEY=tu_clave_real
OPENAI_MODEL=gpt-4o-mini
```

## Ejecución

```powershell
python main.py
```

El script registra el inicio de la validación, ejecuta la cadena asíncrona y devuelve JSON validado. Ante un JSON incompleto o mal formado, LangChain reintenta la cadena una vez antes de propagar el error final.

## Ejemplo de salida

```json
{
  "tecnologias": ["FastAPI", "Redis", "PostgreSQL"],
  "nivel_de_criticidad": "alta",
  "resumen_tecnico": "La API de pagos presenta errores 503, latencia en Redis y agotamiento de conexiones en PostgreSQL."
}
```
