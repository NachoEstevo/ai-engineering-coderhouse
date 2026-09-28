import argparse
import asyncio
import json
import os
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

BASE = Path(__file__).resolve().parents[1]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    load_dotenv(BASE / ".env")
    cohort = json.loads(args.evidence.read_text(encoding="utf-8"))
    client = Client()
    project_name = os.getenv("LANGSMITH_PROJECT", "my-first-agent")
    project = await asyncio.to_thread(client.read_project, project_name=project_name)
    project_id = str(project.id)
    fields = ["ID", "STATUS", "START_TIME", "END_TIME", "ERROR", "RUN_TYPE",
              "METADATA", "TOTAL_TOKENS", "PROMPT_TOKENS", "COMPLETION_TOKENS", "TOTAL_COST"]
    rows = []
    nodes = defaultdict(lambda: {"llm_calls": 0, "tokens": 0, "seconds": 0.0})
    for item in cohort["results"]:
        trace_id = item["job"]["trace_id"]
        run = await client.runs.retrieve(trace_id, project_id=project_id, selects=fields)
        if run.end_time is None or run.error or run.total_cost is None:
            raise RuntimeError(f"Traza incompleta, fallida o sin costo: {trace_id}")
        async for child in client.runs.query(project_ids=[project_id], trace_id=trace_id, selects=fields):
            if (child.run_type or "").upper() != "LLM":
                continue
            node = (child.metadata or {}).get("langgraph_node", "unknown")
            nodes[node]["llm_calls"] += 1
            nodes[node]["tokens"] += child.total_tokens or 0
            if child.end_time:
                nodes[node]["seconds"] += (child.end_time - child.start_time).total_seconds()
        link = await client.runs.get_url(trace_id, project_id=project_id, trace_id=trace_id)
        rows.append({
            "job_id": item["job_id"],
            "trace_id": trace_id,
            "url": link.url,
            "status": run.status,
            "seconds": (run.end_time - run.start_time).total_seconds(),
            "input_tokens": run.prompt_tokens,
            "output_tokens": run.completion_tokens,
            "total_cost_usd": str(run.total_cost),
        })
    stats = await asyncio.to_thread(client.get_run_stats,
        project_names=[project_name], id=[row["trace_id"] for row in rows], is_root=True
    )
    report = {
        "batch_id": cohort["batch_id"],
        "source": "LangSmith API: actual run costs and aggregate statistics",
        "runs": rows,
        "platform_stats": {key: stats.get(key) for key in ("run_count", "latency_p50", "latency_p99", "error_rate")},
        "llm_by_node": dict(nodes),
    }
    output = args.evidence.with_name(args.evidence.stem + "-langsmith.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"Evidencia: {output}")


if __name__ == "__main__":
    asyncio.run(main())
