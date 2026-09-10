# Coroutines, Tasks y TaskGroup

`asyncio` ejecuta coroutines mediante un event loop. Invocar una función definida con `async def` crea un objeto coroutine; su trabajo comienza cuando se usa `await`, cuando se crea una Task o cuando otra herramienta del event loop la agenda.

`asyncio.create_task()` agenda una coroutine para ejecutarse concurrentemente y devuelve una Task. Es importante conservar una referencia a esa Task si se necesita esperar su resultado, cancelarla o inspeccionar una excepción.

`asyncio.gather()` permite esperar varios awaitables y conserva el orden de los resultados. De forma predeterminada, una excepción se propaga hacia quien espera el `gather`, pero las demás tareas no reciben automáticamente la misma garantía de cancelación estructurada.

`asyncio.TaskGroup` es un context manager asíncrono para crear y esperar un grupo de tareas. Al salir del bloque espera a todas. Si una tarea falla con una excepción que no sea cancelación, cancela las restantes y agrupa los errores. Por esa razón ofrece garantías más fuertes que `gather` cuando varias subtareas forman una misma unidad de trabajo.

Fuente: https://docs.python.org/3.12/library/asyncio-task.html
