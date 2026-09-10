# Pre-entrega 4 - RAG escalable con Pinecone

Sistema de recuperación híbrida sobre documentación de Python `asyncio`. Combina búsqueda semántica en Pinecone Serverless con búsqueda léxica BM25 y evalúa los resultados mediante Precision@5 y Recall@5.

## Componentes

- `pinecone_setup.py`: crea el índice Serverless en AWS `us-east-1` si no existe y valida que tenga 1536 dimensiones.
- `documents.py`: carga Markdown y divide el contenido en chunks de 600 tokens con 80 de overlap. La ingesta utiliza lectura estricta para no eliminar datos si falta un archivo por un error de lectura.
- `ingest.py`: genera embeddings con `text-embedding-3-small` e inserta los chunks en el namespace `asyncio-docs`.
- `retriever.py`: combina `BM25Retriever` y Pinecone mediante `EnsembleRetriever`, con pesos 0.4 y 0.6.
- `evaluate.py`: ejecuta cinco preguntas del Golden Set y calcula Precision@5, Recall@5 y MRR@5.
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

El namespace es exclusivo de este dataset. Cada ID usa fuente, posición dentro del documento y contenido; agregar otro documento no cambia los IDs existentes. Después de confirmar todos los lotes, el script elimina por ID los vectores anteriores que ya no están en el corpus. Esto cubre documentos modificados, renombrados y retirados. No usa `delete_all` ni toca otros namespaces. Los documentos locales permiten reconstruir los vectores.

Ejecutá una sola ingesta a la vez sobre este namespace. Si un archivo no puede leerse, está vacío o falla un upsert, el proceso se detiene antes de borrar vectores anteriores. Un directorio sin documentos tampoco permite la limpieza.

Los reintentos externos son como máximo tres, con esperas de 1 y 2 segundos. Para Pinecone se reintentan problemas de transporte, HTTP 408, 429 y 5xx; los 400, 401 y 403 fallan inmediatamente. Los embeddings desactivan los reintentos internos del SDK para no multiplicar los intentos de la aplicación.

## Evaluación

```powershell
python evaluate.py
```

Para cada pregunta se imprimen las fuentes recuperadas, Precision@5, Recall@5 y el rango recíproco. Al final se muestran los promedios. El Top 5 y las métricas se calculan por fuentes únicas, conservando el chunk mejor ubicado de cada fuente.

El Golden Set incluye dos fuentes relevantes justificadas por pregunta, porque cada consulta combina dos necesidades relacionadas. Precision@5 es la cantidad de fuentes relevantes recuperadas dividida por 5; Recall@5 divide por las dos fuentes esperadas. MRR@5 promedia el inverso de la posición de la primera fuente relevante (1 en primera posición, 0.5 en segunda, 0 si no aparece).

## Resultado de la evaluación

Evaluación ejecutada el 10 de septiembre de 2026 sobre el índice `asyncio-rag-serverless` y el namespace `asyncio-docs`:

```text
Precision@5 promedio: 0.40
Recall@5 promedio: 1.00
MRR@5 promedio: 0.90
```

Las dos fuentes relevantes aparecieron en el Top 5 de cada pregunta. La primera fuente relevante quedó primera en cuatro preguntas y segunda en una. Con estas etiquetas, el máximo de Precision@5 es 0.40; MRR permite distinguir el orden de los resultados aunque ese valor se mantenga. Son cinco consultas sobre siete documentos: una comprobación didáctica, no evidencia de calidad para un corpus amplio. Estos valores corresponden al Golden Set revisado y no son comparables directamente con los del benchmark anterior.

## Pruebas locales

```powershell
python -m pytest -q
```

Las pruebas no consumen OpenAI ni Pinecone. La ejecución real de `ingest.py` y `evaluate.py` sí requiere ambas API keys.

Las regresiones cubren IDs estables al agregar documentos, limpieza limitada al namespace, ausencia de borrados cuando falla la carga, lectura estricta, fuentes duplicadas y clasificación de errores reintentables.

## Mantenimiento de dependencias

`langchain-community` emite una advertencia de retirada. Se mantiene para el `BM25Retriever` solicitado por la consigna; la advertencia ya no se oculta en pytest. Revisar su migración a una integración independiente antes de adoptar nuevas versiones mayores de LangChain.

## Fuentes del dataset

Los documentos son resúmenes propios basados en la documentación oficial de Python 3.12:

- https://docs.python.org/3.12/library/asyncio-task.html
- https://docs.python.org/3.12/library/asyncio-sync.html
- https://docs.python.org/3.12/library/asyncio-queue.html
- https://docs.python.org/3.12/library/asyncio-stream.html
- https://docs.python.org/3.12/library/asyncio-subprocess.html
- https://docs.python.org/3.12/library/asyncio-runner.html
