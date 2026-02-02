# LeadFinder Service — Full Spec Pack (Python)

> **Purpose:** A self-serve lead generation service that discovers businesses by **query + geography**, enriches them (website-first; SERP fallback), scores confidence, and exports results.
>
> **Primary constraints:** predictable cost, ToS-friendly enrichment, strong caching, asynchronous workflows, and explicit provenance/confidence for every enriched field.

---

## 0) Glossary

- **Lead:** A business location record usable for outreach (name, address, phone, website, optional socials).
- **Business (canonical entity):** A deduped record representing a unique business location.
- **Search job:** A user request that produces a lead list and optional enrichments.
- **Anchor:** A geographic “tile/center+radius” used to break large regions into manageable discovery queries.
- **Enrichment:** Any additional data gathered beyond discovery results (website social links, SERP-found socials, etc.).
- **Confidence:** 0..1 score for any enriched artifact, with **reasons** and **source**.
- **Plan:** Pricing/feature tier (basic/pro/enterprise), used to gate paid calls (e.g., SERP).

---

## 1) Product scope

### 1.1 MVP user story
A user searches:
- Query: `"pharmacies"`
- Geo: `"Canada"`
- Target: `300`

System returns 300 unique business leads with:
- name, address, phone (if available), website (if available)
- **website-derived socials** when present (cheap + accurate)
- lead score, enrichment confidence
- export to CSV/JSON
- optional “Pro” action: enrich missing socials via SERP **within a budget cap**

### 1.2 Non-goals (v1)
- Deep scraping of restricted social platforms (LinkedIn/Instagram content extraction beyond metadata)
- Harvesting personal emails/phones that are not clearly business contact points
- Guaranteeing social profiles for every business

---

## 2) Architecture overview

### 2.1 Services
- **FastAPI API**: request validation, auth, job orchestration, result pagination, exports
- **Worker(s)**: execute the workflow DAG and enrichment batches
- **Postgres**: persistence for entities, searches, enrichments, exports
- **Redis**: caching + rate-limit state + job coordination (optional but strongly recommended)
- **Object storage**: export artifacts (local filesystem for dev; S3-compatible for prod)

### 2.2 Provider strategy (pluggable)
V1 supports a discovery provider interface with at least one implementation:
- `GooglePlacesProvider` (paid, best coverage) OR
- `OSMOverpassProvider` (free, variable coverage)

SERP fallback provider (Pro tier):
- `SerperProvider` (paid)

> **Cost guardrail:** SERP calls are *never* required to complete a search. They are optional enrichments with caps.

---

## 3) Workflow graph (agent nodes)

This system uses a **DAG** of nodes. Some nodes are deterministic processors; some may be “LLM/agent” nodes (optional). In v1, you can implement all nodes deterministically and add LLM reasoning later for better matching and summaries.

### 3.1 Node list (in execution order)

#### Node A — RequestPlanner
**Inputs:** SearchRequest  
**Outputs:** `ExecutionPlan` (anchors, quotas, provider selection, budget rules, scoring knobs)

Responsibilities:
- Normalize query + geo scope
- If geo is broad (country/province), generate anchor plan
- Select plan defaults based on `plan` tier
- Derive `cost_budget` and `enrichment_policy`

---

#### Node B — AnchorGenerator
**Inputs:** `ExecutionPlan.geo_scope`  
**Outputs:** `List[Anchor]` with `quota_per_anchor`

Anchor types:
- `center+radius` (preferred)
- bounding box (optional)

For “Canada” requests, anchors should be a **nationwide sampling plan**:
- province-level representation + major metro areas
- optional “population-weighted” distribution
- deterministic (no LLM)

---

#### Node C — DiscoverBusinesses
**Inputs:** anchors, query, discovery provider  
**Outputs:** `List[RawCandidate]`

Responsibilities:
- Query provider for each anchor with pagination
- Persist raw provider payload for debugging
- Stop early when `target_count + buffer` candidates collected

---

#### Node D — CanonicalizeAndDedupe
**Inputs:** raw candidates  
**Outputs:** `List[Business]` (unique), mapping `candidate -> business_id`

Responsibilities:
- Upsert canonical `Business` records
- Dedupe using:
  - provider canonical ID when present (`place_id`, `osm_id`)
  - fallback: normalized `(name, address)` + geo-distance tolerance

---

#### Node E — ScoreLeads
**Inputs:** canonical businesses  
**Outputs:** `SearchResult` rows with `score` + `score_breakdown`

Scoring (example):
- +3 website present
- +2 phone present
- +2 category matches query strongly
- +1 complete address fields
- +1 has opening hours (if available from discovery)

---

#### Node F — WebsiteSocialExtractor
**Inputs:** businesses with `website_url`  
**Outputs:** `EnrichmentRecord(type="socials", source="website")`

Responsibilities:
- Fetch homepage HTML (rate-limited per domain)
- Parse links; extract `instagram/facebook/linkedin/tiktok/x/youtube`
- Optionally follow one internal link: `/contact`, `/about` (bounded)
- Store social URLs and high confidence

---

#### Node G — SerpSocialEnricher (Pro only)
**Inputs:** businesses missing socials, remaining paid budget  
**Outputs:** `EnrichmentRecord(type="socials_candidates", source="serp")`

Responsibilities:
- 1 SERP query per business *max*
- Prefer one query covering all platforms:
  - `"{name}" "{city}" "{region}" (instagram OR linkedin OR facebook) official`
- Extract candidate URLs per platform with ranking signals from snippets

---

#### Node H — SocialVerifier
**Inputs:** website socials + SERP candidates  
**Outputs:** final chosen socials + confidence + reasons

Verification signals (ranked):
1. Social link appears on business website → confidence 0.90–0.98
2. Social profile metadata links back to the business website domain → 0.80–0.90
3. Page title/snippet matches name + location → 0.60–0.75
4. URL exists only → 0.30–0.50 (flag)

Outputs:
- final `socials` object per business
- `social_confidence` and `reasons`
- `needs_review` boolean for low confidence

---

#### Node I — AssembleResults
**Inputs:** businesses + enrichments + scores  
**Outputs:** persisted `SearchResult` + search summary

---

#### Node J — ExportGenerator
**Inputs:** search_id + format + columns  
**Outputs:** export artifact (CSV/JSON) + `Export` record

---

### 3.2 Human-in-the-loop (optional UI/endpoint)
For low-confidence socials:
- return candidate list + reasons
- allow user to accept/reject per business

This avoids over-automating questionable matches.

---

## 4) API specification (FastAPI)

### 4.1 Authentication
Use API keys for v1.

**Header:** `X-API-Key: <key>`

---

### 4.2 Endpoints

#### Create search
`POST /v1/searches`

Request body:
```json
{
  "query": "pharmacies",
  "geo_scope": { "country": "CA" },
  "target_count": 300,
  "plan": "basic",
  "options": {
    "include_socials": true,
    "max_paid_enrichments": 0,
    "prefer_website_socials": true
  }
}
```

Response:
```json
{ "search_id": "uuid", "status": "queued" }
```

---

#### Get search status
`GET /v1/searches/{search_id}`

Response:
```json
{
  "search_id": "uuid",
  "status": "running",
  "progress": {
    "anchors_total": 30,
    "anchors_done": 12,
    "candidates_collected": 620,
    "businesses_deduped": 255,
    "website_enriched": 140,
    "serp_enriched": 0
  },
  "budget_usage": {
    "paid_enrichments_used": 0,
    "paid_enrichments_cap": 0,
    "website_fetches_used": 180,
    "website_fetches_cap": 400
  },
  "summary": {
    "lead_count_ready": 220,
    "avg_score": 6.4
  }
}
```

---

#### List leads (paged)
`GET /v1/searches/{search_id}/leads?limit=50&offset=0&min_confidence=0.6&sort=score_desc`

Response:
```json
{
  "search_id": "uuid",
  "total": 300,
  "items": [
    {
      "business_id": "uuid",
      "name": "Example Pharmacy",
      "address_full": "123 Main St, Vancouver, BC, Canada",
      "phone_e164": "+16045551234",
      "website_url": "https://examplepharmacy.ca",
      "categories": ["pharmacy"],
      "score": 8.0,
      "score_breakdown": {"website": 3, "phone": 2, "category_match": 2, "address": 1},
      "socials": {
        "instagram": "https://instagram.com/examplepharmacy",
        "linkedin": null,
        "facebook": "https://facebook.com/examplepharmacy"
      },
      "social_confidence": 0.95,
      "social_reasons": ["linked_from_website_footer"],
      "needs_review": false
    }
  ]
}
```

---

#### Trigger paid enrichment (Pro only)
`POST /v1/searches/{search_id}/enrich`

Request:
```json
{
  "type": "serp_socials",
  "max_items": 50,
  "only_missing": true
}
```

Response:
```json
{ "search_id": "uuid", "status": "running" }
```

---

#### Get a business
`GET /v1/businesses/{business_id}`

#### Get enrichments for a business
`GET /v1/businesses/{business_id}/enrichments`

---

#### Create export
`POST /v1/searches/{search_id}/exports`

Request:
```json
{
  "format": "csv",
  "columns": [
    "name","address_full","phone_e164","website_url",
    "instagram","facebook","linkedin","score","social_confidence"
  ]
}
```

Response:
```json
{ "export_id": "uuid", "status": "ready", "download_url": "/v1/exports/uuid" }
```

---

#### Download export
`GET /v1/exports/{export_id}`

---

### 4.3 Error model
All errors return:
```json
{
  "error": {
    "code": "string",
    "message": "human readable",
    "details": {}
  }
}
```

Common error codes:
- `unauthorized`
- `validation_error`
- `rate_limited`
- `budget_exceeded`
- `provider_error`
- `not_found`

---

## 5) Request/response schemas (Pydantic)

### 5.1 Core request models

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any

PlanTier = Literal["basic", "pro", "enterprise"]

class GeoScope(BaseModel):
    country: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2, e.g., CA")
    regions: Optional[List[str]] = None  # e.g., ["BC", "ON"]
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
```

### 5.2 Output models (key subset)

```python
class LeadSocials(BaseModel):
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    linkedin: Optional[str] = None
    tiktok: Optional[str] = None
    x: Optional[str] = None
    youtube: Optional[str] = None

class LeadItem(BaseModel):
    business_id: str
    name: str
    address_full: str
    phone_e164: Optional[str]
    website_url: Optional[str]
    categories: List[str] = []
    score: float
    score_breakdown: Dict[str, float]
    socials: LeadSocials
    social_confidence: float = 0.0
    social_reasons: List[str] = []
    needs_review: bool = False
```

---

## 6) Database schema (DDL sketch)

> This is a sketch; adjust for your ORM (SQLAlchemy) and migrations (Alembic).

### 6.1 `businesses`
- `business_id UUID PK`
- `source TEXT NOT NULL`
- `source_id TEXT NOT NULL`
- `name TEXT NOT NULL`
- `address_full TEXT`
- `city TEXT`
- `region TEXT`
- `postal TEXT`
- `country TEXT`
- `lat DOUBLE PRECISION`
- `lng DOUBLE PRECISION`
- `phone_e164 TEXT`
- `website_url TEXT`
- `categories JSONB`
- `created_at TIMESTAMPTZ`
- `updated_at TIMESTAMPTZ`

Indexes:
- unique `(source, source_id)`
- optional trigram index on `name`, `address_full` for fallback matching

---

### 6.2 `search_jobs`
- `search_id UUID PK`
- `user_id UUID`
- `query TEXT`
- `geo_scope JSONB`
- `target_count INT`
- `plan TEXT`
- `options JSONB`
- `status TEXT`
- `progress JSONB`
- `budget_usage JSONB`
- `created_at TIMESTAMPTZ`
- `completed_at TIMESTAMPTZ`

---

### 6.3 `search_results`
- `search_id UUID FK`
- `business_id UUID FK`
- `rank INT`
- `score DOUBLE PRECISION`
- `score_breakdown JSONB`
- `enrichment_summary JSONB`
Primary key: `(search_id, business_id)`

---

### 6.4 `enrichment_records`
- `enrichment_id UUID PK`
- `business_id UUID FK`
- `type TEXT`
- `source TEXT`
- `data JSONB`
- `confidence DOUBLE PRECISION`
- `reasons JSONB`
- `fetched_at TIMESTAMPTZ`
- `ttl_expires_at TIMESTAMPTZ`

Index:
- `(business_id, type)`

---

### 6.5 `exports`
- `export_id UUID PK`
- `search_id UUID FK`
- `format TEXT`
- `columns JSONB`
- `file_path TEXT`
- `created_at TIMESTAMPTZ`

---

## 7) Provider interfaces (pluggable)

### 7.1 Discovery provider interface

```python
from typing import Protocol, List, Optional, Dict, Any
from dataclasses import dataclass

@dataclass(frozen=True)
class Anchor:
    center_lat: float
    center_lng: float
    radius_km: float
    quota: int

@dataclass(frozen=True)
class RawCandidate:
    source: str
    source_id: str
    payload: Dict[str, Any]  # raw provider response
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

    async def search(self, query: str, anchor: Anchor, *, page_token: Optional[str]=None) -> tuple[List[RawCandidate], Optional[str]]:
        ...
```

### 7.2 SERP provider interface

```python
@dataclass(frozen=True)
class SerpResult:
    title: str
    link: str
    snippet: str
    rank: int

class SerpProvider(Protocol):
    async def search(self, q: str, *, country: Optional[str]=None) -> List[SerpResult]:
        ...
```

---

## 8) Workflow execution interfaces

### 8.1 Shared context model
```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class WorkflowContext:
    search_id: str
    request: dict
    plan: dict = field(default_factory=dict)
    anchors: list = field(default_factory=list)
    raw_candidates: list = field(default_factory=list)
    business_ids: list = field(default_factory=list)
    errors: list = field(default_factory=list)
```

### 8.2 Node interface
```python
from typing import Protocol

class Node(Protocol):
    name: str
    async def run(self, ctx: WorkflowContext) -> WorkflowContext:
        ...
```

### 8.3 DAG runner
- Executes nodes in order
- Persists progress after each node
- On partial failure: continue where safe; record errors in `ctx.errors`
- Supports resuming from last completed node

---

## 9) Caching + budgets

### 9.1 Cache keys
- `discover:{provider}:{query}:{anchor_hash}`
- `site_socials:{domain}`
- `serp_socials:{name_norm}:{city}:{region}`

### 9.2 TTL guidelines
- discovery cache: 7–30 days
- website socials: 30–90 days
- SERP socials: 30–90 days

### 9.3 Budget counters per search
- `website_fetches_used` / `website_fetches_cap`
- `paid_enrichments_used` / `paid_enrichments_cap`
- `provider_calls_used` (optional)

> The runner must check budgets before executing a node batch and stop gracefully when exceeded.

---

## 10) Rate limiting (polite fetching)

- Per-domain website fetch limiter (e.g., 1 request / 3 seconds)
- Global concurrency cap for website fetchers (e.g., 10)
- SERP concurrency cap (e.g., 3–5)

---

## 11) Export formats

### CSV columns (default)
- name
- address_full
- city
- region
- country
- phone_e164
- website_url
- instagram
- facebook
- linkedin
- score
- social_confidence
- needs_review

### JSON export
Include full `score_breakdown`, `social_reasons`, and provenance if user requests.

---

## 12) Example execution: “pharmacies in Canada” → 300

1. RequestPlanner builds nationwide anchors (e.g., 30 anchors × quota 10)
2. DiscoverBusinesses queries provider per anchor until 300 unique businesses deduped
3. ScoreLeads ranks and stores results
4. WebsiteSocialExtractor enriches socials for leads with websites (within fetch cap)
5. AssembleResults marks search `complete` (Basic)
6. (Pro) SerpSocialEnricher enriches top N missing socials (within paid cap)
7. SocialVerifier updates confidence + flags low-confidence for review

---

## 13) Implementation checklist

- [ ] FastAPI app with API key auth
- [ ] SQLAlchemy models + Alembic migrations
- [ ] Redis cache + rate limiting primitives
- [ ] Workflow runner + nodes (async)
- [ ] Provider stub(s) + configuration
- [ ] Export generator
- [ ] Tests for dedupe + scoring + social extraction parsers
- [ ] Observability: structured logs + metrics hooks

---

## 14) Notes on compliance
- Respect provider terms (Google Places quotas/billing)
- Avoid circumventing access controls (no login-wall scraping)
- Store provenance and confidence for transparency
- Prefer business-owned sources (their website) for socials

---
