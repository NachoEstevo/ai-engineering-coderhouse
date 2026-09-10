# Timeouts y cancelación

`asyncio.timeout()` es un context manager asíncrono que limita cuánto puede durar un bloque. Cuando vence, cancela la tarea actual internamente y transforma la cancelación en `TimeoutError`, que debe capturarse fuera del bloque.

`asyncio.wait_for(awaitable, timeout)` espera un awaitable individual. Si se supera el límite, cancela la tarea y produce `TimeoutError`. El tiempo total puede superar ligeramente el valor indicado porque `wait_for` espera a que la cancelación se complete.

La cancelación de una Task provoca `asyncio.CancelledError` en la próxima oportunidad. Las coroutines deben usar `try/finally` para liberar recursos y normalmente deben volver a propagar `CancelledError` después de limpiar. Ocultar esa excepción puede interferir con componentes de concurrencia estructurada como `TaskGroup` y `asyncio.timeout()`.

`asyncio.shield()` evita que la cancelación del código que espera se transfiera automáticamente a una tarea protegida. No elimina la cancelación externa y debe utilizarse solamente cuando la operación realmente necesita continuar.

Fuente: https://docs.python.org/3.12/library/asyncio-task.html
