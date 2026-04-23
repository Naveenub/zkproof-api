"""
/v1/proofs  — core proof generation & verification endpoints
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Any, Literal

from src.services.prover import prover_service, SUPPORTED_CIRCUITS, SUPPORTED_SYSTEMS

router = APIRouter(tags=["proofs"])


# ------------------------------------------------------------------ #
#  Request / Response models                                           #
# ------------------------------------------------------------------ #

class GenerateRequest(BaseModel):
    circuit: str = Field(
        ...,
        description="Circuit name",
        examples=["identity_verify", "range_proof", "balance_check", "nullifier"],
    )
    system: Literal["groth16", "plonk", "poseidon"] = Field(
        "groth16",
        description="Proof system",
    )
    inputs: dict[str, Any] = Field(
        ...,
        description="Circuit inputs (private + public). See circuit docs for required fields.",
        examples=[{"age": 24, "secret": 12345, "threshold": 18, "commitment": "0x..."}],
    )

    @field_validator("circuit")
    @classmethod
    def validate_circuit(cls, v):
        if v not in SUPPORTED_CIRCUITS:
            raise ValueError(f"Unknown circuit '{v}'. Supported: {SUPPORTED_CIRCUITS}")
        return v


class ProofResponse(BaseModel):
    proof_id:   str
    circuit:    str
    system:     str
    proof:      dict
    public:     list
    verified:   bool
    latency_ms: int
    created_at: str


class VerifyRequest(BaseModel):
    circuit:        str
    system:         Literal["groth16", "plonk", "poseidon"] = "groth16"
    proof:          dict
    public_signals: list


class VerifyResponse(BaseModel):
    verified:   bool
    circuit:    str
    system:     str
    latency_ms: int
    checked_at: str


# ------------------------------------------------------------------ #
#  Routes                                                              #
# ------------------------------------------------------------------ #

@router.post(
    "/proofs",
    response_model=ProofResponse,
    summary="Generate a ZK proof",
    description="""
Generate a zero-knowledge proof for the specified circuit and inputs.

### Supported circuits

| Circuit | Proves | Private inputs | Public inputs |
|---|---|---|---|
| `identity_verify` | age ≥ threshold | age, secret | threshold, commitment |
| `range_proof` | lo ≤ value ≤ hi | value, secret | lo, hi, commitment |
| `balance_check` | balance ≥ required | balance, salt | required_amount, commitment |
| `nullifier` | membership without double-spend | leaf, path, root | nullifier_hash |

### Proof systems
- `groth16` — smallest proof size (~200 bytes), fastest verification
- `plonk` — universal trusted setup, larger proof
- `poseidon` — Poseidon-hash based, optimised for on-chain verification
""",
)
async def generate_proof(body: GenerateRequest, request: Request):
    api_key = request.state.api_key

    # Live key quota check
    if api_key.env == "live" and api_key.proofs_used > api_key.monthly_limit:
        raise HTTPException(
            status_code=402,
            detail={
                "error":   "quota_exceeded",
                "message": f"Monthly quota of {api_key.monthly_limit:,} proofs exceeded. "
                           "Overages billed at $0.004/proof — upgrade in the dashboard.",
            },
        )

    try:
        result = await prover_service.generate(
            circuit=body.circuit,
            system=body.system,
            inputs=body.inputs,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": "invalid_input", "message": str(e)})
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail={"error": "prover_error",   "message": str(e)})

    return result


@router.post(
    "/proofs/verify",
    response_model=VerifyResponse,
    summary="Verify an existing proof",
)
async def verify_proof(body: VerifyRequest, request: Request):
    try:
        result = await prover_service.verify(
            circuit=body.circuit,
            system=body.system,
            proof=body.proof,
            public_signals=body.public_signals,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": "invalid_input", "message": str(e)})
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail={"error": "prover_error",   "message": str(e)})

    return result


@router.get(
    "/proofs/circuits",
    summary="List supported circuits",
)
async def list_circuits():
    return {
        "circuits": [
            {
                "name":           "identity_verify",
                "description":    "Proves age ≥ threshold without revealing age.",
                "private_inputs": ["age", "secret"],
                "public_inputs":  ["threshold", "commitment"],
                "systems":        ["groth16", "plonk", "poseidon"],
            },
            {
                "name":           "range_proof",
                "description":    "Proves lo ≤ value ≤ hi without revealing value.",
                "private_inputs": ["value", "secret"],
                "public_inputs":  ["lo", "hi", "commitment"],
                "systems":        ["groth16", "plonk"],
            },
            {
                "name":           "balance_check",
                "description":    "Proves balance ≥ required_amount without revealing balance.",
                "private_inputs": ["balance", "salt"],
                "public_inputs":  ["required_amount", "commitment"],
                "systems":        ["groth16", "plonk", "poseidon"],
            },
            {
                "name":           "nullifier",
                "description":    "Proves Merkle membership; prevents double-spend via nullifier.",
                "private_inputs": ["leaf", "path_elements", "path_indices"],
                "public_inputs":  ["root", "nullifier_hash"],
                "systems":        ["groth16"],
            },
        ]
    }
