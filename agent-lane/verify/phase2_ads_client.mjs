// Phase 2-⑥ AD escrow verification (real HTTP + ephemeral L1).
// Proves: signed ad events accrue (deduped), settle pays earners ∝ weight at the
// CPM rate FROM the advertiser-funded budget (capped by remaining = redistribution,
// not emission), idempotent per epoch, and an over-budget campaign scales to fit.
import crypto from 'crypto';
import { addressFromPubkey, adEventMessage } from '../../morm-dashboard/app/lib/morm-address.js';

const BASE = process.env.BASE || 'http://127.0.0.1:3014';
const L1 = process.env.L1 || 'http://127.0.0.1:8908';
const ADMIN = process.env.ADMIN || 'testpass';
const RATE = Number(process.env.RATE || 1000);       // AD_UNIT_PER_WEIGHT
const CLICKW = Number(process.env.CLICKW || 20);      // AD_CLICK_WEIGHT

function keygen() {
  const seed = crypto.randomBytes(32);
  const priv = crypto.createPrivateKey({ key: Buffer.concat([Buffer.from('302e020100300506032b657004220420', 'hex'), seed]), format: 'der', type: 'pkcs8' });
  const spki = crypto.createPublicKey(priv).export({ format: 'der', type: 'spki' });
  return { priv, pub: spki.subarray(spki.length - 32) };
}
const signMsg = (priv, m) => crypto.sign(null, Buffer.from(m, 'utf8'), priv).toString('hex');
async function jpost(p, b) { const r = await fetch(BASE + p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return { status: r.status, body: await r.json().catch(() => ({})) }; }
async function l1bal(a) { try { return Number((await (await fetch(`${L1}/account/${a}`)).json()).balance || 0); } catch { return 0; } }
const hr = (t) => console.log('\n' + '='.repeat(64) + `\n${t}\n` + '='.repeat(64));
const assert = (c, m) => { if (!c) { console.error('ASSERT FAILED:', m); process.exit(1); } };
const sleep = (ms) => new Promise((s) => setTimeout(s, ms));

function earner() { const { priv, pub } = keygen(); return { priv, pubHex: pub.toString('hex'), addr: addressFromPubkey(pub) }; }
async function event(camp, e, kind, ref) {
  return jpost('/api/ads/event', { campaignId: camp, earner: e.addr, pubkey: e.pubHex, kind, ref, sig: signMsg(e.priv, adEventMessage(camp, e.addr, kind, ref)) });
}
async function waitBal(addr, want, base) {
  for (let i = 0; i < 25; i++) { const b = await l1bal(addr); if (b >= (base + want)) return b; await sleep(600); }
  return l1bal(addr);
}

async function main() {
  const A = earner(), B = earner();

  hr('1) FUND campaign c1 (advertiser deposit = 1000 MORM budget)');
  let r = await jpost('/api/admin/ad-campaign', { password: ADMIN, action: 'fund', campaignId: 'c1', advertiser: 'adv1', units: 1000000000, depositTx: '0xdep' });
  console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.campaign.funded_units === 1000000000, 'fund failed');

  hr('2) SIGNED ad events (A: 3 impressions, B: 1 impression + 1 click)');
  for (const ref of ['imp1', 'imp2', 'imp3']) { r = await event('c1', A, 'impression', ref); assert(r.status === 200, `A ${ref} failed: ${JSON.stringify(r.body)}`); }
  r = await event('c1', B, 'impression', 'impB1'); assert(r.status === 200, 'B impression failed');
  r = await event('c1', B, 'click', 'clkB1'); assert(r.status === 200 && r.body.weight === CLICKW, 'B click weight wrong');
  // dedup
  const dup = await event('c1', A, 'impression', 'imp1'); assert(dup.status === 409, 'dedup should reject repeat ref');
  console.log('events recorded; dedup 409 OK');

  const aW = 3, bW = 1 + CLICKW, totalW = aW + bW;   // 3, 21, 24
  const a0 = await l1bal(A.addr), b0 = await l1bal(B.addr);

  hr('3) SETTLE c1 epoch e1 -> CPM payout from budget, ∝ weight');
  r = await jpost('/api/admin/ad-campaign', { password: ADMIN, action: 'settle', campaignId: 'c1', epochLabel: 'e1' });
  console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.earners === 2, 'settle should pay 2 earners');
  const expA = aW * RATE, expB = bW * RATE, expSpent = totalW * RATE;
  const a1 = await waitBal(A.addr, expA, a0), b1 = await waitBal(B.addr, expB, b0);
  console.log(`A +${a1 - a0} (exp ${expA}) | B +${b1 - b0} (exp ${expB})`);
  assert(a1 - a0 === expA && b1 - b0 === expB, 'ad payout must be weight × rate');
  assert(r.body.spent === expSpent && r.body.remaining === 1000000000 - expSpent, 'campaign spent/remaining wrong');
  console.log(`=> spent ${r.body.spent} ≤ funded 1e9 (redistribution, no emission)  OK`);

  hr('4) IDEMPOTENCY (re-settle e1)');
  r = await jpost('/api/admin/ad-campaign', { password: ADMIN, action: 'settle', campaignId: 'c1', epochLabel: 'e1' });
  console.log(r.status, JSON.stringify(r.body));
  assert(r.body.earners === 0, 're-settle same epoch must pay nobody');

  hr('5) OVER-BUDGET campaign c2 (funded 5000, due 24000) -> scaled to fit');
  let fr = await jpost('/api/admin/ad-campaign', { password: ADMIN, action: 'fund', campaignId: 'c2', advertiser: 'adv2', units: 5000 });
  console.log('fund c2:', fr.status, JSON.stringify(fr.body));
  for (const ref of ['cx1', 'cx2', 'cx3']) { const er = await event('c2', A, 'impression', ref); assert(er.status === 200, `c2 A ${ref} failed: ${JSON.stringify(er.body)}`); }
  let er = await event('c2', B, 'impression', 'cy1'); assert(er.status === 200, `c2 B imp failed: ${JSON.stringify(er.body)}`);
  er = await event('c2', B, 'click', 'cy2'); assert(er.status === 200, `c2 B click failed: ${JSON.stringify(er.body)}`);
  const dry = await jpost('/api/admin/ad-campaign', { password: ADMIN, action: 'settle', campaignId: 'c2', epochLabel: 'e1', dryRun: true });
  console.log('dryRun:', JSON.stringify(dry.body));
  r = await jpost('/api/admin/ad-campaign', { password: ADMIN, action: 'settle', campaignId: 'c2', epochLabel: 'e1' });
  console.log(r.status, JSON.stringify(r.body));
  const st = await jpost('/api/admin/ad-campaign', { password: ADMIN, action: 'status', campaignId: 'c2' });
  const spent = Number(st.body.spent_units);
  assert(spent > 0 && spent <= 5000, `over-budget settle spent must be (0,5000], got ${spent}`);
  console.log(`=> c2 spent ${spent} ≤ funded 5000 (budget cap holds)  OK`);

  hr('6) AUTH'); r = await jpost('/api/admin/ad-campaign', { password: 'wrong', action: 'status', campaignId: 'c1' });
  assert(r.status === 401, 'bad password rejected'); console.log('unauthorized rejected');

  hr('PHASE 2-⑥ AD ESCROW PROVEN');
  console.log('advertiser-funded budget -> signed ad events -> CPM payout to earners,');
  console.log('capped by budget (redistribution, no emission), idempotent, signed+deduped.');
}
main().catch((e) => { console.error(e); process.exit(1); });
