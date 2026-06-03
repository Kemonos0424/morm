import { NextResponse } from 'next/server';
import { dbAll } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const address = searchParams.get('address');
    if (!address) return NextResponse.json({ tasks: [], runs: [] });

    // All tasks (no enabled filter - use all tasks)
    const tasks = await dbAll('SELECT * FROM tasks ORDER BY category, id');

    // Task runs for nodes owned by this wallet
    const runs = await dbAll(`
      SELECT tr.*, t.name as task_name, t.category, n.name as node_name
      FROM task_runs tr
      JOIN tasks t ON tr.task_id = t.id
      JOIN nodes n ON tr.node_id = n.id
      LEFT JOIN wallets w ON n.id = w.node_id
      WHERE LOWER(n.wallet_address) = LOWER(?) OR LOWER(w.address) = LOWER(?)
      ORDER BY tr.completed_at DESC
      LIMIT 50
    `, [address, address]);

    return NextResponse.json({ tasks, runs });
  } catch (err) {
    return NextResponse.json({ error: err.message, tasks: [], runs: [] }, { status: 500 });
  }
}
