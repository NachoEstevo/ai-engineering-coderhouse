import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parents[1]
TERMINAL = {"DONE", "FAILED", "REJECTED"}


async def run_one(client: httpx.AsyncClient, index: int, batch_id: str) -> dict:
    started = time.perf_counter()
    response = await client.post(
        "/tasks",
        json={
            "query": "Compará promedio y dispersión de ambos grupos usando fuentes. No infieras causalidad.",
            "groups": [
                {"name": f"A{index}", "unit": "ms", "values": [100, 110, 90, 100, 100]},
                {"name": f"B{index}", "unit": "ms", "values": [80, 120, 100, 90, 110]},
            ],
            "save_result": False,
            "batch_id": batch_id,
        },
    )
    response.raise_for_status()
    if response.status_code != 202:
        raise RuntimeError("POST /tasks debe responder 202")
    accepted_seconds = time.perf_counter() - started
    job_id = response.json()["job_id"]
    async with asyncio.timeout(480):
        while True:
            poll = await client.get(f"/tasks/{job_id}")
            poll.raise_for_status()
            job = poll.json()
            if job["status"] in TERMINAL:
                return {
                    "job_id": job_id,
                    "accepted_seconds": accepted_seconds,
                    "end_to_end_seconds": time.perf_counter() - started,
                    "job": job,
                }
            if job["status"] == "WAITING_APPROVAL":
                raise RuntimeError("La prueba sin escritura no debe requerir aprobación")
            await asyncio.sleep(1)


async def main() -> None:
    load_dotenv(BASE / ".env")
    token = os.environ["API_KEY"]
    batch_id = os.getenv("LOAD_BATCH_ID") or f"pre7-load-{uuid4().hex[:12]}"
    started = datetime.now(UTC).isoformat()
    async with httpx.AsyncClient(
        base_url=os.getenv("API_URL", "http://127.0.0.1:18070"),
        headers={"X-API-Key": token},
        timeout=20,
    ) as client:
        results = await asyncio.gather(*(run_one(client, i, batch_id) for i in range(1, 6)))
    evidence = {"batch_id": batch_id, "started_utc": started, "concurrency": 5, "results": results}
    destination = BASE / "evidencias" / f"{batch_id}.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Cohorte: {batch_id}")
    for result in results:
        print(f"{result['job_id']} {result['job']['status']} aceptación={result['accepted_seconds']:.3f}s total={result['end_to_end_seconds']:.2f}s")
    print(f"Evidencia: {destination}")
    if any(result["job"]["status"] != "DONE" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
