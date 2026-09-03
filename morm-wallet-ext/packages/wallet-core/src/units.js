// MORM <-> integer base units, exact (BigInt). Mirrors morm-units.js semantics:
// baseUnitsPerMorm is live-configurable (1 today; 1e6 = µMORM planned). The
// wallet reads the live value from the account API and never hardcodes it.
// Amounts are integers on-chain, so display MORM may be fractional only when the
// base allows it — a too-fine amount is rejected rather than silently rounded.

// "12.5" (MORM string) + base -> BigInt base units. Throws on bad/too-fine input.
export function mormToBaseUnits(mormStr, base) {
  const b = BigInt(base);
  if (b <= 0n) throw new Error("baseUnitsPerMorm must be >= 1");
  const s = String(mormStr).trim();
  if (!/^\d+(\.\d+)?$/.test(s)) throw new Error("金額の形式が不正です");
  const [ip, fp = ""] = s.split(".");
  let units = BigInt(ip) * b;
  if (fp.length) {
    const denom = 10n ** BigInt(fp.length);
    const num = BigInt(fp) * b;
    if (num % denom !== 0n) {
      throw new Error("この金額はチェーンの最小単位で表せません（桁が細かすぎます）");
    }
    units += num / denom;
  }
  if (units <= 0n) throw new Error("金額は正の値を指定してください");
  return units;
}

// BigInt/number base units + base -> trimmed MORM display string.
export function formatBaseUnits(units, base) {
  const b = BigInt(base);
  const u = BigInt(units);
  const whole = u / b;
  const frac = u % b;
  if (frac === 0n) return whole.toString();
  // Fractional digits = width of base (power-of-10 bases give clean decimals).
  const width = b.toString().length - 1;
  let f = frac.toString().padStart(width, "0").replace(/0+$/, "");
  return `${whole.toString()}.${f}`;
}
