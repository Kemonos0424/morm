// Phase 2 unit-system verification. Runs against a dev server started with
// MORM_BASE_UNITS_PER_MORM=1000000 (µMORM). Proves:
//   • MORM->units->MORM is consistent at the money boundaries
//   • sub-MORM rewards (0.002 MORM) are representable on-chain (= 2000 units)
//   • displayed balanceMorm matches the raw integer base units / base
import crypto from 'crypto';
import { addressFromPubkey, registerMessage, laneEarnMessage } from '../../morm-dashboard/app/lib/morm-address.js';

const BASE = process.env.BASE || 'http://127.0.0.1:3011';
const EXPECT_BASE = Number(process.env.EXPECT_BASE || 1000000);
const FAUCET_MORM = Number(process.env.EXPECT_FAUCET || 5);
const EARN_MORM = Number(process.env.EXPECT_EARN || 0.002);

function keygen() {
  const seed = crypto.randomBytes(32);
  const priv = crypto.createPrivateKey({ key: Buffer.concat([Buffer.from('302e020100300506032b657004220420', 'hex'), seed]), format: 'der', type: 'pkcs8' });
  const spki = crypto.createPublicKey(priv).export({ format: 'der', type: 'spki' });
  return { priv, pub: spki.subarray(spki.length - 32) };
}
const signMsg = (priv, m) => crypto.sign(null, Buffer.from(m, 'utf8'), priv).toString('hex');
async function jget(p) { const r = await fetch(BASE + p); return { status: r.status, body: await r.json().catch(() => ({})) }; }
async function jpost(p, b) { const r = await fetch(BASE + p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return { status: r.status, body: await r.json().catch(() => ({})) }; }
const hr = (t) => console.log('\n' + '='.repeat(64) + `\n${t}\n` + '='.repeat(64));
const assert = (c, m) => { if (!c) { console.error('ASSERT FAILED:', m); process.exit(1); } };
const sleep = (ms) => new Promise((s) => setTimeout(s, ms));

async function pollBalanceUnits(addr, min, timeout = 25000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const me = await jget(`/api/lane/me?addr=${addr}`);
    const u = Number(me.body?.chain?.balance ?? -1);
    if (u >= min) return me.body;
    await sleep(600);
  }
  return (await jget(`/api/lane/me?addr=${addr}`)).body;
}

async function main() {
  const { priv, pub } = keygen();
  const pubHex = pub.toString('hex');
  const addr = addressFromPubkey(pub);
  hr('0) AGENT'); console.log('addr:', addr, '| base target:', EXPECT_BASE);

  // register (faucet drips FAUCET_MORM at base=1e6 -> FAUCET_MORM*1e6 units)
  let r = await jpost('/api/wallet/register', { address: addr, pubkey: pubHex, sig: signMsg(priv, registerMessage(addr)) });
  hr('1) REGISTER + faucet'); console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.ok, 'register failed');

  // wait for faucet to land, then check unit math
  const faucetUnits = Math.round(FAUCET_MORM * EXPECT_BASE);
  let me = await pollBalanceUnits(addr, faucetUnits);
  hr('2) UNIT MATH after faucet'); console.log(JSON.stringify(me));
  assert(Number(me.baseUnitsPerMorm) === EXPECT_BASE, `baseUnitsPerMorm should be ${EXPECT_BASE}`);
  assert(Number(me.chain.balance) === faucetUnits, `raw units should be ${faucetUnits} (=${FAUCET_MORM} MORM * ${EXPECT_BASE})`);
  assert(Math.abs(Number(me.chain.balanceMorm) - FAUCET_MORM) < 1e-9, `balanceMorm should display ${FAUCET_MORM}`);
  console.log(`=> ${FAUCET_MORM} MORM == ${faucetUnits} units, displayed back as ${me.chain.balanceMorm} MORM  OK`);

  const before = Number(me.chain.balance);

  // sub-MORM earn: EARN_MORM (0.002) -> EARN_MORM*1e6 = 2000 units
  const kind = 'view', ref = 'unit' + crypto.randomBytes(6).toString('hex');
  r = await jpost('/api/lane/earn', { addr, pubkey: pubHex, kind, ref, sig: signMsg(priv, laneEarnMessage(addr, kind, ref)) });
  hr('3) SUB-MORM EARN (0.002 MORM)'); console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.ok, 'earn failed');

  const earnUnits = Math.round(EARN_MORM * EXPECT_BASE);
  me = await pollBalanceUnits(addr, before + earnUnits);
  const after = Number(me.chain.balance);
  hr('RESULT');
  console.log(`units: ${before} -> ${after} (delta ${after - before}, expected ${earnUnits})`);
  console.log(`balanceMorm now: ${me.chain.balanceMorm} (expected ${FAUCET_MORM + EARN_MORM})`);
  assert(after - before === earnUnits, `sub-MORM earn should add exactly ${earnUnits} units`);
  assert(Math.abs(Number(me.chain.balanceMorm) - (FAUCET_MORM + EARN_MORM)) < 1e-9, 'balanceMorm mismatch');
  console.log('\nUNIT UNIFICATION PROVEN: sub-MORM (0.002) is representable on-chain and');
  console.log('MORM<->units is consistent at every boundary at base=1e6.  OK');
}
main().catch((e) => { console.error(e); process.exit(1); });
