import { NextResponse } from 'next/server';
import { dbAll, dbGet, dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';
export async function GET() {
  const eligible = await dbAll(`
    SELECT * FROM nodes
    WHERE wallet_address IS NOT NULL AND total_score >= 50 AND gas_stipend_sent = 0
    ORDER BY total_score DESC
  `);
  return NextResponse.json({ eligible });
}

export async function POST(request) {
  const { nodeId } = await request.json();
  if (!nodeId) return NextResponse.json({ error: 'nodeId required' }, { status: 400 });

  const node = await dbGet('SELECT * FROM nodes WHERE id = ?', [nodeId]);
  if (!node) return NextResponse.json({ error: 'ノードが見つかりません' }, { status: 404 });
  if (!node.wallet_address) return NextResponse.json({ error: 'ウォレット未接続' }, { status: 400 });

  // Simulated gas stipend
  const txHash = `0xgas_${Date.now().toString(16)}`;
  await dbRun('UPDATE nodes SET gas_stipend_sent = 1, gas_stipend_tx = ? WHERE id = ?', [txHash, nodeId]);

  return NextResponse.json({ message: 'ガス代送信完了', txHash });
}
