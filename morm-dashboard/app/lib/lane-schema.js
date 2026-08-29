import { dbExec, dbRun, dbGet, dbAll } from '@/app/lib/db';

// Agent Lane schema — self-provisioning (CREATE TABLE IF NOT EXISTS), mirroring
// the wallet-schema pattern so no separate migration step is needed on Turso.
//   lane_content : one row per on-chain REGISTER_CONTENT an agent publishes.
//   lane_earn    : dedup ledger for signed earn-claims (view/serve/etc.).
let ensured = false;
export async function ensureLaneSchema() {
  if (ensured) return;
  await dbExec(`
    CREATE TABLE IF NOT EXISTS lane_content (
      content_id    TEXT PRIMARY KEY,
      creator       TEXT NOT NULL,
      root_hash     TEXT,
      generation_id TEXT,
      tx_hash       TEXT,
      media_ref     TEXT,
      caption       TEXT,
      created_at    TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_lane_content_creator ON lane_content(creator);
    CREATE INDEX IF NOT EXISTS idx_lane_content_created ON lane_content(created_at);
  `);
  await dbExec(`
    CREATE TABLE IF NOT EXISTS lane_earn (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      addr       TEXT NOT NULL,
      kind       TEXT NOT NULL,
      ref        TEXT NOT NULL,
      amount     INTEGER,
      tx_hash    TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      UNIQUE(addr, kind, ref)
    );
    CREATE INDEX IF NOT EXISTS idx_lane_earn_addr ON lane_earn(addr);
  `);
  ensured = true;
}

export async function recordLaneContent({ contentId, creator, rootHash, generationId, txHash, mediaRef, caption }) {
  await dbRun(
    `INSERT OR IGNORE INTO lane_content
       (content_id, creator, root_hash, generation_id, tx_hash, media_ref, caption)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [contentId, creator, rootHash || null, generationId || null, txHash || null,
     mediaRef || null, (caption || '').toString().slice(0, 500)]
  );
}

export async function laneFeed(limit = 50) {
  return dbAll(
    `SELECT content_id, creator, generation_id, tx_hash, media_ref, caption, created_at
       FROM lane_content ORDER BY created_at DESC, rowid DESC LIMIT ?`,
    [Math.max(1, Math.min(200, Number(limit) || 50))]
  );
}

export async function laneStats(addr) {
  const pub = await dbGet(`SELECT COUNT(*) AS n FROM lane_content WHERE creator = ?`, [addr]);
  const earn = await dbGet(`SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS total FROM lane_earn WHERE addr = ?`, [addr]);
  return {
    published: Number(pub?.n || 0),
    earnClaims: Number(earn?.n || 0),
    earnedUnits: Number(earn?.total || 0),
  };
}

// Reserve a (addr, kind, ref) earn slot atomically. Returns true if this call
// won the slot (first claim), false if it was already taken (replay/dup).
export async function reserveEarn({ addr, kind, ref }) {
  try {
    const r = await dbRun(
      `INSERT OR IGNORE INTO lane_earn (addr, kind, ref, amount) VALUES (?, ?, ?, 0)`,
      [addr, kind, ref]
    );
    // libsql returns rowsAffected; 0 means the UNIQUE row already existed.
    return Number(r?.rowsAffected ?? r?.changes ?? 0) > 0;
  } catch {
    return false;
  }
}

export async function finalizeEarn({ addr, kind, ref, amount, txHash }) {
  await dbRun(
    `UPDATE lane_earn SET amount = ?, tx_hash = ? WHERE addr = ? AND kind = ? AND ref = ?`,
    [Number(amount) || 0, txHash || null, addr, kind, ref]
  );
}

// ★送金失敗(未確認/ドロップ)時に予約(amount=0 の未確定行)を解放して ref を再試行可能に戻す。
//   amount>0(確定済)は削除しない=支払い済みの二重払いを防ぐ。
export async function releaseEarn({ addr, kind, ref }) {
  try {
    await dbRun(
      `DELETE FROM lane_earn WHERE addr = ? AND kind = ? AND ref = ? AND amount = 0`,
      [addr, kind, ref]
    );
  } catch { /* best-effort release */ }
}
