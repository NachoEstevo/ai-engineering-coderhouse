import asyncio
import logging
from time import perf_counter

from langchain_core.tools import BaseTool, ToolException, tool

logger = logging.getLogger(__name__)

INCIDENTS = {
    "pagos": {
        "incidente_id": "INC-204",
        "servicio": "pagos",
        "sintoma": "Respuestas 503 al agotarse el pool de conexiones a PostgreSQL.",
        "procedimiento_id": "POOL-01",
        "responsable": "Equipo de plataforma",
    },
    "pedidos": {
        "incidente_id": "INC-305",
        "servicio": "pedidos",
        "sintoma": "Trabajos pendientes por un consumidor detenido.",
        "procedimiento_id": "QUEUE-02",
        "responsable": "Equipo de operaciones",
    },
}

PROCEDURES = {
    "POOL-01": {
        "procedimiento_id": "POOL-01",
        "pasos": [
            "Revisar conexiones activas y transacciones largas en PostgreSQL.",
            "Corregir las rutas que no liberan conexiones al finalizar.",
            "Limitar la concurrencia de la API a la capacidad del pool.",
        ],
        "verificacion": "Comprobar que bajan los errores 503 y la espera de conexiones.",
    },
    "QUEUE-02": {
        "procedimiento_id": "QUEUE-02",
        "pasos": [
            "Revisar el log del consumidor y corregir la causa de la detención.",
            "Reiniciar el consumidor siguiendo el procedimiento operativo.",
            "Verificar que cada trabajo confirma su finalización.",
        ],
        "verificacion": "Comprobar que la cantidad de trabajos pendientes disminuye.",
    },
}


def build_tools(simulate_failure: bool = False) -> list[BaseTool]:
    pending_failure = simulate_failure

    @tool
    async def buscar_incidente(servicio: str) -> dict[str, object]:
        """Consulta incidentes de la base de soporte simulada para un servicio exacto.

        Usala cuando el usuario pregunta qué falla en pagos o pedidos. Recibe el
        nombre del servicio y devuelve incidente_id, síntoma, responsable y
        procedimiento_id. No contiene los pasos de resolución: para obtenerlos
        consultá consultar_procedimiento con el ID devuelto. Si falta el servicio
        devuelve opciones para pedir aclaración. Un ToolException temporal admite
        un nuevo intento con el mismo argumento. No modifica ningún sistema real.
        """
        nonlocal pending_failure
        started_at = perf_counter()
        await asyncio.sleep(0.01)
        if pending_failure:
            pending_failure = False
            raise ToolException(
                "Consulta temporalmente no disponible; reintentá una vez."
            )
        incident = INCIDENTS.get(servicio.strip().casefold())
        logger.info("buscar_incidente: %.3fs", perf_counter() - started_at)
        if incident is None:
            return {
                "estado": "incompleto",
                "mensaje": "Pedí al usuario que indique uno de los servicios disponibles.",
                "servicios_disponibles": list(INCIDENTS),
            }
        return {"estado": "ok", **incident}

    @tool
    async def consultar_procedimiento(procedimiento_id: str) -> dict[str, object]:
        """Obtiene pasos y verificación de un procedimiento de soporte simulado.

        Usala para explicar cómo resolver un incidente después de conocer su
        procedimiento_id mediante buscar_incidente o el historial de esta sesión.
        Recibe ese ID exacto, por ejemplo POOL-01. Devuelve pasos y verificación,
        sin ejecutar comandos ni aplicar cambios. Si el ID no existe, devuelve
        información incompleta: verificá el incidente o pedí aclaración, no inventes
        instrucciones ni repitas indefinidamente el mismo ID inválido.
        """
        started_at = perf_counter()
        await asyncio.sleep(0.01)
        procedure = PROCEDURES.get(procedimiento_id.strip().upper())
        logger.info("consultar_procedimiento: %.3fs", perf_counter() - started_at)
        if procedure is None:
            return {
                "estado": "incompleto",
                "mensaje": "Procedimiento desconocido. Verificá el ID.",
            }
        return {"estado": "ok", **procedure}

    return [buscar_incidente, consultar_procedimiento]
