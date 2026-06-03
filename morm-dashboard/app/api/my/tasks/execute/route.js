import { NextResponse } from 'next/server';
import { dbGet, dbRun } from '@/app/lib/db';
import { completeTaskSuccess } from '@/app/lib/task-complete';

export const dynamic = 'force-dynamic';

export async function POST(request) {
  try {
    const { address, node_id, task_id } = await request.json();
    if (!address || !node_id || !task_id) {
      return NextResponse.json({ error: 'address, node_id, task_id are required' }, { status: 400 });
    }

    // 1. Get task and node
    const task = await dbGet('SELECT * FROM tasks WHERE id = ?', [task_id]);
    if (!task) return NextResponse.json({ error: 'タスクが見つかりません' }, { status: 404 });

    const node = await dbGet(`
      SELECT n.* FROM nodes n
      LEFT JOIN wallets w ON n.id = w.node_id
      WHERE n.id = ? AND (LOWER(n.wallet_address) = LOWER(?) OR LOWER(w.address) = LOWER(?))
    `, [node_id, address, address]);
    if (!node) return NextResponse.json({ error: 'ノードが見つかりません' }, { status: 404 });

    // 2. Check credential
    if (task.requires_credential) {
      const cred = await dbGet(
        'SELECT id FROM credentials WHERE node_id = ? AND service = ?',
        [node_id, task.requires_credential]
      );
      if (!cred) {
        return NextResponse.json({ error: 'アカウント登録が必要です' }, { status: 400 });
      }
    }

    // 3. Check MORM balance
    const mormCost = Number(task.morm_cost) || 0;
    const mormBalance = Number(node.morm_balance) || 0;
    if (mormCost > 0 && mormBalance < mormCost) {
      return NextResponse.json({
        error: `MORM残高不足 (必要: ${mormCost} MORM, 残高: ${mormBalance.toFixed(2)} MORM)`
      }, { status: 400 });
    }

    // 4. Check cooldown (based on last successful run)
    const cooldown = Number(task.cooldown_hours) || 0;
    if (cooldown > 0) {
      const lastRun = await dbGet(
        `SELECT completed_at FROM task_runs WHERE task_id = ? AND node_id = ? AND status = 'success' ORDER BY completed_at DESC LIMIT 1`,
        [task_id, node_id]
      );
      if (lastRun && lastRun.completed_at) {
        const diff = (Date.now() - new Date(lastRun.completed_at).getTime()) / (1000 * 60 * 60);
        if (diff < cooldown) {
          return NextResponse.json({ error: `クールダウン中 (残り: ${Math.ceil(cooldown - diff)}h)` }, { status: 400 });
        }
      }
    }

    const hasCommand = task.command && String(task.command).trim().length > 0;

    // 5a. Command tasks: enqueue for the node agent to execute, do NOT award yet.
    if (hasCommand) {
      const pending = await dbGet(
        `SELECT id FROM task_runs WHERE task_id = ? AND node_id = ? AND status IN ('pending','running') LIMIT 1`,
        [task_id, node_id]
      );
      if (pending) {
        return NextResponse.json({ error: 'このタスクは既に実行待ち/実行中です' }, { status: 400 });
      }
      const res = await dbRun(
        `INSERT INTO task_runs (node_id, task_id, status, created_at) VALUES (?, ?, 'pending', datetime('now'))`,
        [node_id, task_id]
      );
      const runId = Number(res.lastInsertRowid ?? res.last_insert_rowid ?? 0);
      return NextResponse.json({ success: true, queued: true, run_id: runId, message: 'ノードエージェントの実行待ちに追加しました' });
    }

    // 5b. Commandless tasks: instant local completion (connection toggles etc.)
    await dbRun(
      `INSERT INTO task_runs (node_id, task_id, status, score_earned, created_at, completed_at) VALUES (?, ?, 'success', ?, datetime('now'), datetime('now'))`,
      [node_id, task_id, Number(task.score_value) || 0]
    );
    const summary = await completeTaskSuccess(node, task);
    return NextResponse.json({ success: true, queued: false, ...summary });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
