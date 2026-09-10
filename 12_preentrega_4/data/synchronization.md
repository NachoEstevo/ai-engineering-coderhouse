# Primitivas de sincronización

Las primitivas de `asyncio` coordinan coroutines dentro de un event loop. No son thread-safe y no deben utilizarse para sincronizar threads del sistema operativo.

`asyncio.Lock` protege acceso exclusivo a un recurso compartido. La forma habitual de adquirirlo y liberarlo es `async with lock`, que garantiza la liberación al abandonar el bloque.

`asyncio.Semaphore` mantiene un contador interno. Cada adquisición disminuye el contador y cada liberación lo aumenta. Cuando el contador llega a cero, las tareas siguientes esperan hasta que otra libere un permiso. Un `Semaphore(10)` permite que como máximo diez coroutines entren simultáneamente en la sección protegida. Esto resulta útil para limitar conexiones, llamadas a una API o trabajos costosos.

`BoundedSemaphore` agrega una verificación: produce un error si se libera más veces de las que permite su valor inicial. Las primitivas no reciben un timeout directamente; cuando se necesita un límite temporal puede combinarse la operación con las herramientas de timeout de `asyncio`.

Fuente: https://docs.python.org/3.12/library/asyncio-sync.html
