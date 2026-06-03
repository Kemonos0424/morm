import { NextResponse } from 'next/server';
import { dbGet, dbRun } from '@/app/lib/db';
import { completeTaskSuccess } from '@/app/lib/task-complete';

export const dynamic = 'force-dynamic';

// Node agent reports the result of a job it ran.
// Auth: node_id + agent_token. status: 'success' | 'failed'.
export async function POST(request) {
  try {
    const { node_id, token, run_id, status, output } = await request.json();
    if (!node_id || !token || !run_id || !status) {
      return NextResponse.json({ error: 'node_id, token, run_id, status are required' }, { status: 400 });
    }
    if (status !== 'success' && status !== 'failed') {
      return NextResponse.json({ error: "status must be 'success' or 'failed'" }, { status: 400 });
    }

    const node = await dbGet('SELECT * FROM nodes WHERE id = ?', [node_id]);
    if (!node || !node.agent_token || node.agent_token !== token) {
      return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
    }

    const run = await dbGet('SELECT * FROM task_runs WHERE id = ? AND node_id = ?', [run_id, node_id]);
    if (!run) return NextResponse.json({ error: 'run not found' }, { status: 404 });
    if (run.status !== 'running' && run.status !== 'pending') {
      return NextResponse.json({ error: `run already finalized (${run.status})` }, { status: 409 });
    }

    const task = await dbGet('SELECT * FROM tasks WHERE id = ?', [run.task_id]);
    if (!task) return NextResponse.json({ error: 'task not found' }, { status: 404 });

    const result = (output || '').toString().slice(0, 4000);

    if (status === 'failed') {
      await dbRun(
        `UPDATE task_runs SET status = 'failed', result = ?, score_earned = 0, completed_at = datetime('now') WHERE id = ?`,
        [result, run_id]
      );
      return NextResponse.json({ success: true, status: 'failed' });
    }

    // success: finalize run, then apply economic effects once.
    await dbRun(
      `UPDATE task_runs SET status = 'success', result = ?, score_earned = ?, completed_at = datetime('now') WHERE id = ?`,
      [result, Number(task.score_value) || 0, run_id]
    );
    const summary = await completeTaskSuccess(node, task);
    return NextResponse.json({ success: true, status: 'success', ...summary });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
