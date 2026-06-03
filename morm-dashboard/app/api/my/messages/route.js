import { NextResponse } from 'next/server';
import { dbAll, dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const address = searchParams.get('address');
    if (!address) return NextResponse.json({ messages: [] });

    const messages = await dbAll(`
      SELECT m.*, n.name as node_name FROM messages m
      JOIN nodes n ON m.node_id = n.id
      LEFT JOIN wallets w ON n.id = w.node_id
      WHERE LOWER(n.wallet_address) = LOWER(?) OR LOWER(w.address) = LOWER(?)
      ORDER BY m.created_at ASC
    `, [address, address]);

    // Mark admin messages as read
    const nodeIds = [...new Set(messages.map(m => m.node_id))];
    for (const nid of nodeIds) {
      await dbRun(
        `UPDATE messages SET read = 1 WHERE node_id = ? AND sender = 'admin' AND read = 0`,
        [nid]
      );
    }

    return NextResponse.json({ messages });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const { address, node_id, message } = await request.json();
    if (!address || !node_id || !message) {
      return NextResponse.json({ error: 'address, node_id, message are required' }, { status: 400 });
    }

    await dbRun(
      `INSERT INTO messages (node_id, sender, message, created_at) VALUES (?, 'user', ?, datetime('now'))`,
      [node_id, message]
    );

    return NextResponse.json({ success: true });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
