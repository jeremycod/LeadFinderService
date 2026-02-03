from __future__ import annotations

from ..workflow_types import WorkflowContext


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


class CanonicalizeAndDedupeNode:
    name = "canonicalize_and_dedupe"

    async def run(self, ctx: WorkflowContext) -> WorkflowContext:
        seen = set()
        unique = []
        for c in ctx.raw_candidates:
            key = (c.source, c.source_id) if c.source_id else ("fallback", _norm(c.name + "|" + (c.address_full or "")))
            if key in seen:
                continue
            seen.add(key)
            unique.append(c)
        ctx.raw_candidates = unique
        return ctx
