from __future__ import annotations

from ..workflow_types import WorkflowContext


class AssembleResultsNode:
    name = "assemble_results"

    async def run(self, ctx: WorkflowContext) -> WorkflowContext:
        enrich = getattr(ctx, "website_enrichments", {}) or {}
        items = []

        for score, breakdown, c in getattr(ctx, "scored", []):
            key = f"{c.source}:{c.source_id}"
            e = enrich.get(key, {}) or {}
            items.append(
                {
                    "business_key": key,
                    "name": c.name,
                    "address_full": c.address_full,
                    "phone": c.phone,
                    "website_url": c.website_url,
                    "categories": c.categories,
                    "score": score,
                    "score_breakdown": breakdown,
                    "socials": e.get("socials") or {},
                    "social_confidence": float(e.get("confidence") or 0.0),
                    "social_reasons": e.get("reasons") or [],
                    "needs_review": False,
                }
            )

        ctx.results = items
        return ctx
