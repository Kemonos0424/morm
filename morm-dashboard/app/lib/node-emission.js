import { dbExec, dbRun, dbGet, dbAll } from '@/app/lib/db';
import { baseUnitsPerMorm, unitsToMorm } from '@/app/lib/morm-units';
import { transferMorm, mormL1Enabled } from '@/app/lib/morm-l1';
import { ensureWalletSchema, recordTx } from '@/app/lib/wallet-schema';

// Phase 2-⑤ — MORMNODE reward, UNIFIED with the Play engagement track under the
// SAME budget-capped proportional model. A node's verified work accrues as
// nodes.total_score (base_score = capacity/provision, task_score = completed,
// verified task_runs — this is where serve/edge belongs, since it is verified
// rather than self-reported). Each epoch the NODE allocation of B_day is split
// across nodes ∝ score:
//     payout_node(units) = floor(nodeBudgetUnits × score / Σscore), capped.
// Shared budget contract (same envs the Play settler reads):
//   B_EPOCH_MORM, EPOCH_ACCT_CAP_FRAC, MORM_BASE_UNITS_PER_MORM
//   SPLIT_NODE = node allocation fraction of B_day (default 0.30 per §16)
// Flag-gated by the caller (admin route); the legacy /api/rewards route is left
// untouched, so default behavior is unchanged.
const bEpochMorm = () => Number(process.env.B_EPOCH_MORM || 5000);
const splitNode = () => Number(process.env.SPLIT_NODE || 0.30);
const capFrac = () => Number(process.env.EPOCH_ACCT_CAP_FRAC || 0.005);

let ensured = false;
export async function ensureNodeEmissionSchema() {
  if (ensured) return;
  await dbExec(`
    CREATE TABLE IF NOT EXISTS node_emissions (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      epoch_label   TEXT NOT NULL,
      node_id       TEXT NOT NULL,
      wallet_address TEXT,
      score         INTEGER,
      units         INTEGER,
      tx_hash       TEXT,
      status        TEXT DEFAULT 'pending',
      created_at    INTEGER NOT NULL,
      UNIQUE(epoch_label, node_id)
    );
    CREATE INDEX IF NOT EXISTS idx_node_emissions_epoch ON node_emissions(epoch_label);
  `);
  ensured = true;
}

// Compute the proportional plan (no payment). Pure read; used by dryRun + tests.
export async function planNodeEmission() {
  const nodes = await dbAll(
    `SELECT id, wallet_address, total_score FROM nodes
      WHERE wallet_address IS NOT NULL AND wallet_address != '' AND total_score > 0`
  );
  const totalScore = nodes.reduce((s, n) => s + Number(n.total_score || 0), 0);
  const nodeBudgetUnits = Math.round(bEpochMorm() * splitNode() * baseUnitsPerMorm());
  const capUnits = Math.floor(nodeBudgetUnits * capFrac());
  const plan = [];
  if (totalScore > 0) {
    for (const n of nodes) {
      let share = Math.floor((nodeBudgetUnits * Number(n.total_score)) / totalScore);
      if (capUnits > 0 && share > capUnits) share = capUnits; // anti-whale
      if (share >= 1) plan.push({ node_id: n.id, wallet: n.wallet_address, score: Number(n.total_score), units: share });
    }
  }
  return { totalScore, nodeBudgetUnits, capUnits, plan };
}

// Settle one epoch. Idempotent per (epoch_label, node_id): a row is reserved
// before payment, so re-running the same epoch never double-pays.
export async function settleNodesProportional({ epochLabel, dryRun = false }) {
  if (!epochLabel) throw new Error('epochLabel required');
  await ensureNodeEmissionSchema();
  const { totalScore, nodeBudgetUnits, plan } = await planNodeEmission();
  if (dryRun) return { ok: true, dryRun: true, epochLabel, totalScore, nodeBudgetUnits, plan };
  if (!plan.length) return { ok: true, epochLabel, nodes: 0, units: 0, totalScore, nodeBudgetUnits };
  if (!mormL1Enabled()) return { error: 'L1 payout not available' };
  // Node rewards must show up in the same wallet history the user sees on
  // account.html (/api/wallet/history reads morm_txs). Every other payout path
  // (faucet, transfer, bridge) calls recordTx; node emissions did not, so a
  // paid node's balance moved silently. Ensure the tx-index table exists.
  await ensureWalletSchema();

  const now = Math.floor(Date.now() / 1000);
  let paid = 0, unitsTotal = 0;
  for (const p of plan) {
    const done = await dbGet(
      `SELECT status FROM node_emissions WHERE epoch_label = ? AND node_id = ?`, [epochLabel, p.node_id]);
    if (done && done.status === 'sent') continue; // already paid this epoch
    if (!done) {
      await dbRun(
        `INSERT OR IGNORE INTO node_emissions (epoch_label,node_id,wallet_address,score,units,status,created_at)
         VALUES (?,?,?,?,?, 'pending', ?)`,
        [epochLabel, p.node_id, p.wallet, p.score, p.units, now]);
    }
    try {
      const mormAmount = unitsToMorm(p.units);
      const r = await transferMorm({ to: p.wallet, mormAmount });
      await dbRun(`UPDATE node_emissions SET tx_hash = ?, status = 'sent' WHERE epoch_label = ? AND node_id = ?`,
        [r.txHash, epochLabel, p.node_id]);
      // Index the payout so it appears in the recipient's wallet history.
      await recordTx({ txHash: r.txHash, from: process.env.MORM_TREASURY_ADDRESS, to: p.wallet, amount: mormAmount, kind: 'node-reward' });
      paid++; unitsTotal += p.units;
    } catch (e) {
      await dbRun(`UPDATE node_emissions SET status = 'failed' WHERE epoch_label = ? AND node_id = ?`,
        [epochLabel, p.node_id]);
    }
  }
  return { ok: true, epochLabel, nodes: paid, units: unitsTotal, totalScore, nodeBudgetUnits };
}
