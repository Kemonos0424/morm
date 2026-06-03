import { dbGet, dbRun } from '@/app/lib/db';

// Apply the economic effects of a successfully completed task to a node:
// award score, deduct MORM (m0r) cost, recompute pending/balance, toggle SNS connections.
// `node` and `task` are full DB rows. Returns a summary for the API response.
// Balance ledger columns: nodes.morm_balance / morm_pending / morm_spent, tasks.morm_cost.
export async function completeTaskSuccess(node, task) {
  const mormCost = Number(task.morm_cost) || 0;
  const scoreValue = Number(task.score_value) || 0;

  const newTaskScore = (Number(node.task_score) || 0) + scoreValue;
  const newTotalScore = (Number(node.base_score) || 0) + newTaskScore;
  const newMormPending = newTaskScore / 100.0;
  const newMormSpent = (Number(node.morm_spent) || 0) + mormCost;
  const newMormBalance = newMormPending - newMormSpent;

  await dbRun(
    'UPDATE nodes SET task_score = ?, total_score = ?, morm_pending = ?, morm_spent = ?, morm_balance = ? WHERE id = ?',
    [newTaskScore, newTotalScore, newMormPending, newMormSpent, newMormBalance, node.id]
  );

  if (task.id && task.id.startsWith('sns_connect_')) {
    const service = task.id.replace('sns_connect_', '');
    const serviceMap = { x: 'x', ig: 'instagram', tt: 'tiktok', fb: 'facebook', yt: 'youtube' };
    const svcName = serviceMap[service] || service;
    const existing = await dbGet('SELECT id FROM connections WHERE node_id = ? AND service = ?', [node.id, svcName]);
    if (existing) {
      await dbRun(`UPDATE connections SET status = 'connected', connected_at = datetime('now') WHERE id = ?`, [existing.id]);
    } else {
      await dbRun(`INSERT INTO connections (node_id, service, status, connected_at) VALUES (?, ?, 'connected', datetime('now'))`, [node.id, svcName]);
    }
  }

  return {
    score_earned: scoreValue,
    morm_spent: mormCost,
    new_balance: Math.max(0, newMormBalance).toFixed(2),
  };
}
