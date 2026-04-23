pragma circom 2.0.0;

include "circomlib/circuits/comparators.circom";
include "circomlib/circuits/poseidon.circom";

/*
 * RangeProof
 * Proves: lo <= value <= hi, without revealing value.
 * Public inputs:  lo, hi, commitment
 * Private inputs: value, secret
 *
 * commitment = Poseidon(value, secret)
 */
template RangeProof() {
    signal input value;
    signal input secret;

    signal input lo;
    signal input hi;
    signal input commitment;

    // 1. Verify commitment
    component hasher = Poseidon(2);
    hasher.inputs[0] <== value;
    hasher.inputs[1] <== secret;
    hasher.out === commitment;

    // 2. value >= lo
    component gte = GreaterEqThan(64);
    gte.in[0] <== value;
    gte.in[1] <== lo;
    gte.out === 1;

    // 3. value <= hi
    component lte = LessEqThan(64);
    lte.in[0] <== value;
    lte.in[1] <== hi;
    lte.out === 1;
}

component main { public [lo, hi, commitment] } = RangeProof();
