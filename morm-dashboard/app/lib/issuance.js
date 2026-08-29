import { dbGet, dbRun } from '@/app/lib/db';

// システム全体の日次「新規発行」上限(MORM/24h)。sybil で register/faucet/lane-earn を無制限に
// 引かれ供給インフレするのを防ぐ backstop。register drip + faucet + lane-earn の発行を合算する
// (AD は funded escrow の再分配・bridge は別系なので除外)。0/未設定なら既定の保守値。
// ★値は経済判断: 運用に応じて MORM_DAILY_ISSUANCE_CAP で調整(0 で無制限)。
const DAILY_CAP = Number(process.env.MORM_DAILY_ISSUANCE_CAP ?? 10000);

let idxEnsured = false;
async function ensureIdx() {
  if (idxEnsured) return;
  try {
    await dbRun(`CREATE INDEX IF NOT EXISTS idx_morm_txs_kind_created ON morm_txs(kind, created_at)`);
  } catch { /* best-effort */ }
  idxEnsured = true;
}

// 直近24hの新規発行合計(MORM)。faucet(=register drip も kind='faucet') と lane-earn:* を合算。
export async function dailyIssued() {
  await ensureIdx();
  const r = await dbGet(
    `SELECT COALESCE(SUM(amount),0) AS total FROM morm_txs
       WHERE (kind = 'faucet' OR kind LIKE 'lane-earn%')
         AND created_at > datetime('now','-1 day')`, []);
  return Number(r?.total || 0);
}

// 追加発行 amount が日次上限内か。{ ok, used, cap, remaining, unlimited?, degraded? }
// DB 失敗時は degraded で通す(発行台帳は best-effort・新規ユーザーを全面ブロックしない)。
export async function issuanceAllowed(amount) {
  if (!(DAILY_CAP > 0)) return { ok: true, unlimited: true, used: 0, cap: 0 };
  let used;
  try {
    used = await dailyIssued();
  } catch {
    return { ok: true, degraded: true, used: 0, cap: DAILY_CAP };
  }
  const add = Number(amount || 0);
  const ok = used + add <= DAILY_CAP;
  return { ok, used, cap: DAILY_CAP, remaining: Math.max(0, DAILY_CAP - used) };
}
