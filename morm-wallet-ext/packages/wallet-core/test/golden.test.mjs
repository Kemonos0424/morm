// Golden-vector test: proves @morm/wallet-core reproduces the MORM L1 Python
// reference byte-for-byte. Run: node --test  (from packages/wallet-core)
// Regenerate vectors with: python3 tools/gen_golden.py
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import {
  addressFromPubkey,
  hexToBytes,
  bytesToHex,
  pubkeyFromSeed,
  buildTransfer,
  buildBridgeBurn,
  signingBytes,
  signTx,
  verify,
  seedToRecovery,
  recoveryToSeed,
} from "../src/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const golden = JSON.parse(readFileSync(join(here, "golden.json"), "utf8"));
const dec = new TextDecoder();

test("golden.json loaded with vectors", () => {
  assert.ok(Array.isArray(golden.vectors) && golden.vectors.length >= 4);
});

for (const [i, v] of golden.vectors.entries()) {
  const seed = hexToBytes(v.seed_hex);

  test(`[${i}] pubkey from seed matches`, async () => {
    const pub = await pubkeyFromSeed(seed);
    assert.equal(bytesToHex(pub), v.pubkey_hex);
  });

  test(`[${i}] address from pubkey matches`, () => {
    const addr = addressFromPubkey(hexToBytes(v.pubkey_hex));
    assert.equal(addr, v.address);
  });

  test(`[${i}] recovery key round-trips and matches web format`, () => {
    assert.equal(seedToRecovery(seed), v.recovery_key);
    assert.equal(bytesToHex(recoveryToSeed(v.recovery_key)), v.seed_hex);
    // Bare hex and spaced/upper variants must also decode to the same seed.
    assert.equal(bytesToHex(recoveryToSeed(v.seed_hex)), v.seed_hex);
  });

  test(`[${i}] signing_bytes match Python canonical JSON`, () => {
    const body = buildTransfer({
      senderPubkeyHex: v.tx.sender,
      nonce: v.tx.nonce,
      to: v.tx.payload.to,
      amount: BigInt(v.tx.amount_str),
    });
    const sb = signingBytes(body);
    assert.equal(dec.decode(sb), v.tx.signing_bytes_utf8);
    assert.equal(bytesToHex(sb), v.tx.signing_bytes_hex);
  });

  test(`[${i}] signature matches Python (deterministic ed25519)`, async () => {
    const body = buildTransfer({
      senderPubkeyHex: v.tx.sender,
      nonce: v.tx.nonce,
      to: v.tx.payload.to,
      amount: BigInt(v.tx.amount_str),
    });
    const signed = await signTx(body, seed);
    assert.equal(signed.signature, v.tx.signature_hex);
    // And the signature verifies against the sender pubkey.
    const ok = await verify(hexToBytes(v.tx.sender), signingBytes(body), hexToBytes(signed.signature));
    assert.ok(ok);
  });

  test(`[${i}] BRIDGE_BURN signing_bytes + signature match Python`, async () => {
    const bb = v.bridge_burn;
    const body = buildBridgeBurn({
      senderPubkeyHex: bb.sender,
      nonce: bb.nonce,
      amount: BigInt(bb.amount_str),
      evmRecipient: bb.evm_recipient,
      token: bb.token,
    });
    assert.equal(dec.decode(signingBytes(body)), bb.signing_bytes_utf8);
    const signed = await signTx(body, seed);
    assert.equal(signed.signature, bb.signature_hex);
  });
}
