// Recovery-key encoding — identical to account.html seedToRecovery/recoveryToSeed.
//   morm-rk1-<base32(seed)>  grouped in 4-char blocks (display only).
// This is the interop bridge with the web wallet: a key exported here restores
// on morm.one and vice-versa. The recovery key IS the raw 32-byte seed in
// base32 — treat it as the highest-sensitivity secret (see SECURITY notes).
import { base32Encode, base32Decode } from "./base32.js";
import { hexToBytes } from "./ed25519.js";

const PREFIX = "morm-rk1-";

// 32-byte seed (Uint8Array) -> display recovery key.
export function seedToRecovery(seed) {
  if (!(seed instanceof Uint8Array) || seed.length !== 32) {
    throw new Error("seed must be a 32-byte Uint8Array");
  }
  const body = base32Encode(seed).replace(/(.{4})/g, "$1 ").trim();
  return PREFIX + body;
}

// Accepts a morm-rk1 recovery key, a bare base32 body, or raw 64-hex.
// Returns a 32-byte Uint8Array seed. Throws if it cannot decode to 32 bytes.
export function recoveryToSeed(input) {
  let s = String(input).trim().toLowerCase().replace(/\s+/g, "");
  if (s.startsWith(PREFIX)) s = s.slice(PREFIX.length);
  if (/^[0-9a-f]{64}$/.test(s)) return hexToBytes(s);
  const bytes = base32Decode(s).slice(0, 32);
  if (bytes.length !== 32) throw new Error("recovery key does not decode to 32 bytes");
  return bytes;
}
