import { NextResponse } from 'next/server';
import { dbAll, dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const messages = await dbAll(`
      SELECT m.*, n.name as node_name FROM messages m
      JOIN nodes n ON m.node_id = n.id
      ORDER BY m.created_at ASC
    `);

    // Get unread counts per node (user messages not read by admin)
    const unreadCounts = await dbAll(`
      SELECT node_id, COUNT(*) as unread FROM messages
      WHERE sender = 'user' AND read = 0
      GROUP BY node_id
    `);

    const unreadMap = {};
    for (const u of unreadCounts) {
      unreadMap[u.node_id] = Number(u.unread);
    }

    // Get distinct nodes that have messages
    const nodes = await dbAll(`
      SELECT DISTINCT n.id, n.name FROM messages m
      JOIN nodes n ON m.node_id = n.id
      ORDER BY n.name
    `);

    return NextResponse.json({ messages, nodes, unreadMap });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const { node_id, message } = await request.json();
    if (!node_id || !message) {
      return NextResponse.json({ error: 'node_id, message are required' }, { status: 400 });
    }

    await dbRun(
      `INSERT INTO messages (node_id, sender, message, created_at) VALUES (?, 'admin', ?, datetime('now'))`,
      [node_id, message]
    );

    // Mark user messages for this node as read
    await dbRun(
      `UPDATE messages SET read = 1 WHERE node_id = ? AND sender = 'user' AND read = 0`,
      [node_id]
    );

    return NextResponse.json({ success: true });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
