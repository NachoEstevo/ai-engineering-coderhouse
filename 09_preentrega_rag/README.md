# Pre-entrega 3 - RAG local

Sistema RAG local sobre documentación ficticia de PagoClaro. Los documentos se fragmentan en bloques de hasta 500 tokens, con 50 tokens de solapamiento, y se guardan en ChromaDB.

La respuesta se genera de forma asíncrona mediante una cadena LCEL y se valida con Pydantic. El prompt obliga a responder solamente con el contexto recuperado y a devolver `No lo sé` cuando no hay información suficiente.

## Instalación

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completá `OPENAI_API_KEY` en `.env`. Ese archivo no se sube al repositorio.

## Ejecución

Primero se indexan los cuatro documentos de `data/`:

```powershell
python ingest.py
```

La base se persiste en `vectorstore/`. Si ya contiene documentos, la ingesta no vuelve a indexarlos.

Luego se ejecutan las dos consultas de prueba:

```powershell
python rag.py
```

La primera consulta pregunta dónde se guardan las transacciones y debe basarse en `arquitectura.md`. La segunda pregunta por un sistema de mensajería inexistente en el dataset y debe responder `No lo sé`.
