// Phase 2-⑤ node-emission verification via the admin route.
// Proves: NODE allocation of B_day is split ∝ node score, paid on-chain,
// idempotent per epoch, and nonce-safe (serialized transferMorm all land).
const BASE = process.env.BASE || 'http://127.0.0.1:3013';
const L1 = process.env.L1 || 'http://127.0.0.1:8907';
const ADMIN = process.env.ADMIN || 'testpass';

async function jpost(p, b) { const r = await fetch(BASE + p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return { status: r.status, body: await r.json().catch(() => ({})) }; }
async function l1bal(addr) { try { const a = await (await fetch(`${L1}/account/${addr}`)).json(); return Number(a.balance || 0); } catch { return 0; } }
const hr = (t) => console.log('\n' + '='.repeat(64) + `\n${t}\n` + '='.repeat(64));
const assert = (c, m) => { if (!c) { console.error('ASSERT FAILED:', m); process.exit(1); } };
const sleep = (ms) => new Promise((s) => setTimeout(s, ms));

async function main() {
  const epoch = 'e-test-1';

  hr('1) DRY RUN (plan only)');
  let r = await jpost('/api/admin/emit-nodes', { password: ADMIN, epochLabel: epoch, dryRun: true });
  console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.dryRun, 'dryRun should succeed');
  const plan = r.body.plan;
  const budget = r.body.nodeBudgetUnits;
  assert(plan.length === 3, 'expected 3 nodes in plan');
  // expected shares: 10/30/60 of nodeBudget (=1000*0.30*1e6 = 300,000,000)
  assert(budget === 300000000, `node budget should be 300M units, got ${budget}`);
  const byId = Object.fromEntries(plan.map((p) => [p.node_id, p]));
  assert(byId.nodeA.units === 30000000 && byId.nodeB.units === 90000000 && byId.nodeC.units === 180000000, 'plan shares must be 10/30/60 split');
  const planSum = plan.reduce((s, p) => s + p.units, 0);
  assert(planSum === budget, 'plan units must sum to the node budget');
  console.log('=> plan: 30M/90M/180M = 300M budget (10/30/60)  OK');

  // record before-balances
  const before = {};
  for (const p of plan) before[p.node_id] = await l1bal(p.wallet);

  hr('2) REAL SETTLE');
  r = await jpost('/api/admin/emit-nodes', { password: ADMIN, epochLabel: epoch });
  console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.nodes === 3, 'should pay 3 nodes');
  assert(r.body.units === budget, 'total emitted must equal the node budget (no runaway)');

  hr('3) VERIFY ON-CHAIN (each node ∝ score, nonce-safe)');
  let emitted = 0;
  for (const p of plan) {
    let b1 = before[p.node_id];
    for (let i = 0; i < 20; i++) { b1 = await l1bal(p.wallet); if (b1 >= before[p.node_id] + p.units) break; await sleep(600); }
    const got = b1 - before[p.node_id];
    emitted += got;
    console.log(`${p.node_id} score=${p.score} got=${got} expected=${p.units}`);
    assert(got === p.units, `${p.node_id} payout mismatch (nonce collision?)`);
  }
  assert(emitted === budget, 'all node payouts must land (serialized transferMorm)');
  console.log(`=> Σ ${emitted} units = ${emitted / 1e6} MORM node budget, all landed  OK`);

  hr('4) IDEMPOTENCY (re-run same epoch)');
  r = await jpost('/api/admin/emit-nodes', { password: ADMIN, epochLabel: epoch });
  console.log(r.status, JSON.stringify(r.body));
  assert(r.body.nodes === 0, 're-run same epoch must pay nobody');

  hr('5) AUTH');
  r = await jpost('/api/admin/emit-nodes', { password: 'wrong', epochLabel: 'x' });
  assert(r.status === 401, 'bad password must be rejected');
  console.log('unauthorized correctly rejected');

  hr('PHASE 2-⑤ NODE EMISSION PROVEN');
  console.log('MORMNODE reward unified into the same budget-capped proportional model:');
  console.log('node budget split ∝ verified score, on-chain, idempotent, nonce-safe.');
}
main().catch((e) => { console.error(e); process.exit(1); });
