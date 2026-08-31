# Seguridad de PagoClaro

Las solicitudes a la API requieren un token Bearer. FastAPI verifica el token antes de ejecutar una operación de pago.

Los secretos se cargan desde variables de entorno y no deben guardarse en el repositorio.
