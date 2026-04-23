"""
Integration tests for /v1/proofs
Run: pytest tests/ -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app

LIVE_KEY = "zk_live_k9mXpQ2nRtY7vLsJ3hWdFbAeUcN4o8_4a2f"
TEST_KEY = "zk_test_r3cVzT5wKnMjXpL8qYdBsGhFuAeN1o6_9c1b"
AUTH     = {"Authorization": f"Bearer {LIVE_KEY}"}


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ------------------------------------------------------------------ #
#  Health                                                              #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ------------------------------------------------------------------ #
#  Auth                                                                #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_no_auth_rejected(client):
    r = await client.post("/v1/proofs", json={})
    assert r.status_code == 401

@pytest.mark.anyio
async def test_bad_key_rejected(client):
    r = await client.post(
        "/v1/proofs",
        headers={"Authorization": "Bearer zk_live_invalid"},
        json={},
    )
    assert r.status_code == 401

@pytest.mark.anyio
async def test_test_key_accepted(client):
    r = await client.get(
        "/v1/proofs/circuits",
        headers={"Authorization": f"Bearer {TEST_KEY}"},
    )
    assert r.status_code == 200


# ------------------------------------------------------------------ #
#  List circuits                                                       #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_list_circuits(client):
    r = await client.get("/v1/proofs/circuits", headers=AUTH)
    assert r.status_code == 200
    names = [c["name"] for c in r.json()["circuits"]]
    assert "identity_verify" in names
    assert "range_proof"     in names
    assert "balance_check"   in names


# ------------------------------------------------------------------ #
#  Generate proofs                                                     #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_generate_identity_verify(client):
    r = await client.post("/v1/proofs", headers=AUTH, json={
        "circuit": "identity_verify",
        "system":  "groth16",
        "inputs":  {"age": 24, "secret": 99999, "threshold": 18, "commitment": 12345},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["circuit"]    == "identity_verify"
    assert body["system"]     == "groth16"
    assert body["verified"]   == True
    assert body["proof_id"].startswith("prf_")
    assert body["latency_ms"] >= 0

@pytest.mark.anyio
async def test_generate_range_proof(client):
    r = await client.post("/v1/proofs", headers=AUTH, json={
        "circuit": "range_proof",
        "system":  "plonk",
        "inputs":  {"value": 50, "secret": 777, "lo": 18, "hi": 65, "commitment": 99},
    })
    assert r.status_code == 200
    assert r.json()["verified"] == True

@pytest.mark.anyio
async def test_generate_balance_check(client):
    r = await client.post("/v1/proofs", headers=AUTH, json={
        "circuit": "balance_check",
        "system":  "poseidon",
        "inputs":  {"balance": 10000, "salt": 42, "required_amount": 500, "commitment": 88},
    })
    assert r.status_code == 200
    assert r.json()["circuit"] == "balance_check"

@pytest.mark.anyio
async def test_generate_returns_proof_fields(client):
    r = await client.post("/v1/proofs", headers=AUTH, json={
        "circuit": "identity_verify",
        "system":  "groth16",
        "inputs":  {"age": 30, "secret": 1, "threshold": 21, "commitment": 2},
    })
    body = r.json()
    assert "proof"      in body
    assert "public"     in body
    assert "created_at" in body


# ------------------------------------------------------------------ #
#  Validation errors                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_unknown_circuit_rejected(client):
    r = await client.post("/v1/proofs", headers=AUTH, json={
        "circuit": "nonexistent_circuit",
        "system":  "groth16",
        "inputs":  {},
    })
    assert r.status_code == 422

@pytest.mark.anyio
async def test_unknown_system_rejected(client):
    r = await client.post("/v1/proofs", headers=AUTH, json={
        "circuit": "identity_verify",
        "system":  "invalid_system",
        "inputs":  {},
    })
    assert r.status_code == 422


# ------------------------------------------------------------------ #
#  Verify endpoint                                                     #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_verify_proof(client):
    gen = await client.post("/v1/proofs", headers=AUTH, json={
        "circuit": "identity_verify",
        "system":  "groth16",
        "inputs":  {"age": 25, "secret": 555, "threshold": 18, "commitment": 777},
    })
    body = gen.json()
    r = await client.post("/v1/proofs/verify", headers=AUTH, json={
        "circuit":        "identity_verify",
        "system":         "groth16",
        "proof":          body["proof"],
        "public_signals": body["public"],
    })
    assert r.status_code == 200
    assert r.json()["verified"] == True


# ------------------------------------------------------------------ #
#  Keys                                                                #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_list_keys(client):
    r = await client.get("/v1/keys", headers=AUTH)
    assert r.status_code == 200
    assert len(r.json()["keys"]) >= 1

@pytest.mark.anyio
async def test_create_key(client):
    r = await client.post("/v1/keys", headers=AUTH, json={
        "label": "ci-test",
        "env":   "test",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["key"].startswith("zk_test_")
    assert "warning" in body
