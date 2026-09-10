# Streams de red

La API de streams ofrece abstracciones de alto nivel para conexiones de red asíncronas. `asyncio.open_connection()` abre una conexión y devuelve un `StreamReader` junto con un `StreamWriter`. `asyncio.start_server()` inicia un servidor y ejecuta un callback por cada cliente conectado.

`StreamReader` permite leer bytes sin bloquear el event loop mediante operaciones como `read()`, `readline()` y `readexactly()`. `StreamWriter.write()` coloca datos en el buffer de salida. Después de escribir, `await writer.drain()` permite aplicar control de flujo cuando el buffer alcanza su límite superior.

Para cerrar correctamente una conexión se llama `writer.close()` y luego `await writer.wait_closed()`. Los límites configurados en el reader ayudan a controlar el tamaño del buffer, pero no sustituyen las validaciones propias del protocolo de aplicación.

Los streams son apropiados para clientes y servidores TCP sencillos. Las aplicaciones deben definir framing, timeouts y manejo de conexiones incompletas según el protocolo que implementan.

Fuente: https://docs.python.org/3.12/library/asyncio-stream.html
