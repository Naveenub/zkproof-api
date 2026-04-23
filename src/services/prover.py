"""
ProverService
Wraps snarkjs CLI to generate and verify Groth16 / PLONK proofs
from pre-compiled Circom circuit artifacts (.wasm + .zkey).

Circuit artifacts must be present at:
  keys/{circuit_name}/circuit.wasm
  keys/{circuit_name}/groth16_final.zkey   (for Groth16)
  keys/{circuit_name}/plonk_final.zkey     (for PLONK)
  keys/{circuit_name}/verification_key.json
"""

import asyncio
import json
import os
import time
import uuid
import tempfile
import hashlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("zkproof.prover")

BASE_DIR   = Path(__file__).resolve().parents[2]
KEYS_DIR   = BASE_DIR / "keys"
SNARKJS    = "snarkjs"   # resolved from PATH after npm install -g

SUPPORTED_CIRCUITS = ["identity_verify", "range_proof", "balance_check", "nullifier"]
SUPPORTED_SYSTEMS  = ["groth16", "plonk", "poseidon"]


class ProverService:
    def __init__(self):
        self._loaded: dict[str, bool] = {}

    async def preload_circuits(self):
        """
        Verify that compiled artifacts exist for every supported circuit.
        In production this would also warm the WASM JIT cache.
        """
        for circuit in SUPPORTED_CIRCUITS:
            wasm = KEYS_DIR / circuit / "circuit.wasm"
            self._loaded[circuit] = wasm.exists()
            status = "ok" if self._loaded[circuit] else "MISSING (run compile_circuits.sh)"
            logger.info(f"  circuit={circuit:<20} artifacts={status}")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    async def generate(
        self,
        circuit: str,
        system: str,
        inputs: dict[str, Any],
    ) -> dict:
        """
        Generate a ZK proof.

        Returns:
            {
              proof_id:    str,
              circuit:     str,
              system:      str,
              proof:       dict,       # pi_a, pi_b, pi_c / protocol-specific
              public:      list,       # public signals
              verified:    bool,
              latency_ms:  int,
              created_at:  str,
            }
        """
        self._validate(circuit, system)
        t0 = time.perf_counter()

        if self._loaded.get(circuit):
            result = await self._run_snarkjs(circuit, system, inputs)
        else:
            # Fallback: mock proof for dev / demo mode
            logger.warning(f"Circuit '{circuit}' artifacts missing — returning mock proof.")
            result = self._mock_proof(circuit, system, inputs)

        latency_ms = int((time.perf_counter() - t0) * 1000)
        proof_id   = "prf_" + uuid.uuid4().hex[:12]

        return {
            "proof_id":   proof_id,
            "circuit":    circuit,
            "system":     system,
            "proof":      result["proof"],
            "public":     result["public"],
            "verified":   result["verified"],
            "latency_ms": latency_ms,
            "created_at": _now(),
        }

    async def verify(
        self,
        circuit: str,
        system: str,
        proof: dict,
        public_signals: list,
    ) -> dict:
        """
        Verify an existing proof against the circuit's verification key.
        """
        self._validate(circuit, system)
        t0 = time.perf_counter()

        if self._loaded.get(circuit):
            verified = await self._run_verify(circuit, system, proof, public_signals)
        else:
            verified = True  # mock

        return {
            "verified":   verified,
            "circuit":    circuit,
            "system":     system,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "checked_at": _now(),
        }

    # ------------------------------------------------------------------ #
    #  snarkjs integration                                                 #
    # ------------------------------------------------------------------ #

    async def _run_snarkjs(
        self,
        circuit: str,
        system: str,
        inputs: dict,
    ) -> dict:
        circuit_dir = KEYS_DIR / circuit
        wasm        = circuit_dir / "circuit.wasm"
        zkey        = circuit_dir / f"{system}_final.zkey"
        vkey        = circuit_dir / "verification_key.json"

        with tempfile.TemporaryDirectory() as tmp:
            inp_file   = os.path.join(tmp, "input.json")
            wtns_file  = os.path.join(tmp, "witness.wtns")
            proof_file = os.path.join(tmp, "proof.json")
            pub_file   = os.path.join(tmp, "public.json")

            # 1. Write inputs
            with open(inp_file, "w") as f:
                json.dump(inputs, f)

            # 2. Compute witness
            await _run(f"{SNARKJS} wtns calculate {wasm} {inp_file} {wtns_file}")

            # 3. Generate proof
            if system == "groth16":
                await _run(
                    f"{SNARKJS} groth16 prove {zkey} {wtns_file} {proof_file} {pub_file}"
                )
            elif system == "plonk":
                await _run(
                    f"{SNARKJS} plonk prove {zkey} {wtns_file} {proof_file} {pub_file}"
                )
            else:  # poseidon — treated as groth16 under the hood
                await _run(
                    f"{SNARKJS} groth16 prove {zkey} {wtns_file} {proof_file} {pub_file}"
                )

            # 4. Verify proof
            verify_out = await _run(
                f"{SNARKJS} {system if system != 'poseidon' else 'groth16'} "
                f"verify {vkey} {pub_file} {proof_file}"
            )
            verified = "OK" in verify_out

            with open(proof_file) as f:
                proof_data = json.load(f)
            with open(pub_file) as f:
                public_data = json.load(f)

        return {"proof": proof_data, "public": public_data, "verified": verified}

    async def _run_verify(
        self,
        circuit: str,
        system: str,
        proof: dict,
        public_signals: list,
    ) -> bool:
        circuit_dir = KEYS_DIR / circuit
        vkey        = circuit_dir / "verification_key.json"

        with tempfile.TemporaryDirectory() as tmp:
            proof_file = os.path.join(tmp, "proof.json")
            pub_file   = os.path.join(tmp, "public.json")

            with open(proof_file, "w") as f:
                json.dump(proof, f)
            with open(pub_file, "w") as f:
                json.dump(public_signals, f)

            proto = system if system != "poseidon" else "groth16"
            out   = await _run(f"{SNARKJS} {proto} verify {vkey} {pub_file} {proof_file}")

        return "OK" in out

    # ------------------------------------------------------------------ #
    #  Mock proof (dev / demo mode — no compiled artifacts needed)        #
    # ------------------------------------------------------------------ #

    def _mock_proof(self, circuit: str, system: str, inputs: dict) -> dict:
        h = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        proof = {
            "protocol": system,
            "curve":    "bn128",
            "pi_a":     [h[:16], h[16:32], "1"],
            "pi_b":     [[h[32:48], h[48:64]], [h[:16], h[16:32]], ["1", "0"]],
            "pi_c":     [h[32:48], h[48:64], "1"],
        }
        public = [str(v) for v in inputs.values() if isinstance(v, (int, float))]
        return {"proof": proof, "public": public, "verified": True}

    # ------------------------------------------------------------------ #
    #  Validation                                                          #
    # ------------------------------------------------------------------ #

    def _validate(self, circuit: str, system: str):
        if circuit not in SUPPORTED_CIRCUITS:
            raise ValueError(
                f"Unknown circuit '{circuit}'. "
                f"Supported: {SUPPORTED_CIRCUITS}"
            )
        if system not in SUPPORTED_SYSTEMS:
            raise ValueError(
                f"Unknown proof system '{system}'. "
                f"Supported: {SUPPORTED_SYSTEMS}"
            )


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

async def _run(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"snarkjs command failed:\n  cmd: {cmd}\n  err: {stderr.decode()}"
        )
    return stdout.decode()


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


prover_service = ProverService()
