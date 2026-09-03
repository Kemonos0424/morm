// Canonical JSON matching Python's
//   json.dumps(obj, sort_keys=True, separators=(",", ":"))
// combined with morm-l1/tx.py `_canonicalize` (recursively sorts dict keys).
// This is the exact pre-image the MORM L1 signs/verifies, so it MUST agree
// byte-for-byte with the Python encoder — pinned by the golden vectors.
//
// Integer amounts on MORM can exceed 2^53 (balances reach 京 = 1e16+), so
// integers are carried as BigInt and emitted verbatim (no quotes, no exponent).
// All MORM tx keys/values are ASCII, so we never hit the ensure_ascii escaping
// difference between Python (escapes non-ASCII) and JS (does not).

export function canonicalStringify(value) {
  if (value === null) return "null";
  const t = typeof value;

  if (t === "bigint") return value.toString();

  if (t === "number") {
    if (!Number.isFinite(value)) throw new Error("non-finite number in tx");
    if (!Number.isInteger(value)) {
      throw new Error("non-integer number in tx (use BigInt / integers only)");
    }
    if (!Number.isSafeInteger(value)) {
      throw new Error("unsafe integer; pass amounts as BigInt to avoid precision loss");
    }
    return String(value);
  }

  if (t === "boolean") return value ? "true" : "false";
  if (t === "string") return JSON.stringify(value);

  if (Array.isArray(value)) {
    return "[" + value.map(canonicalStringify).join(",") + "]";
  }

  if (t === "object") {
    // Sort keys by code point (Python sort_keys); ASCII keys => same as JS default.
    const keys = Object.keys(value).sort();
    const parts = keys.map(
      (k) => JSON.stringify(k) + ":" + canonicalStringify(value[k]),
    );
    return "{" + parts.join(",") + "}";
  }

  throw new Error("unsupported type in canonical JSON: " + t);
}

const enc = new TextEncoder();

// UTF-8 bytes of the canonical form — the exact ed25519 pre-image.
export function canonicalBytes(value) {
  return enc.encode(canonicalStringify(value));
}
