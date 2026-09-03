// PRF-protected wallet path. A real WebAuthn ceremony can't run headless, so we
// inject a synthetic 32-byte PRF secret (what the authenticator would return)
// and verify protect -> record shape -> unlock round-trips, and that the wrong
// PRF secret fails. Requires `node tools/build_ext.mjs` first.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const W = await import("file://" + join(here, "..", "..", "..", "extension", "wallet.js"));

function memStore() {
  const m = new Map();
  return { get: async (k) => m.get(k), set: async (k, v) => void m.set(k, v), remove: async (k) => void m.delete(k) };
}
const PRF = new Uint8Array(32).fill(7);      // stand-in for the passkey PRF secret
const CRED = "Y3JlZC1pZC1zYW1wbGU";           // stand-in credId (base64url)

test("PRF protect stores prf record with credId, no plaintext seed", async () => {
  const s = memStore();
  const { seed } = await import("file://" + join(here, "..", "src", "index.js")).then((c) => c.generateSeed());
  const { address } = await W.protectWithPRF(s, seed, PRF, CRED);
  const rec = await W.loadRecord(s);
  assert.equal(rec.kdf, "prf");
  assert.equal(rec.credIdB64u, CRED);
  assert.equal(rec.saltB64u, null);
  assert.ok(rec.ct && rec.iv);
  assert.equal(rec.address, address);
});

test("PRF unlock round-trips with the same secret", async () => {
  const s = memStore();
  const core = await import("file://" + join(here, "..", "src", "index.js"));
  const { seed } = await core.generateSeed();
  const expectedAddr = core.addressFromPubkey(await core.pubkeyFromSeed(seed));
  await W.protectWithPRF(s, seed, PRF, CRED);
  const session = await W.unlockWithPRF(s, PRF);
  assert.equal(session.address, expectedAddr);
  assert.match(session.seedHex, /^[0-9a-f]{64}$/);
});

test("PRF unlock with wrong secret fails", async () => {
  const s = memStore();
  const core = await import("file://" + join(here, "..", "src", "index.js"));
  const { seed } = await core.generateSeed();
  await W.protectWithPRF(s, seed, PRF, CRED);
  const wrong = new Uint8Array(32).fill(9);
  await assert.rejects(() => W.unlockWithPRF(s, wrong));
});
