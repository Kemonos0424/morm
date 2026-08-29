// MORM unit system — single source of truth for MORM <-> integer base units.
//
// The L1 stores balances as integers only (no decimals). "1 MORM" is defined as
// MORM_BASE_UNITS_PER_MORM base units. Base = 1 (the current live default) means
// 1 unit == 1 MORM and there is no sub-MORM on-chain. Phase 2 proportional
// emission needs sub-MORM (per-head rewards are often < 1 MORM), so a coordinated
// cutover raises the base to 1e6 (µMORM). Flipping the base REINTERPRETS every
// existing on-chain balance, so it is a coordinated migration — never a silent
// change. This module keeps the conversion in ONE place so a cutover is a single
// env change, and every read/write boundary stays consistent.
//
//   env MORM_BASE_UNITS_PER_MORM : integer >= 1 (default 1). Phase 2 target 1e6.

export function baseUnitsPerMorm() {
  const v = Number(process.env.MORM_BASE_UNITS_PER_MORM || 1);
  return Number.isFinite(v) && v >= 1 ? Math.floor(v) : 1;
}

// MORM (display, may be fractional) -> integer base units. Throws on bad input.
export function mormToUnits(morm) {
  const units = Math.round(Number(morm) * baseUnitsPerMorm());
  if (!Number.isFinite(units) || units < 0) {
    throw new Error(`invalid MORM amount: ${morm}`);
  }
  return units;
}

// integer base units -> MORM (may be fractional).
export function unitsToMorm(units) {
  return Number(units || 0) / baseUnitsPerMorm();
}

// Human string in MORM, trimming trailing zeros (e.g. 5000000 -> "5", 2000 -> "0.002").
export function formatMorm(units, dp = 6) {
  const s = unitsToMorm(units).toFixed(dp);
  return s.includes('.') ? s.replace(/\.?0+$/, '') : s;
}
