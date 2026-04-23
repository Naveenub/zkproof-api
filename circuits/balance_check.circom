pragma circom 2.0.0;

include "circomlib/circuits/comparators.circom";
include "circomlib/circuits/poseidon.circom";

/*
 * BalanceCheck
 * Proves: balance >= required_amount, without revealing balance.
 * Public inputs:  required_amount, commitment
 * Private inputs: balance, salt
 *
 * commitment = Poseidon(balance, salt)
 */
template BalanceCheck() {
    signal input balance;
    signal input salt;

    signal input required_amount;
    signal input commitment;

    // 1. Verify commitment
    component hasher = Poseidon(2);
    hasher.inputs[0] <== balance;
    hasher.inputs[1] <== salt;
    hasher.out === commitment;

    // 2. Prove balance >= required_amount (64-bit supports up to ~18 quintillion)
    component gte = GreaterEqThan(64);
    gte.in[0] <== balance;
    gte.in[1] <== required_amount;
    gte.out === 1;
}

component main { public [required_amount, commitment] } = BalanceCheck();
