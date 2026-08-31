# Caché de PagoClaro

PagoClaro utiliza Redis para guardar temporalmente resultados de consultas frecuentes, como el historial reciente de pagos de un usuario.

Las claves de caché tienen un TTL de cinco minutos. Redis reduce la latencia de lectura, pero no reemplaza a PostgreSQL como almacenamiento persistente.
