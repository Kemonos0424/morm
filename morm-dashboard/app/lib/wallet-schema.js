import { dbExec, dbRun } from '@/app/lib/db';

// Lazily ensure the walletless-account table exists. Idempotent and cheap
// (CREATE TABLE IF NOT EXISTS). Called at the top of the wallet API routes so
// the schema self-provisions on first use — no separate prod migration step,
// and it works against whichever Turso the deployment is wired to.
let ensured = false;
export async function ensureWalletSchema() {
  if (ensured) return;
  await dbExec(`
    CREATE TABLE IF NOT EXISTS morm_accounts (
      address         TEXT PRIMARY KEY,
      handle          TEXT UNIQUE,
      pubkey          TEXT NOT NULL,
      passkey_cred_id TEXT,
      faucet_tx       TEXT,
      faucet_status   TEXT DEFAULT 'pending',
      ip_hash         TEXT,
      created_at      TEXT DEFAULT (datetime('now')),
      updated_at      TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_morm_accounts_handle ON morm_accounts(handle);
    CREATE INDEX IF NOT EXISTS idx_morm_accounts_created ON morm_accounts(created_at);
  `);
  // Best-effort column add for the one-time test faucet claim (older rows).
  try { await dbRun(`ALTER TABLE morm_accounts ADD COLUMN faucet_claimed INTEGER DEFAULT 0`); } catch {}

  // Wallet-relevant tx index (every tx the dashboard relays: faucet, claim, and
  // user transfers). Powers per-account history without an L1 history endpoint.
  await dbExec(`
    CREATE TABLE IF NOT EXISTS morm_txs (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      tx_hash    TEXT,
      from_addr  TEXT,
      to_addr    TEXT,
      amount     INTEGER,
      kind       TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_morm_txs_from ON morm_txs(from_addr);
    CREATE INDEX IF NOT EXISTS idx_morm_txs_to ON morm_txs(to_addr);
  `);
  ensured = true;
}

// Record a wallet tx for history. Best-effort: never throws into the caller.
export async function recordTx({ txHash, from, to, amount, kind }) {
  try {
    await dbRun(
      `INSERT INTO morm_txs (tx_hash, from_addr, to_addr, amount, kind) VALUES (?, ?, ?, ?, ?)`,
      [txHash || null, from || null, to || null, Number(amount) || 0, kind || 'transfer']
    );
  } catch (e) { /* history is non-critical */ }
}
