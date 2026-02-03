# LeadFinder Service (Python)

This repo implements the **LeadFinder** service: a self-serve lead generation workflow
that discovers businesses by **query + geography**, enriches them (website-first, SERP
fallback), scores confidence, and exports results.

Key features:
- FastAPI API with API key auth
- async workflow runner (DAG)
- pluggable discovery + SERP providers
- caching + budget enforcement
- export to CSV/JSON

## Quick start (dev)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn leadfinder.api.app:app --reload
```

## Optional (uv)
```bash
uv pip install -e ".[dev]"
uvicorn leadfinder.api.app:app --reload
```

## Environment
Create `.env` at repo root (see `.env.example`):
- `GOOGLE_PLACES_API_KEY` (required for Google Places discovery)
- `SERPER_API_KEY` (optional; SERP enrichment)
- `DATABASE_URL` (Postgres)
- `REDIS_URL` (Redis)
- `EXPORT_DIR` (export output path)

## Architecture overview
- **FastAPI API**: request validation, auth, job orchestration, pagination, exports
- **Worker(s)**: execute workflow DAG + enrichment batches
- **Postgres**: persistence for entities, searches, enrichments, exports
- **Redis**: caching + rate-limit + job coordination
- **Object storage**: export artifacts (local for dev; S3-compatible for prod)

## Workflow (DAG) nodes
1. RequestPlanner
2. AnchorGenerator
3. DiscoverBusinesses
4. CanonicalizeAndDedupe
5. ScoreLeads
6. WebsiteSocialExtractor
7. (Pro) SerpSocialEnricher
8. SocialVerifier
9. AssembleResults
10. ExportGenerator

## API (summary)
- `POST /v1/searches`
- `GET /v1/searches/{search_id}`
- `GET /v1/searches/{search_id}/leads`
- `POST /v1/searches/{search_id}/enrich` (Pro)
- `POST /v1/searches/{search_id}/exports`
- `GET /v1/exports/{export_id}`

## Notebooks
- `notebooks/1_init.ipynb`: LangGraph + tool sandbox and chat UI
- `notebooks/2_run_example.ipynb`: runs the full workflow with a Gradio form

## Docs
- See `docs/spec.md` for the full specification.
