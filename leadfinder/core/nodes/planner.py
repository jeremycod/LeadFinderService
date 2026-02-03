from __future__ import annotations

from dataclasses import dataclass
from ..workflow_types import WorkflowContext


@dataclass(frozen=True)
class RequestPlannerConfig:
    default_website_fetch_cap: int = 400


class RequestPlannerNode:
    name = "request_planner"

    def __init__(self, config: RequestPlannerConfig | None = None):
        self.config = config or RequestPlannerConfig()

    async def run(self, ctx: WorkflowContext) -> WorkflowContext:
        req = ctx.request
        options = req.get("options", {}) or {}
        website_cap = int(options.get("website_fetch_cap") or self.config.default_website_fetch_cap)

        ctx.plan = {
            "target_count": int(req.get("target_count", 100)),
            "website_fetch_cap": website_cap,
            "include_socials": bool(options.get("include_socials", True)),
        }
        return ctx
