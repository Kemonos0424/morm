import { NextResponse } from 'next/server';
import { dbRun } from '@/app/lib/db';
import { mormL1Enabled, transferMorm } from '@/app/lib/morm-l1';

export const dynamic = 'force-dynamic';

// このルートは live 時に treasury から任意アドレスへ実MORMを送金する（＝資金流出面）。
// 従来は無認証で、誰でもPOSTするだけでトレジャリーを抜けた。fail-closed で塞ぐ:
// x-admin-key == ADMIN_PASSWORD のときだけ許可。ADMIN_PASSWORD 未設定なら常に拒否。
function adminAuthed(request) {
  const key = (request.headers.get('x-admin-key') || request.headers.get('x-admin-password') || '').trim();
  const expect = (process.env.ADMIN_PASSWORD || '').trim();
  if (!expect) return false;   // 未設定＝機能無効（既定 '1234' は撤廃）
  return key === expect;
}

export async function POST(request) {
  if (!adminAuthed(request)) {
    return NextResponse.json({ error: 'unauthorized (set ADMIN_PASSWORD and send x-admin-key)' }, { status: 401 });
  }
  const { recipients } = await request.json();
  if (!recipients || !Array.isArray(recipients) || recipients.length === 0) {
    return NextResponse.json({ error: 'recipients required' }, { status: 400 });
  }

  const week = `W${new Date().toISOString().slice(0, 10)}`;
  const live = mormL1Enabled();
  const results = [];

  for (const r of recipients) {
    try {
      let txHash;
      if (live) {
        // Real m0r transfer: signs a TRANSFER tx with the treasury key and
        // submits it to the MORM L1 node RPC (see app/lib/morm-l1.js and
        // ../morm-l1: tx.py TRANSFER / rpc.py POST /tx).
        const res = await transferMorm({ to: r.address, mormAmount: r.amount });
        txHash = res.txHash;
      } else {
        // Simulation fallback (no MORM_L1_RPC_URL / MORM_TREASURY_SEED set):
        // synthesize a plausible m0r-prefixed hash so the dashboard flow works
        // without a live chain. Status is still recorded as 'sent'.
        txHash = `m0r${Date.now().toString(16)}${Math.random().toString(16).slice(2, 10)}`;
      }

      await dbRun(`
        INSERT INTO weekly_snapshots (week_label, node_id, wallet_address, total_score, morm_amount, tx_hash, status)
        VALUES (?, ?, ?, ?, ?, ?, 'sent')
      `, [week, r.nodeId, r.address, 0, r.amount, txHash]);

      results.push({ address: r.address, amount: r.amount, txHash, status: 'sent', mode: live ? 'l1' : 'sim' });
    } catch (e) {
      results.push({ address: r.address, amount: r.amount, status: 'failed', error: e.message });
    }
  }

  const sent = results.filter(r => r.status === 'sent').length;
  return NextResponse.json({
    message: `${sent}/${recipients.length} 送信完了${live ? ' (MORM L1)' : ' (シミュレーション)'}`,
    mode: live ? 'l1' : 'sim',
    results,
  });
}
