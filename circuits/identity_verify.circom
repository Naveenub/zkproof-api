pragma circom 2.0.0;

include "circomlib/circuits/comparators.circom";
include "circomlib/circuits/poseidon.circom";

/*
 * IdentityVerify
 * Proves: age >= threshold, without revealing age.
 * Public inputs:  threshold, commitment
 * Private inputs: age, secret
 *
 * commitment = Poseidon(age, secret)
 */
template IdentityVerify() {
    // private
    signal input age;
    signal input secret;

    // public
    signal input threshold;
    signal input commitment;

    // 1. Verify commitment
    component hasher = Poseidon(2);
    hasher.inputs[0] <== age;
    hasher.inputs[1] <== secret;
    hasher.out === commitment;

    // 2. Prove age >= threshold
    component gte = GreaterEqThan(8); // 8-bit: supports 0..255
    gte.in[0] <== age;
    gte.in[1] <== threshold;
    gte.out === 1;
}

component main { public [threshold, commitment] } = IdentityVerify();
