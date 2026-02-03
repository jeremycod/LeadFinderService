from __future__ import annotations

from typing import List

from .workflow_types import WorkflowContext


class WorkflowRunner:
    def __init__(self, nodes: List):
        self.nodes = nodes

    async def run(self, ctx: WorkflowContext) -> WorkflowContext:
        for node in self.nodes:
            ctx = await node.run(ctx)
        return ctx
