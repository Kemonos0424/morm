import { NextResponse } from 'next/server';
import { dbGet, dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function POST(request) {
  try {
    const body = await request.json();
    const address = body.address || body.wallet_address;
    const nodeId = body.node_id || body.nodeId;

    if (!address || !nodeId) return NextResponse.json({ error: 'addressとnode_idが必要です' }, { status: 400 });

    const node = await dbGet('SELECT * FROM nodes WHERE id = ?', [nodeId]);
    if (!node) return NextResponse.json({ error: 'ノードが見つかりません (ID: ' + nodeId + ')' }, { status: 404 });

    if (node.wallet_address && node.wallet_address.toLowerCase() !== address.toLowerCase()) {
      return NextResponse.json({ error: 'このノードは他のウォレットに紐づいています' }, { status: 400 });
    }

    // Update nodes table
    await dbRun('UPDATE nodes SET wallet_address = ? WHERE id = ?', [address.toLowerCase(), nodeId]);

    // Upsert wallets table
    const existing = await dbGet('SELECT * FROM wallets WHERE node_id = ?', [nodeId]);
    if (existing) {
      await dbRun('UPDATE wallets SET address = ? WHERE node_id = ?', [address.toLowerCase(), nodeId]);
    } else {
      await dbRun('INSERT INTO wallets (node_id, address) VALUES (?, ?)', [nodeId, address.toLowerCase()]);
    }

    return NextResponse.json({ success: true, nodeName: node.name });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
