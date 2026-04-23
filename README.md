# ZKProof API

Zero-knowledge proof generation as a service, powered by [ZKSN](https://github.com/Naveenob/zksn).

> "Stripe for ZK proofs" — one API call to generate cryptographic proofs without managing circuits, proving keys, or ZK infrastructure.

---

## Quick start

```bash
  # 1. Install dependencies
  pip install -r requirements.txt
  npm install -g snarkjs

  # 2. Compile circuits (first time only — requires circom binary)
  chmod +x compile_circuits.sh && ./compile_circuits.sh

  # 3. Start the server
  uvicorn main:app --reload
```

API is live at `http://localhost:8000`
Docs at `http://localhost:8000/docs`

---

## Generate a proof

```bash
  curl -X POST http://localhost:8000/v1/proofs \
    -H "Authorization: Bearer zk_live_k9mXpQ2nRtY7vLsJ3hWdFbAeUcN4o8_4a2f" \
    -H "Content-Type: application/json" \
    -d '{
      "circuit":  "identity_verify",
      "system":   "groth16",
      "inputs": {
        "age":        24,
        "secret":     99999,
        "threshold":  18,
        "commitment": 12345
      }
    }'
```

Response:
```json
  {
    "proof_id":   "prf_a1b2c3d4e5f6",
    "circuit":    "identity_verify",
    "system":     "groth16",
    "proof":      { "protocol": "groth16", "pi_a": [...], "pi_b": [...], "pi_c": [...] },
    "public":     ["18", "12345"],
    "verified":   true,
    "latency_ms": 74,
    "created_at": "2026-04-23T11:42:01+00:00"
  }
```

---

## Supported circuits

| Circuit | Proves | Private inputs | Public inputs |
|---|---|---|---|
| `identity_verify` | age ≥ threshold | age, secret | threshold, commitment |
| `range_proof` | lo ≤ value ≤ hi | value, secret | lo, hi, commitment |
| `balance_check` | balance ≥ required | balance, salt | required_amount, commitment |
| `nullifier` | Merkle membership, no double-spend | leaf, path | root, nullifier_hash |

## Proof systems

| System | Proof size | Trusted setup | Best for |
|---|---|---|---|
| `groth16` | ~200 bytes | Per-circuit | Speed, on-chain verification |
| `plonk` | ~800 bytes | Universal | Flexibility, new circuits |
| `poseidon` | ~200 bytes | Per-circuit | On-chain, Poseidon-native |

---

## Project structure

```
zkproof-api/
├── circuits/                   # Circom source files
│   ├── identity_verify.circom
│   ├── range_proof.circom
│   └── balance_check.circom
├── src/
│   ├── middleware/
│   │   ├── auth.py             # Bearer token validation
│   │   └── ratelimit.py        # Sliding-window rate limiter
│   ├── routers/
│   │   ├── proofs.py           # POST /v1/proofs, POST /v1/proofs/verify
│   │   ├── keys.py             # GET/POST /v1/keys
│   │   └── health.py           # GET /health
│   └── services/
│       ├── prover.py           # snarkjs wrapper (Groth16 / PLONK / Poseidon)
│       └── keys.py             # API key store
├── tests/
│   ├── conftest.py
│   └── test_proofs.py          # Full integration test suite
├── .gitignore
├── compile_circuits.sh         # One-shot circuit compilation
├── Dockerfile
├── main.py                     # FastAPI app + lifespan
├── pytest.ini
├── README.md
└── requirements.txt
```

---

## Run tests

```bash
  pytest tests/ -v
```

---

## Deploy (Docker)

```bash
  # Build (after running compile_circuits.sh)
  docker build -t zkproof-api .

  # Run
  docker run -p 8000:8000 zkproof-api
```

---

## Roadmap

- [ ] Redis-backed API key store + proof log persistence
- [ ] Webhook callbacks on proof completion
- [ ] On-chain verifier contract deployment (EVM)
- [ ] Custom circuit upload endpoint
- [ ] SDK packages: `@zkproof/sdk` (JS) + `zkproof` (Python)

---

Built on [ZKSN](https://github.com/Naveenob/zksn) by [novus.forge](https://novusforge.dev)
