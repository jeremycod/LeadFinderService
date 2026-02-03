from __future__ import annotations

import json
from pathlib import Path
from ..workflow_types import WorkflowContext


class ExportGeneratorNode:
    name = "export_generator"

    def __init__(self, export_dir: str = "./exports"):
        self.export_dir = Path(export_dir)

    async def run(self, ctx: WorkflowContext) -> WorkflowContext:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        out = self.export_dir / f"{ctx.search_id}.json"
        out.write_text(json.dumps({"results": getattr(ctx, "results", [])}, indent=2), encoding="utf-8")
        ctx.export_paths = {"json": str(out)}
        return ctx
