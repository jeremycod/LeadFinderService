from __future__ import annotations

from ..workflow_types import WorkflowContext


class ScoreLeadsNode:
    name = "score_leads"

    async def run(self, ctx: WorkflowContext) -> WorkflowContext:
        scored = []
        for c in ctx.raw_candidates:
            score = 0.0
            breakdown = {}
            if c.website_url:
                score += 3.0
                breakdown["website"] = 3.0
            if c.phone:
                score += 2.0
                breakdown["phone"] = 2.0
            if c.address_full:
                score += 1.0
                breakdown["address"] = 1.0
            if c.categories:
                score += 1.0
                breakdown["types"] = 1.0
            scored.append((score, breakdown, c))

        scored.sort(key=lambda t: t[0], reverse=True)
        target = int(ctx.plan.get("target_count", 100))
        ctx.scored = scored[:target]
        return ctx
