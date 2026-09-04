// Ed25519 via vendored @noble/ed25519 (pure JS) with WebCrypto SHA-512 for the
// internal hash. Pure-JS curve math means this works EVERYWHERE — Chrome
// extension, Node, and mobile WebViews (iOS WKWebView lacks WebCrypto Ed25519
// on iOS <17; SHA-512 digest is available everywhere). Ed25519 is deterministic,
// so signatures/keys are byte-identical to the Python reference (pinned by the
// golden vectors).
import * as ed from "./vendor/noble-ed25519.js";

const subtle = globalThis.crypto?.subtle;
if (!subtle) throw new Error("WebCrypto SubtleCrypto unavailable");

// Provide SHA-512 to @noble via WebCrypto (async). Available in all target
// runtimes including iOS WKWebView.
ed.etc.sha512Async = async (...msgs) => {
  const total = msgs.reduce((n, m) => n + m.length, 0);
  const buf = new Uint8Array(total);
  let o = 0;
  for (const m of msgs) { buf.set(m, o); o += m.length; }
  return new Uint8Array(await subtle.digest("SHA-512", buf));
};

export function bytesToHex(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += bytes[i].toString(16).padStart(2, "0");
  return s;
}

export function hexToBytes(hex) {
  const clean = hex.length % 2 ? "0" + hex : hex;
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(clean.substr(i * 2, 2), 16);
  return out;
}

function assertSeed(seed) {
  if (!(seed instanceof Uint8Array) || seed.length !== 32) {
    throw new Error("seed must be a 32-byte Uint8Array");
  }
}

// Generate a fresh account: { seed, pubkey } as 32-byte Uint8Arrays.
export async function generateSeed() {
  const seed = crypto.getRandomValues(new Uint8Array(32));
  const pubkey = await ed.getPublicKeyAsync(seed);
  return { seed, pubkey };
}

// Derive the 32-byte public key from a 32-byte seed.
export async function pubkeyFromSeed(seed) {
  assertSeed(seed);
  return ed.getPublicKeyAsync(seed);
}

// Sign a message (Uint8Array) with the seed; returns a 64-byte signature.
export async function sign(seed, message) {
  assertSeed(seed);
  return ed.signAsync(message, seed);
}

// Verify a signature given a raw 32-byte public key.
export async function verify(pubkey, message, signature) {
  try {
    return await ed.verifyAsync(signature, message, pubkey);
  } catch {
    return false;
  }
}
