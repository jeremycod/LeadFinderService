import uuid
from .config import settings

# NOTE: This is a placeholder orchestrator.
# In a real deployment, this would enqueue a job to a worker (Celery/RQ/Arq).
# For the starter project, we just create an ID and store minimal in-memory state.

_IN_MEMORY = {}

async def submit_search(req) -> str:
    search_id = str(uuid.uuid4())
    _IN_MEMORY[search_id] = {
        "search_id": search_id,
        "status": "queued",
        "progress": {"anchors_total": 0, "anchors_done": 0},
        "budget_usage": {"paid_enrichments_used": 0},
        "summary": {"lead_count_ready": 0},
    }
    return search_id

async def get_search_status(search_id: str):
    return _IN_MEMORY.get(search_id)
