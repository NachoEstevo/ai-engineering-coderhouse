# Arquitectura de PagoClaro

PagoClaro expone una API REST creada con FastAPI. La API valida cada solicitud y registra las transacciones confirmadas en PostgreSQL.

PostgreSQL es la fuente de verdad para pagos, usuarios y estados de las operaciones. Las transacciones no se almacenan en Redis.
