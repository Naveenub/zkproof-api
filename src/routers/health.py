from fastapi import APIRouter
from src.services.prover import prover_service, SUPPORTED_CIRCUITS

router = APIRouter(tags=["health"])

@router.get("/health", summary="Health check")
async def health():
    return {
        "status":   "ok",
        "version":  "1.0.0",
        "circuits": {c: prover_service._loaded.get(c, False) for c in SUPPORTED_CIRCUITS},
    }
