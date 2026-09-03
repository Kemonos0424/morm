// RFC 4648 base32 with the MORM alphabet (lowercase a-z2-7, no padding).
// Matches morm-l1/crypto.py (base64.b32encode(...).lower().rstrip("=")) and
// account.html's inline base32.
const B32 = "abcdefghijklmnopqrstuvwxyz234567";
const B32_MAP = (() => {
  const m = Object.create(null);
  for (let i = 0; i < B32.length; i++) m[B32[i]] = i;
  return m;
})();

// Encode bytes -> lowercase base32 string (no "=" padding).
export function base32Encode(bytes) {
  let out = "";
  let bits = 0;
  let val = 0;
  for (let i = 0; i < bytes.length; i++) {
    val = (val << 8) | bytes[i];
    bits += 8;
    while (bits >= 5) {
      out += B32[(val >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) out += B32[(val << (5 - bits)) & 31];
  return out;
}

// Decode a base32 string (case-insensitive, ignores non-alphabet chars) -> bytes.
export function base32Decode(s) {
  const str = s.toLowerCase();
  let bits = 0;
  let val = 0;
  const out = [];
  for (let i = 0; i < str.length; i++) {
    const c = B32_MAP[str[i]];
    if (c === undefined) continue;
    val = (val << 5) | c;
    bits += 5;
    if (bits >= 8) {
      out.push((val >>> (bits - 8)) & 0xff);
      bits -= 8;
    }
  }
  return new Uint8Array(out);
}
