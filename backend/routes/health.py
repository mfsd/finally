from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health() -> dict:
    """Health check for Docker / deployment probes."""
    return {"status": "ok"}
