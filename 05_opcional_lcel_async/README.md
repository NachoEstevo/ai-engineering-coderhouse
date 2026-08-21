# Ejercicio opcional - Refactorización a LCEL Asíncrono

Ejemplo mínimo de una cadena LCEL asíncrona con OpenAI.

El flujo principal de [lcel_async.py](lcel_async.py) es:

```python
prompt | model | StrOutputParser()
```

El prompt recibe un diccionario con la clave `pregunta` y la ejecución usa `await chain.ainvoke(...)`. `StrOutputParser` convierte la respuesta del modelo en texto plano.

## Instalación

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Editá `.env` y agregá una API key de OpenAI:

```dotenv
OPENAI_API_KEY=tu_clave_real
OPENAI_MODEL=gpt-4o-mini
```

## Ejecución

```powershell
python lcel_async.py
```
