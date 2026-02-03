# Go# leadfinder/providers/google_places.py
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .base import Anchor, RawCandidate


def _safe_get(d: Dict[str, Any], path: List[str], default=None):
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _extract_address_components(addr: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Lightweight parsing for city/region/country from Google's formattedAddress.
    Not perfect, but ok for v1. You can upgrade later using addressComponents.
    Expected-ish format: "street, City, Region Postal, Country"
    """
    if not addr:
        return None, None, None
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    if len(parts) >= 1:
        country = parts[-1]
    else:
        country = None
    region = parts[-2] if len(parts) >= 2 else None
    city = parts[-3] if len(parts) >= 3 else None
    return city, region, country


@dataclass(frozen=True)
class GooglePlacesConfig:
    api_key: str
    # e.g. "en" or "en-CA"
    language_code: str = "en"
    # e.g. "CA" for Canada bias in results
    region_code: Optional[str] = "CA"

    # Hard caps / safety
    timeout_s: float = 20.0
    max_retries: int = 4
    base_backoff_s: float = 0.6

    # Field masks
    # Keep these lean to reduce billing/latency.
    search_field_mask: str = (
        "places.id,"
        "places.displayName.text,"
        "places.formattedAddress,"
        "places.location,"
        "places.types"
    )
    details_field_mask: str = (
        "id,"
        "displayName.text,"
        "formattedAddress,"
        "location,"
        "types,"
        "nationalPhoneNumber,"
        "websiteUri"
    )


class GooglePlacesProvider:
    """
    Google Places API v1 provider:
      - POST https://places.googleapis.com/v1/places:searchText
      - GET  https://places.googleapis.com/v1/places/{place_id}

    Auth header:
      - X-Goog-Api-Key: <key>

    Field masks:
      - X-Goog-FieldMask: <comma-separated fields>
    """

    provider_name = "google_places"
    _BASE_URL = "https://places.googleapis.com/v1"

    def __init__(self, cfg: GooglePlacesConfig, client: Optional[httpx.AsyncClient] = None):
        if not cfg.api_key:
            raise ValueError("GooglePlacesConfig.api_key is required")
        self.cfg = cfg
        self._client = client

    async def __aenter__(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.cfg.timeout_s)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._client is not None:
            await self._client.aclose()
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("GooglePlacesProvider must be used with 'async with' or provide a client.")
        return self._client

    async def _request_with_retries(
        self,
        method: str,
        url: str,
        *,
        headers: Dict[str, str],
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retries on transient failures (429/5xx/timeouts) with exponential backoff + jitter.
        """
        last_err: Optional[Exception] = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                resp = await self.client.request(method, url, headers=headers, json=json, params=params)
                if resp.status_code in (429, 500, 502, 503, 504):
                    # transient / quota / backend issues
                    raise httpx.HTTPStatusError(
                        f"transient status {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    raise ValueError("Expected JSON object response")
                return data
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError, ValueError) as e:
                last_err = e
                if attempt >= self.cfg.max_retries:
                    break
                # Exponential backoff with jitter
                backoff = self.cfg.base_backoff_s * (2 ** attempt)
                jitter = random.random() * 0.25
                await asyncio.sleep(backoff + jitter)
        raise RuntimeError(f"Google Places request failed after retries: {last_err}") from last_err

    def _headers(self, field_mask: str) -> Dict[str, str]:
        h = {
            "X-Goog-Api-Key": self.cfg.api_key,
            "X-Goog-FieldMask": field_mask,
            "Content-Type": "application/json",
        }
        return h

    async def search(
        self,
        query: str,
        anchor: Optional[Anchor],
        *,
        page_token: Optional[str] = None,
    ) -> Tuple[List[RawCandidate], Optional[str]]:
        """
        Executes one search page for the given query + anchor.
        Returns (candidates, next_page_token).

        Notes:
        - We use 'locationBias' as a circle around the anchor.
        - We do a details fetch per place to get phone + website. (Optional but usually needed for leads.)
        - You can later optimize by skipping details in Basic plan or only fetching details for top N.
        """
        # --- 1) SearchText ---
        search_url = f"{self._BASE_URL}/places:searchText"

        body: Dict[str, Any] = {
            "textQuery": query,
            "languageCode": self.cfg.language_code,
        }
        if anchor is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": anchor.center_lat, "longitude": anchor.center_lng},
                    "radius": float(anchor.radius_km) * 1000.0,
                }
            }
        if self.cfg.region_code:
            body["regionCode"] = self.cfg.region_code

        # Places API uses "pageToken" for pagination
        if page_token:
            body["pageToken"] = page_token

        search_data = await self._request_with_retries(
            "POST",
            search_url,
            headers=self._headers(self.cfg.search_field_mask),
            json=body,
        )

        places = search_data.get("places", []) or []
        next_token = search_data.get("nextPageToken")

        # --- 2) Fetch details (phone + website) ---
        # If you want to save costs, you can make this conditional by plan,
        # or fetch details only for candidates you keep after scoring.
        candidates: List[RawCandidate] = []
        for p in places:
            place_id = _safe_get(p, ["id"])
            if not place_id:
                continue

            details = await self._get_place_details(place_id)

            name = _safe_get(details, ["displayName", "text"], "") or ""
            formatted_address = _safe_get(details, ["formattedAddress"], "") or ""
            loc = _safe_get(details, ["location"], {}) or {}
            lat = loc.get("latitude")
            lng = loc.get("longitude")
            types = details.get("types", []) or []

            phone = details.get("nationalPhoneNumber")
            website = details.get("websiteUri")

            city, region, country = _extract_address_components(formatted_address)

            candidates.append(
                RawCandidate(
                    source=self.provider_name,
                    source_id=str(place_id),
                    payload={
                        "search_place": p,
                        "details": details,
                    },
                    name=name,
                    address_full=formatted_address,
                    city=city,
                    region=region,
                    country=country,
                    lat=lat,
                    lng=lng,
                    phone=phone,
                    website_url=website,
                    categories=[str(t) for t in types],
                )
            )

        return candidates, (str(next_token) if next_token else None)

    async def _get_place_details(self, place_id: str) -> Dict[str, Any]:
        url = f"{self._BASE_URL}/places/{place_id}"
        return await self._request_with_retries(
            "GET",
            url,
            headers=self._headers(self.cfg.details_field_mask),
        )
