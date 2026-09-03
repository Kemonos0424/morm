// App-logic tests for extension/wallet.js using an in-memory store. Exercises
// create -> lock -> unlock, import round-trip, and wrong-password rejection.
// Requires `node tools/build_ext.mjs` first (wallet.js imports ./walletcore).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const walletUrl = "file://" + join(here, "..", "..", "..", "extension", "wallet.js");
const W = await import(walletUrl);

function memStore() {
  const m = new Map();
  return {
    get: async (k) => m.get(k),
    set: async (k, v) => void m.set(k, v),
    remove: async (k) => void m.delete(k),
    _map: m,
  };
}

test("create -> stored ciphertext only, unlock recovers address", async () => {
  const s = memStore();
  const { address, recoveryKey } = await W.createWithPassword(s, "hunter2hunter");
  assert.match(address, /^m0r[a-z2-7]{32}$/);
  assert.match(recoveryKey, /^morm-rk1-/);
  const rec = await W.loadRecord(s);
  assert.equal(rec.kdf, "pbkdf2");
  assert.ok(rec.ct && rec.iv && rec.saltB64u);
  // No plaintext seed anywhere in storage.
  assert.ok(!JSON.stringify(rec).includes(recoveryKey.replace(/^morm-rk1-/, "").replace(/ /g, "")));
  const session = await W.unlockWithPassword(s, "hunter2hunter");
  assert.equal(session.address, address);
  assert.match(session.seedHex, /^[0-9a-f]{64}$/);
});

test("wrong password is rejected", async () => {
  const s = memStore();
  await W.createWithPassword(s, "correctpassword");
  await assert.rejects(() => W.unlockWithPassword(s, "wrongpassword"), /パスワードが違います/);
});

test("import from recovery key reproduces the same address", async () => {
  const a = memStore();
  const { address, recoveryKey } = await W.createWithPassword(a, "passwordone");
  const b = memStore();
  const imported = await W.importWithPassword(b, recoveryKey, "differentpw");
  assert.equal(imported.address, address); // same seed => same address
  const session = await W.unlockWithPassword(b, "differentpw");
  assert.equal(session.address, address);
});

test("import accepts raw 64-hex too", async () => {
  const a = memStore();
  const { recoveryKey } = await W.createWithPassword(a, "passwordone");
  const s = await W.unlockWithPassword(a, "passwordone");
  const b = memStore();
  const imported = await W.importWithPassword(b, s.seedHex, "pw2pw2pw2");
  const s2 = await W.unlockWithPassword(b, "pw2pw2pw2");
  assert.equal(imported.address, s2.address);
});
