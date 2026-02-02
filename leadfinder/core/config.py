from pydantic import BaseModel
import os

class Settings(BaseModel):
    discovery_provider: str = os.getenv("DISCOVERY_PROVIDER", "osm")
    google_places_api_key: str = os.getenv("GOOGLE_PLACES_API_KEY", "")
    serper_api_key: str = os.getenv("SERPER_API_KEY", "")
    export_dir: str = os.getenv("EXPORT_DIR", "./exports")

settings = Settings()
