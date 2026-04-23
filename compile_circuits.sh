#!/usr/bin/env bash
# compile_circuits.sh
# Compiles all Circom circuits and runs the Groth16/PLONK trusted setup.
# Run once before starting the server in production.
#
# Prerequisites:
#   npm install -g snarkjs
#   npm install -g circom        (or install circom binary from https://docs.circom.io)
#   node >= 16
#
# Output: keys/{circuit}/ directories with .wasm + .zkey + verification_key.json

set -euo pipefail

CIRCUITS_DIR="./circuits"
KEYS_DIR="./keys"
PTAU="powersOfTau28_hez_final_12.ptau"   # fits circuits up to 2^12 constraints

# ── Download Powers of Tau (if not cached) ──────────────────────────────────
if [ ! -f "$PTAU" ]; then
  echo "Downloading Powers of Tau..."
  curl -L -o "$PTAU" \
    "https://hermez.s3-eu-west-1.amazonaws.com/powersOfTau28_hez_final_12.ptau"
fi

compile_circuit() {
  local NAME=$1
  local SRC="$CIRCUITS_DIR/${NAME}.circom"
  local OUT="$KEYS_DIR/${NAME}"

  echo ""
  echo "═══════════════════════════════════════"
  echo "  Compiling: $NAME"
  echo "═══════════════════════════════════════"
  mkdir -p "$OUT"

  # 1. Compile circom → R1CS + WASM + sym
  circom "$SRC" \
    --r1cs --wasm --sym \
    --output "$OUT" \
    --include node_modules    # circomlib path

  # ── Groth16 setup ──────────────────────────────────────────────────
  echo "  [groth16] Phase 2 setup..."
  snarkjs groth16 setup "$OUT/${NAME}.r1cs" "$PTAU" "$OUT/groth16_0.zkey"

  echo "  [groth16] Contribute randomness (deterministic for CI)..."
  echo "zkproof-naveen-entropy-$(date +%s)" | \
    snarkjs zkey contribute "$OUT/groth16_0.zkey" "$OUT/groth16_final.zkey" \
      --name="ZKProof API v1" -v

  echo "  [groth16] Export verification key..."
  snarkjs zkey export verificationkey "$OUT/groth16_final.zkey" "$OUT/verification_key.json"

  # ── PLONK setup ────────────────────────────────────────────────────
  echo "  [plonk] Setup (universal — no phase 2 needed)..."
  snarkjs plonk setup "$OUT/${NAME}.r1cs" "$PTAU" "$OUT/plonk_final.zkey"

  echo "  [plonk] Export verification key..."
  snarkjs zkey export verificationkey "$OUT/plonk_final.zkey" "$OUT/plonk_verification_key.json"

  # Move WASM to expected path
  mv "$OUT/${NAME}_js/${NAME}.wasm" "$OUT/circuit.wasm" 2>/dev/null || true

  echo "  Done → $OUT/"
}

# Compile all circuits
compile_circuit "identity_verify"
compile_circuit "range_proof"
compile_circuit "balance_check"

echo ""
echo "All circuits compiled. Run: uvicorn main:app --reload"
