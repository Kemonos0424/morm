import { NextResponse } from 'next/server';
import {
  isHexPubkey, isValidMormAddress, addressFromPubkey,
  verifyEd25519, laneEarnMessage,
} from '@/app/lib/morm-address';
import { dbGet } from '@/app/lib/db';
import { mormL1Enabled, transferMorm } from '@/app/lib/morm-l1';
import { ensureWalletSchema, recordTx } from '@/app/lib/wallet-schema';
import {
  ensureLaneSchema, reserveEarn, finalizeEarn, releaseEarn,
} from '@/app/lib/lane-schema';

export const dynamic = 'force-dynamic';

// Agent Lane — EARN. The signed-claim payout primitive: an agent proves, with
// an Ed25519 signature over MORM-LANE-EARN:v1:<addr>:<kind>:<ref>, that it
// performed a rewardable action (view/serve/...), and the treasury pays it a
// small MORM reward via a real kind:6 TRANSFER. Sybil/replay bounds for Phase 1:
//   • addr must be a REGISTERED account (morm_accounts)          — 1 passkey/DID
//   • (addr, kind, ref) is UNIQUE → each ref pays at most once   — no replay
//   • reward is a small fixed amount                             — bounded cost
// The POLICY of what counts as a valid (kind, ref) — views by others, verified
// serve-proofs, ad impressions — is Phase 2. This route proves the payout rail.
const LANE_EARN_MORM = Number(process.env.MORM_LANE_EARN || 1);
const ALLOWED_KINDS = new Set(['view', 'serve', 'ad']); // extend in Phase 2
const REF_RE = /^[A-Za-z0-9:_-]{3,128}$/;

function cors() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
  };
}

export async function OPTIONS() {
  return new Response(null, { status: 204, headers: cors() });
}

export async function POST(request) {
  const headers = cors();
  try {
    const { addr, pubkey, kind, ref, sig } = await request.json().catch(() => ({}));

    if (!isValidMormAddress(addr)) {
      return NextResponse.json({ error: 'invalid m0r addr' }, { status: 400, headers });
    }
    if (!isHexPubkey(pubkey) || addressFromPubkey(Buffer.from(pubkey, 'hex')) !== addr) {
      return NextResponse.json({ error: 'pubkey does not match addr' }, { status: 400, headers });
    }
    if (!ALLOWED_KINDS.has(kind)) {
      return NextResponse.json({ error: `kind must be one of ${[...ALLOWED_KINDS].join(', ')}` }, { status: 400, headers });
    }
    if (!REF_RE.test(ref || '')) {
      return NextResponse.json({ error: 'ref must be 3-128 chars [A-Za-z0-9:_-]' }, { status: 400, headers });
    }
    if (typeof sig !== 'string' || !verifyEd25519(pubkey, laneEarnMessage(addr, kind, ref), sig)) {
      return NextResponse.json({ error: 'invalid earn signature' }, { status: 401, headers });
    }

    await ensureWalletSchema();
    await ensureLaneSchema();

    // Must be a registered account (1 passkey/DID) — the sybil floor.
    const acct = await dbGet('SELECT address FROM morm_accounts WHERE address = ?', [addr]);
    if (!acct) {
      return NextResponse.json({ error: 'addr not registered (register first)' }, { status: 404, headers });
    }

    // Per-account daily cap. lane earn is a per-claim treasury payout with only
    // dedup on (addr,kind,ref) and NO on-chain ref-validity check, so it is
    // farmable by inventing refs. The real earning paths are the budget-capped
    // tracks (view_by_other / node emission / AD). Keep this bounded and small.
    const CAP = Number(process.env.MORM_LANE_EARN_DAILY_CAP || 10);
    if (CAP <= 0) {
      return NextResponse.json({ error: 'lane earn disabled' }, { status: 403, headers });
    }
    const used = await dbGet(
      `SELECT COUNT(*) AS n FROM lane_earn WHERE addr = ? AND created_at > datetime('now','-1 day')`, [addr]);
    if (Number(used?.n || 0) >= CAP) {
      return NextResponse.json({ error: 'daily earn cap reached', cap: CAP }, { status: 429, headers });
    }

    // Atomically reserve the (addr, kind, ref) slot; false = already claimed.
    const won = await reserveEarn({ addr, kind, ref });
    if (!won) {
      return NextResponse.json({ error: 'already claimed for this ref', duplicate: true }, { status: 409, headers });
    }

    if (!mormL1Enabled()) {
      await releaseEarn({ addr, kind, ref });  // 予約だけ残して未払いにしない
      return NextResponse.json({ error: 'L1 payout not available' }, { status: 503, headers });
    }

    // ★送金失敗(未確認/ドロップ)時は予約を解放し ref を再試行可能に戻す(未払いで恒久 unclaimable にしない)。
    let r;
    try {
      r = await transferMorm({ to: addr, mormAmount: LANE_EARN_MORM });
    } catch (e) {
      await releaseEarn({ addr, kind, ref });
      return NextResponse.json({ error: 'payout not confirmed, retry', detail: e.message }, { status: 502, headers });
    }
    await finalizeEarn({ addr, kind, ref, amount: LANE_EARN_MORM, txHash: r.txHash });
    await recordTx({ txHash: r.txHash, from: process.env.MORM_TREASURY_ADDRESS, to: addr, amount: LANE_EARN_MORM, kind: `lane-earn:${kind}` });

    return NextResponse.json({ ok: true, addr, kind, ref, amount: LANE_EARN_MORM, txHash: r.txHash }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}
