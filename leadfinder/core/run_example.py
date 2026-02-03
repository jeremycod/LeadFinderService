from __future__ import annotations

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

from leadfinder.core.workflow import WorkflowRunner
from leadfinder.core.workflow_types import WorkflowContext
from leadfinder.core.nodes.planner import RequestPlannerNode
from leadfinder.core.nodes.anchors import AnchorGeneratorNode
from leadfinder.core.nodes.discover import DiscoverBusinessesNode
from leadfinder.core.nodes.dedupe import CanonicalizeAndDedupeNode
from leadfinder.core.nodes.score import ScoreLeadsNode
from leadfinder.core.nodes.website_socials import WebsiteSocialExtractorNode
from leadfinder.core.nodes.assemble import AssembleResultsNode
from leadfinder.core.nodes.export import ExportGeneratorNode
from leadfinder.providers.google_places import GooglePlacesProvider, GooglePlacesConfig


async def main():
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env", override=False)
    load_dotenv(repo_root / "notebooks" / ".env", override=False)

    req = {
        "query": "coffee shop",
        "geo_scope": {"center_lat": 49.2827, "center_lng": -123.1207, "radius_km": 10},
        "target_count": 25,
        "plan": "pro",
        "options": {"include_socials": True, "website_fetch_cap": 50},
    }

    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        raise ValueError(
            "GOOGLE_PLACES_API_KEY is not set. "
            "Add it to the repo root .env or export it in the shell."
        )
    cfg = GooglePlacesConfig(api_key=api_key, region_code="CA")
    async with GooglePlacesProvider(cfg) as provider:
        runner = WorkflowRunner(
            nodes=[
                RequestPlannerNode(),
                AnchorGeneratorNode(),
                DiscoverBusinessesNode(provider),
                CanonicalizeAndDedupeNode(),
                ScoreLeadsNode(),
                WebsiteSocialExtractorNode(),
                AssembleResultsNode(),
                ExportGeneratorNode(export_dir=os.getenv("EXPORT_DIR", "./exports")),
            ]
        )

        ctx = WorkflowContext(search_id="example", request=req)
        ctx = await runner.run(ctx)
        print(f"Got {len(ctx.results)} results; wrote exports: {ctx.export_paths}")

if __name__ == "__main__":
    asyncio.run(main())
