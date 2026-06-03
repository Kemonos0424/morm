import { NextResponse } from 'next/server';
import { dbAll, dbGet, dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

// Node agent polls this endpoint for work assigned to it.
// Auth: node_id + agent_token (per-node secret generated at provision time).
export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const nodeId = searchParams.get('node_id');
  const token = searchParams.get('token');
  if (!nodeId || !token) {
    return NextResponse.json({ error: 'node_id and token are required' }, { status: 400 });
  }

  const node = await dbGet('SELECT id, agent_token FROM nodes WHERE id = ?', [nodeId]);
  if (!node || !node.agent_token || node.agent_token !== token) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  // Polling counts as a heartbeat.
  await dbRun('UPDATE nodes SET status = ?, last_heartbeat = ? WHERE id = ?', ['online', new Date().toISOString(), nodeId]);

  const pending = await dbAll(
    `SELECT r.id AS run_id, r.task_id, t.command, t.timeout_sec
       FROM task_runs r JOIN tasks t ON r.task_id = t.id
      WHERE r.node_id = ? AND r.status = 'pending'
      ORDER BY r.id ASC`,
    [nodeId]
  );

  const jobs = [];
  for (const j of pending) {
    if (!j.command || !String(j.command).trim()) continue;
    await dbRun(
      `UPDATE task_runs SET status = 'running', started_at = datetime('now') WHERE id = ? AND status = 'pending'`,
      [j.run_id]
    );
    jobs.push({
      run_id: Number(j.run_id),
      task_id: j.task_id,
      command: j.command,
      timeout_sec: Number(j.timeout_sec) || 300,
    });
  }

  return NextResponse.json({ jobs });
}
