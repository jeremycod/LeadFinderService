import os
from fastapi import Header, HTTPException

async def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")):
    expected = os.getenv("LEADFINDER_API_KEY", "")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="unauthorized")
