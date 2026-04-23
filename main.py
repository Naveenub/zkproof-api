"""
ZKProof API — /v1/proofs endpoint
Wraps ZKSN Circom circuits (Groth16 / PLONK / Poseidon)
via snarkjs under the hood.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from src.routers import proofs, keys, health
from src.middleware.auth import APIKeyMiddleware
from src.middleware.ratelimit import RateLimitMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("zkproof")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ZKProof API starting — preloading circuit artifacts...")
    from src.services.prover import prover_service
    await prover_service.preload_circuits()
    logger.info("Circuit artifacts loaded. Ready.")
    yield
    logger.info("ZKProof API shutting down.")

    
app = FastAPI(
    title="ZKProof API",
    description="Zero-knowledge proof generation as a service, powered by ZKSN.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(APIKeyMiddleware, exempt_paths=["/health", "/docs", "/redoc", "/openapi.json"])

app.include_router(health.router)
app.include_router(proofs.router, prefix="/v1")
app.include_router(keys.router,   prefix="/v1")
