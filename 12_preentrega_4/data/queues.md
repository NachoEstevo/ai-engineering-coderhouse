# Colas asíncronas

`asyncio.Queue` implementa una cola FIFO para distribuir trabajo entre coroutines productoras y consumidoras. Está diseñada para código `async` y no es thread-safe.

Si `maxsize` es mayor que cero, `await queue.put(item)` espera cuando la cola está llena hasta que exista espacio. `await queue.get()` espera cuando está vacía hasta que aparezca un elemento. Este comportamiento genera backpressure y evita que un productor rápido acumule trabajo sin límite.

Cada elemento obtenido mediante `get()` debe finalizar con `queue.task_done()` cuando su procesamiento termina. `await queue.join()` espera hasta que todos los elementos agregados hayan recibido su correspondiente `task_done()`. Llamar `task_done()` más veces que los elementos retirados genera `ValueError`.

`PriorityQueue` entrega primero el elemento con prioridad numérica menor. `LifoQueue` utiliza el orden último en entrar, primero en salir. Los métodos de Queue no reciben un timeout propio; puede utilizarse `asyncio.wait_for()` alrededor de una operación de cola.

Fuente: https://docs.python.org/3.12/library/asyncio-queue.html
