from __future__ import annotations

import re
from urllib.parse import urlparse
import httpx

from ..workflow_types import WorkflowContext


SOCIAL_DOMAINS = {
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "linkedin.com": "linkedin",
    "tiktok.com": "tiktok",
    "x.com": "x",
    "twitter.com": "x",
    "youtube.com": "youtube",
}


def _extract_links(html: str) -> list[str]:
    return re.findall(r'href=["\'](.*?)["\']', html, flags=re.IGNORECASE)


def _pick_socials(urls: list[str]) -> tuple[dict, list[str]]:
    socials = {}
    reasons = []
    for u in urls:
        try:
            host = (urlparse(u).netloc or "").lower()
        except Exception:
            continue
        for domain, key in SOCIAL_DOMAINS.items():
            if domain in host and key not in socials:
                socials[key] = u
                reasons.append("linked_from_website")
    return socials, reasons


class WebsiteSocialExtractorNode:
    name = "website_social_extractor"

    def __init__(self, timeout_s: float = 15.0):
        self.timeout_s = timeout_s

    async def run(self, ctx: WorkflowContext) -> WorkflowContext:
        if not ctx.plan.get("include_socials", True):
            return ctx

        cap = int(ctx.plan.get("website_fetch_cap", 400))
        used = 0
        enrichments = {}

        async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True) as client:
            for score, breakdown, c in getattr(ctx, "scored", []):
                if used >= cap:
                    break
                if not c.website_url:
                    continue
                try:
                    r = await client.get(c.website_url)
                    used += 1
                    if r.status_code >= 400:
                        continue
                    links = _extract_links(r.text)
                    socials, reasons = _pick_socials(links)
                    if socials:
                        enrichments[f"{c.source}:{c.source_id}"] = {
                            "socials": socials,
                            "confidence": 0.95,
                            "reasons": reasons,
                            "source": "website",
                        }
                except Exception:
                    continue

        ctx.website_enrichments = enrichments
        ctx.budget_usage = {"website_fetches_used": used, "website_fetches_cap": cap}
        return ctx
