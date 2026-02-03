# Provider interfaces and dataclasses.
# leadfinder/providers/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple


@dataclass(frozen=True)
class Anchor:
    """A geographic anchor used to query discovery providers."""
    center_lat: float
    center_lng: float
    radius_km: float
    quota: int


@dataclass(frozen=True)
class RawCandidate:
    """
    A normalized, provider-agnostic candidate returned by discovery providers.
    `payload` stores the raw-ish provider response fields for debugging/provenance.
    """
    source: str
    source_id: str
    payload: Dict[str, Any]

    name: str
    address_full: str
    city: Optional[str]
    region: Optional[str]
    country: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    phone: Optional[str]
    website_url: Optional[str]
    categories: List[str]


class DiscoveryProvider(Protocol):
    provider_name: str

    async def search(
        self,
        query: str,
        anchor: Optional[Anchor],
        *,
        page_token: Optional[str] = None,
    ) -> Tuple[List[RawCandidate], Optional[str]]:
        """
        Returns (candidates, next_page_token). next_page_token is None when done.
        """
        ...
