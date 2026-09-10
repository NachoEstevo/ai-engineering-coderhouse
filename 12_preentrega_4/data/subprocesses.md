# Subprocesos asíncronos

`asyncio.create_subprocess_exec()` inicia un programa con sus argumentos separados. Esta opción evita que un shell interprete los argumentos y suele ser la alternativa adecuada cuando el comando y sus parámetros ya están estructurados.

`asyncio.create_subprocess_shell()` ejecuta una cadena mediante el shell del sistema. Si la cadena incorpora entrada externa, la aplicación debe escapar correctamente los caracteres especiales para evitar shell injection.

Ambas funciones devuelven un objeto `Process`. Cuando stdout o stderr se configuran con `asyncio.subprocess.PIPE`, `await process.communicate()` lee ambas salidas y espera la finalización. Es preferible a esperar primero con `Process.wait()` cuando el proceso escribe mucho, porque los buffers llenos podrían provocar un deadlock.

Los métodos `wait()` y `communicate()` no incluyen un timeout propio. Pueden envolverse con `asyncio.wait_for()` o `asyncio.timeout()`. El atributo `returncode` permite conocer el estado de salida una vez finalizado el proceso.

Fuente: https://docs.python.org/3.12/library/asyncio-subprocess.html
