from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal

PlanTier = Literal["basic", "pro", "enterprise"]

class GeoScope(BaseModel):
    country: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2, e.g., CA")
    regions: Optional[List[str]] = None
    cities: Optional[List[str]] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_km: Optional[float] = None

class SearchOptions(BaseModel):
    include_socials: bool = True
    prefer_website_socials: bool = True
    max_paid_enrichments: int = 0
    website_fetch_cap: int = 400

class CreateSearchRequest(BaseModel):
    query: str
    geo_scope: GeoScope
    target_count: int = Field(ge=1, le=5000)
    plan: PlanTier = "basic"
    options: SearchOptions = SearchOptions()

class CreateSearchResponse(BaseModel):
    search_id: str
    status: str

class SearchStatusResponse(BaseModel):
    search_id: str
    status: str
    progress: Dict[str, int] = {}
    budget_usage: Dict[str, int] = {}
    summary: Dict[str, float] = {}
