from __future__ import annotations

from ...providers.base import Anchor
from ..workflow_types import WorkflowContext


class AnchorGeneratorNode:
    name = "anchor_generator"

    async def run(self, ctx: WorkflowContext) -> WorkflowContext:
        geo = ctx.request.get("geo_scope", {}) or {}
        target = int(ctx.plan.get("target_count", 100))

        if geo.get("center_lat") is not None and geo.get("center_lng") is not None and geo.get("radius_km") is not None:
            ctx.anchors = [
                Anchor(
                    center_lat=float(geo["center_lat"]),
                    center_lng=float(geo["center_lng"]),
                    radius_km=float(geo["radius_km"]),
                    quota=target,
                )
            ]
            return ctx

        ctx.anchors = [Anchor(center_lat=49.2827, center_lng=-123.1207, radius_km=30.0, quota=target)]
        return ctx
