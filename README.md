# LeadFinder Service (Python)

This repo is a starter skeleton for the **LeadFinder** service:
- FastAPI API
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

## Docs
- See `docs/spec.md` for the full specification.
