from __future__ import annotations

from ..workflow_types import WorkflowContext


class DiscoverBusinessesNode:
    name = "discover_businesses"

    def __init__(self, provider):
        self.provider = provider

    async def run(self, ctx: WorkflowContext) -> WorkflowContext:
        query = str(ctx.request.get("query", "")).strip()
        if not query:
            ctx.errors.append("empty query")
            return ctx

        target = int(ctx.plan.get("target_count", 100))
        raw = []

        for anchor in ctx.anchors:
            token = None
            while True:
                batch, token = await self.provider.search(query, anchor, page_token=token)
                raw.extend(batch)
                if len(raw) >= target:
                    break
                if not token:
                    break
            if len(raw) >= target:
                break

        ctx.raw_candidates = raw
        return ctx
