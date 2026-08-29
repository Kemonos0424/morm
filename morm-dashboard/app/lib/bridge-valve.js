import { dbExec, dbRun, dbGet } from '@/app/lib/db';
import { unitsToMorm } from '@/app/lib/morm-units';
import { getPriceReserve } from '@/app/lib/morm-price';

// Cash-out valve (Phase 2-③). Throttles the FORWARD bridge (BRIDGE_BURN → wMORM)
// so cashing MORM out cannot crater the thin $0.0136 wMORM/USDC pool reference.
// Three limits, all in USD terms via the live price:
//   • system 24h ≤ BRIDGE_SYSTEM_DAILY_FRAC × USDC-reserve  (default 0.5%)
//   • per-account 24h ≤ BRIDGE_ACCT_DAILY_USD
//   • per-account cooldown ≥ BRIDGE_COOLDOWN_SEC between burns
// Flag-gated: BRIDGE_VALVE=on enforces; anything else = bypass (non-destructive,
// current behavior). If the pool reserve is unknown, the system cap falls back
// to a conservative absolute USD/day (fail-safe, not fail-open).
const on = () => (process.env.BRIDGE_VALVE || 'off').toLowerCase() === 'on';
const sysFrac = () => Number(process.env.BRIDGE_SYSTEM_DAILY_FRAC || 0.005);
const acctDailyUsd = () => Number(process.env.BRIDGE_ACCT_DAILY_USD || 50);
const cooldownSec = () => Number(process.env.BRIDGE_COOLDOWN_SEC || 86400);
const fallbackSysUsd = () => Number(process.env.BRIDGE_FALLBACK_DAILY_USD || 5);

let ensured = false;
export async function ensureBridgeSchema() {
  if (ensured) return;
  await dbExec(`
    CREATE TABLE IF NOT EXISTS bridge_burn_log (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      from_addr    TEXT NOT NULL,
      amount_units INTEGER NOT NULL,
      usd          REAL NOT NULL,
      tx_hash      TEXT,
      created_at   INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_bbl_from ON bridge_burn_log(from_addr, created_at);
    CREATE INDEX IF NOT EXISTS idx_bbl_created ON bridge_burn_log(created_at);
  `);
  ensured = true;
}

async function usd24h(fromAddr) {
  const since = Math.floor(Date.now() / 1000) - 86400;
  const row = fromAddr
    ? await dbGet(`SELECT COALESCE(SUM(usd),0) AS s FROM bridge_burn_log WHERE created_at > ? AND from_addr = ?`, [since, fromAddr])
    : await dbGet(`SELECT COALESCE(SUM(usd),0) AS s FROM bridge_burn_log WHERE created_at > ?`, [since]);
  return Number(row?.s || 0);
}

// Returns { ok:true, ... } to allow, or { ok:false, code, reason, ... } to block.
export async function checkBurn({ fromAddr, amountUnits }) {
  if (!on()) return { ok: true, bypass: true };
  await ensureBridgeSchema();
  const morm = unitsToMorm(amountUnits);
  const pr = await getPriceReserve();
  const usd = morm * Number(pr.usdPerMorm || 0.01);

  // cooldown
  const last = await dbGet(`SELECT created_at FROM bridge_burn_log WHERE from_addr = ? ORDER BY id DESC LIMIT 1`, [fromAddr]);
  if (last) {
    const dt = Math.floor(Date.now() / 1000) - Number(last.created_at);
    if (dt < cooldownSec()) {
      return { ok: false, code: 429, reason: `cooldown: wait ${cooldownSec() - dt}s before another cash-out`, usd };
    }
  }
  // system daily cap
  const sysCapUsd = pr.usdcReserve != null ? pr.usdcReserve * sysFrac() : fallbackSysUsd();
  const sysUsed = await usd24h(null);
  if (sysUsed + usd > sysCapUsd) {
    return { ok: false, code: 429, reason: 'system daily cash-out cap reached (price protection)',
             usd, sysUsed, sysCapUsd, priceSource: pr.source };
  }
  // per-account daily cap
  const acctUsed = await usd24h(fromAddr);
  if (acctUsed + usd > acctDailyUsd()) {
    return { ok: false, code: 429, reason: 'account daily cash-out cap reached',
             usd, acctUsed, acctCapUsd: acctDailyUsd() };
  }
  return { ok: true, usd, sysCapUsd, sysUsed, acctUsed, usdPerMorm: pr.usdPerMorm, priceSource: pr.source };
}

export async function recordBurn({ fromAddr, amountUnits, usd, txHash }) {
  try {
    await ensureBridgeSchema();
    await dbRun(
      `INSERT INTO bridge_burn_log (from_addr, amount_units, usd, tx_hash, created_at) VALUES (?, ?, ?, ?, ?)`,
      [fromAddr, Number(amountUnits) || 0, Number(usd) || 0, txHash || null, Math.floor(Date.now() / 1000)]
    );
  } catch { /* accounting is best-effort; never block a completed burn */ }
}
