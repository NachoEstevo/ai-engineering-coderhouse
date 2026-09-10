# Ejecución del event loop

`asyncio.run(coro)` es el punto de entrada habitual para un programa asíncrono. Crea un event loop, ejecuta la coroutine principal, finaliza generadores asíncronos y cierra el executor antes de cerrar el loop. No puede llamarse cuando otro event loop ya está ejecutándose en el mismo thread.

`asyncio.Runner` es un context manager que permite ejecutar varias funciones asíncronas dentro del mismo event loop y contexto. Es útil cuando un programa necesita realizar más de una llamada asíncrona de nivel superior sin crear y destruir un loop para cada una.

Las librerías normalmente deben exponer coroutines y dejar que la aplicación controle el event loop. Colocar `asyncio.run()` dentro de una función reutilizable dificulta su uso desde notebooks, servidores asíncronos y frameworks que ya administran su propio loop.

El event loop agenda Tasks, callbacks y operaciones de entrada y salida. Las funciones síncronas lentas bloquean ese loop; para trabajo bloqueante apropiado puede utilizarse `asyncio.to_thread()`.

Fuente: https://docs.python.org/3.12/library/asyncio-runner.html
