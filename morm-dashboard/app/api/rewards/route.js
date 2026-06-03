import { NextResponse } from 'next/server';
import { dbAll, dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';
export async function GET() {
  const snapshots = await dbAll(`
    SELECT ws.*, n.name as node_name
    FROM weekly_snapshots ws
    JOIN nodes n ON ws.node_id = n.id
    ORDER BY ws.created_at DESC
  `);
  return NextResponse.json({ snapshots });
}

export async function POST(request) {
  const { weekLabel } = await request.json();
  if (!weekLabel) return NextResponse.json({ error: 'weekLabel required' }, { status: 400 });

  const nodes = await dbAll('SELECT * FROM nodes WHERE wallet_address IS NOT NULL');

  const inserts = [];
  for (const n of nodes) {
    const mormAmount = Math.round(n.total_score * 0.1 * 100) / 100;
    await dbRun(`
      INSERT INTO weekly_snapshots (week_label, node_id, wallet_address, total_score, morm_amount, status)
      VALUES (?, ?, ?, ?, ?, 'pending')
    `, [weekLabel, n.id, n.wallet_address, n.total_score, mormAmount]);
    inserts.push({ nodeId: n.id, mormAmount });
  }

  return NextResponse.json({ message: `${inserts.length}件のスナップショットを作成`, inserts });
}
