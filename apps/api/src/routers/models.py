from fastapi import APIRouter, Query
import httpx
from src.config import settings

router = APIRouter(prefix="/models")

@router.get("/search")
async def search_models(source: str = Query("hf"), q: str = Query("")):
    if source == "hf":
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://huggingface.co/api/models",
                params={"search": q, "limit": 20},
                headers={"Authorization": f"Bearer {settings.hf_token}"} if settings.hf_token else {},
            )
        return r.json()
    elif source == "ollama":
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:11434/api/tags")
        return r.json()
    return {"models": []}
