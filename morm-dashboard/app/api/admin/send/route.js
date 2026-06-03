import { NextResponse } from 'next/server';
import { dbRun } from '@/app/lib/db';
import { mormL1Enabled, transferMorm } from '@/app/lib/morm-l1';

export const dynamic = 'force-dynamic';
export async function POST(request) {
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
