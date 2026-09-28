import argparse
import asyncio
import json
import logging
from pathlib import Path

from config import BASE_DIR
from graph import run_analysis
from state import AnalysisRequest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orquestador de estadística descriptiva"
    )
    parser.add_argument(
        "--input", type=Path, default=BASE_DIR / "examples" / "comparison.json"
    )
    parser.add_argument("--trace", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        request = AnalysisRequest.model_validate_json(
            args.input.read_text(encoding="utf-8")
        )
        result = asyncio.run(run_analysis(request))
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.trace:
            args.trace.parent.mkdir(parents=True, exist_ok=True)
            args.trace.write_text(output, encoding="utf-8")
        print(output)
        return 0 if result["completed"] else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "completed": False,
                    "error": type(exc).__name__,
                    "response": "Entrada o configuración inválida; revisá los archivos y variables requeridos.",
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
