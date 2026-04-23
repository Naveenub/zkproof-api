"""
/v1/keys — API key management
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Literal

from src.services.keys import api_key_service

router = APIRouter(tags=["keys"])


class CreateKeyRequest(BaseModel):
    label: str
    env:   Literal["live", "test"] = "test"


@router.post("/keys", summary="Create a new API key")
async def create_key(body: CreateKeyRequest, request: Request):
    owner   = request.state.api_key.owner
    raw, key = api_key_service.create(label=body.label, env=body.env, owner=owner)
    return {
        "key":        raw,          # shown ONCE — store it now
        "key_id":     key.key_id,
        "label":      key.label,
        "env":        key.env,
        "created_at": key.created_at,
        "warning":    "Store this key securely. It will not be shown again.",
    }


@router.get("/keys", summary="List your API keys")
async def list_keys(request: Request):
    owner = request.state.api_key.owner
    keys  = api_key_service.list_for_owner(owner)
    return {
        "keys": [
            {
                "key_id":       k.key_id,
                "label":        k.label,
                "env":          k.env,
                "revoked":      k.revoked,
                "proofs_used":  k.proofs_used,
                "monthly_limit": k.monthly_limit,
                "created_at":   k.created_at,
            }
            for k in keys
        ]
    }


@router.delete("/keys/{key_id}", summary="Revoke an API key")
async def revoke_key(key_id: str, request: Request):
    # In a real system, look up by key_id scoped to owner
    return {"revoked": True, "key_id": key_id}
