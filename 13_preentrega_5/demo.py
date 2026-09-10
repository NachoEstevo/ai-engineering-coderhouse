import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from config import BASE_DIR, Settings


async def main() -> None:
    parser = argparse.ArgumentParser(description="Demostración reproducible del agente")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    session = f"demo-{uuid4().hex[:10]}"
    directory = BASE_DIR / "storage" / session
    directory.mkdir(parents=True)
    evidence_dir = args.output_dir.resolve() if args.output_dir else directory
    if evidence_dir != directory:
        evidence_dir.mkdir(parents=True, exist_ok=False)
    queries = [
        "¿Qué incidente tiene el servicio pagos y qué pasos recomienda su procedimiento para resolverlo?",
        "¿Quién es el responsable de ese incidente? Indicá también su ID.",
        "Consultá si hay un incidente en el servicio envíos.",
        "Ahora consultá el incidente del servicio pedidos y los pasos de su procedimiento.",
        "¿Quién era el responsable del incidente que mencioné antes?",
    ]
    turns = []
    for number, query in enumerate(queries, start=1):
        trace_path = evidence_dir / f"turn-{number}.json"
        thread_id = f"{session}-nuevo" if number == 5 else session
        command = [
            sys.executable,
            str(BASE_DIR / "main.py"),
            query,
            "--thread-id",
            thread_id,
            "--database",
            str(directory / "checkpoints.sqlite"),
            "--trace",
            str(trace_path),
        ]
        if number == 1:
            command.append("--simulate-failure")
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        stdout, stderr = await process.communicate()
        await asyncio.to_thread(
            (evidence_dir / f"turn-{number}.log").write_text,
            stderr.decode("utf-8", errors="replace")
            + "\n"
            + stdout.decode("utf-8", errors="replace"),
            encoding="utf-8",
        )
        if process.returncode:
            print(stderr.decode("utf-8", errors="replace"))
            raise RuntimeError(f"Falló el turno {number} de la demostración")
        print(stdout.decode("utf-8", errors="replace").strip())
        turns.append(json.loads(trace_path.read_text(encoding="utf-8")))

    actions = [event for event in turns[0]["eventos"] if event["tipo"] == "accion"]
    observations = [
        event for event in turns[0]["eventos"] if event["tipo"] == "observacion"
    ]
    checks = {
        "multipaso": len(actions) >= 2
        and {event["herramienta"] for event in actions}
        == {"buscar_incidente", "consultar_procedimiento"},
        "recuperacion_de_error": any(
            event["estado"] == "error" for event in observations
        )
        and "POOL-01" in turns[0]["respuesta"],
        "memoria_entre_procesos": "INC-204" in turns[1]["respuesta"]
        and "plataforma" in turns[1]["respuesta"].casefold()
        and not any(event["tipo"] == "accion" for event in turns[1]["eventos"]),
        "informacion_incompleta": any(
            "incompleto" in str(event.get("resultado", ""))
            for event in turns[2]["eventos"]
        )
        and "?" in turns[2]["respuesta"],
        "cambio_de_servicio": "INC-305" in turns[3]["respuesta"]
        and "QUEUE-02" in turns[3]["respuesta"]
        and len([event for event in turns[3]["eventos"] if event["tipo"] == "accion"])
        >= 2,
        "aislamiento_de_hilos": "?" in turns[4]["respuesta"]
        and not any(
            identifier in turns[4]["respuesta"] for identifier in ("INC-204", "INC-305")
        )
        and not any(event["tipo"] == "accion" for event in turns[4]["eventos"]),
    }
    result = {
        "origen": "Ejecución real de OpenAI con herramientas y datos ficticios locales",
        "modelo": Settings().openai_model,
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Acciones, observaciones y respuestas visibles; no contiene razonamiento interno privado.",
        "procesos_independientes": len(turns),
        "verificaciones": checks,
        "turnos": turns,
    }
    output = BASE_DIR / "trace_example.json"
    await asyncio.to_thread(
        output.write_text,
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    await asyncio.to_thread(
        (evidence_dir / "trace.json").write_text,
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not all(checks.values()):
        raise RuntimeError(f"Revisar la traza: {checks}")
    print(f"Verificaciones: {checks}")
    print(f"Traza guardada en {output}")


if __name__ == "__main__":
    asyncio.run(main())
