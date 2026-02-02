from fastapi import APIRouter, Depends, HTTPException
from .schemas import CreateSearchRequest, CreateSearchResponse, SearchStatusResponse
from ..core.auth import require_api_key
from ..core.orchestrator import submit_search, get_search_status

router = APIRouter()

@router.post("/searches", response_model=CreateSearchResponse, dependencies=[Depends(require_api_key)])
async def create_search(req: CreateSearchRequest):
    search_id = await submit_search(req)
    return CreateSearchResponse(search_id=search_id, status="queued")

@router.get("/searches/{search_id}", response_model=SearchStatusResponse, dependencies=[Depends(require_api_key)])
async def read_search(search_id: str):
    status = await get_search_status(search_id)
    if status is None:
        raise HTTPException(status_code=404, detail="search not found")
    return status
