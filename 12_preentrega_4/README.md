# Pre-entrega 4 - RAG escalable con Pinecone

Sistema de recuperación híbrida sobre documentación de Python `asyncio`. Combina búsqueda semántica en Pinecone Serverless con búsqueda léxica BM25 y evalúa los resultados mediante Precision@5 y Recall@5.

## Componentes

- `pinecone_setup.py`: crea el índice Serverless en AWS `us-east-1` si no existe y valida que tenga 1536 dimensiones.
- `documents.py`: carga Markdown, continúa ante archivos ilegibles y divide el contenido en chunks de 600 tokens con 80 de overlap.
- `ingest.py`: genera embeddings con `text-embedding-3-small` e inserta los chunks en el namespace `asyncio-docs`.
- `retriever.py`: combina `BM25Retriever` y Pinecone mediante `EnsembleRetriever`, con pesos 0.4 y 0.6.
- `evaluate.py`: ejecuta cinco preguntas del Golden Set y calcula Precision@5 y Recall@5.
- `tests/`: verifica localmente configuración, chunking, errores de archivos, reintentos, batching, recuperación y métricas.

## Cuentas y variables necesarias

Creá una cuenta en [Pinecone](https://app.pinecone.io/) y obtené una API key. También necesitás una [API key de OpenAI](https://platform.openai.com/api-keys) con saldo para generar embeddings.

No compartas las claves ni las subas a Git. Copiá el ejemplo localmente:

```powershell
Copy-Item .env.example .env
```

Luego completá:

```dotenv
PINECONE_API_KEY=tu_clave_real
OPENAI_API_KEY=tu_clave_real
INDEX_NAME=asyncio-rag-serverless
```

## Instalación

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Ingesta

```powershell
python ingest.py
```

El script crea o reutiliza el índice, valida la dimensión, procesa los archivos de `data/`, genera embeddings y realiza el upsert por lotes. Cada vector conserva `text`, `source`, `page`, `category`, `tags` y `chunk_id` en sus metadatos.

## Evaluación

```powershell
python evaluate.py
```

Para cada pregunta se imprimen las fuentes recuperadas, Precision@5 y Recall@5. Al final se muestra el promedio de las cinco consultas.

Con una única fuente relevante por pregunta, Recall@5 vale 1 cuando esa fuente aparece entre los cinco resultados. Precision@5 vale 0.2 cuando uno de los cinco resultados pertenece a la fuente esperada.

## Resultado de la evaluación

Evaluación ejecutada el 10 de septiembre de 2026 sobre el índice `asyncio-rag-serverless` y el namespace `asyncio-docs`:

```text
Precision@5 promedio: 0.20
Recall@5 promedio: 1.00
```

La fuente esperada apareció en la primera posición para las cinco preguntas. Como cada caso define una única fuente relevante, una recuperación perfecta dentro del top 5 produce Precision@5 de 0.20 y Recall@5 de 1.00.

## Pruebas locales

```powershell
python -m pytest -q
```

Las pruebas no consumen OpenAI ni Pinecone. La ejecución real de `ingest.py` y `evaluate.py` sí requiere ambas API keys.

## Fuentes del dataset

Los documentos son resúmenes propios basados en la documentación oficial de Python 3.12:

- https://docs.python.org/3.12/library/asyncio-task.html
- https://docs.python.org/3.12/library/asyncio-sync.html
- https://docs.python.org/3.12/library/asyncio-queue.html
- https://docs.python.org/3.12/library/asyncio-stream.html
- https://docs.python.org/3.12/library/asyncio-subprocess.html
- https://docs.python.org/3.12/library/asyncio-runner.html
