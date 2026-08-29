// Phase 2-③ cash-out valve verification (real HTTP + ephemeral L1).
// Proves: a within-cap BRIDGE_BURN succeeds (balance drops on-chain), an
// immediate second burn is blocked by cooldown, and a burn that would exceed
// the system daily cap (0.5% of USDC reserve) is blocked. Valve is ON.
import crypto from 'crypto';
import { addressFromPubkey, registerMessage } from '../../morm-dashboard/app/lib/morm-address.js';

const BASE = process.env.BASE || 'http://127.0.0.1:3012';
const B = Number(process.env.EXPECT_BASE || 1000000); // µMORM

function keygen() {
  const seed = crypto.randomBytes(32);
  const priv = crypto.createPrivateKey({ key: Buffer.concat([Buffer.from('302e020100300506032b657004220420', 'hex'), seed]), format: 'der', type: 'pkcs8' });
  const spki = crypto.createPublicKey(priv).export({ format: 'der', type: 'spki' });
  return { priv, pub: spki.subarray(spki.length - 32) };
}
const signMsg = (priv, m) => crypto.sign(null, Buffer.from(m, 'utf8'), priv).toString('hex');
function canon(o) { if (Array.isArray(o)) return o.map(canon); if (o && typeof o === 'object') { const r = {}; for (const k of Object.keys(o).sort()) r[k] = canon(o[k]); return r; } return o; }
function signTx(priv, tx) { const body = canon({ kind: tx.kind, sender: tx.sender, nonce: tx.nonce, payload: tx.payload }); return crypto.sign(null, Buffer.from(JSON.stringify(body), 'utf8'), priv).toString('hex'); }
async function jget(p) { const r = await fetch(BASE + p); return { status: r.status, body: await r.json().catch(() => ({})) }; }
async function jpost(p, b) { const r = await fetch(BASE + p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return { status: r.status, body: await r.json().catch(() => ({})) }; }
const hr = (t) => console.log('\n' + '='.repeat(64) + `\n${t}\n` + '='.repeat(64));
const assert = (c, m) => { if (!c) { console.error('ASSERT FAILED:', m); process.exit(1); } };
const sleep = (ms) => new Promise((s) => setTimeout(s, ms));
const EVM = '0x' + '1'.repeat(40);

async function nonceOf(addr) { const me = await jget(`/api/lane/me?addr=${addr}`); return Number(me.body?.chain?.nonce || 0); }
async function balOf(addr) { const me = await jget(`/api/lane/me?addr=${addr}`); return Number(me.body?.chain?.balance || 0); }

async function burn(priv, pubHex, addr, mormAmount) {
  const amount = Math.round(mormAmount * B);
  const nonce = await nonceOf(addr);
  const tx = { kind: 21, sender: pubHex, nonce, payload: { amount, evm_recipient: EVM, token: 'MORM' } };
  tx.signature = signTx(priv, tx);
  return jpost('/api/wallet/bridge-burn', tx);
}

async function main() {
  const { priv, pub } = keygen();
  const pubHex = pub.toString('hex');
  const addr = addressFromPubkey(pub);
  hr('0) AGENT'); console.log(addr);

  const FUND = Number(process.env.EXPECT_FUND || 200); // single register drip (avoids nonce race)
  let r = await jpost('/api/wallet/register', { address: addr, pubkey: pubHex, sig: signMsg(priv, registerMessage(addr)) });
  hr('1) FUND (single register drip)'); console.log('register:', r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.ok, 'register failed');
  // wait for the FULL drip to land on-chain before burning
  let bal = 0; for (let i = 0; i < 40; i++) { bal = await balOf(addr); if (bal >= FUND * B) break; await sleep(500); }
  console.log('balance units:', bal, '=', bal / B, 'MORM');
  assert(bal >= FUND * B, `agent not fully funded (want ${FUND * B}, got ${bal})`);

  // A) within-cap burn -> OK, balance drops
  hr('2) BURN A (30 MORM, within caps) -> expect OK + balance drop');
  const before = await balOf(addr);
  r = await burn(priv, pubHex, addr, 30);
  console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.ok, 'within-cap burn should succeed');
  let after = before; for (let i = 0; i < 25; i++) { after = await balOf(addr); if (after <= before - 30 * B) break; await sleep(500); }
  console.log(`balance ${before} -> ${after} (drop ${before - after}, expected ${30 * B})`);
  assert(before - after === 30 * B, 'burn should reduce on-chain balance by the amount');

  // B) immediate second burn -> cooldown block
  hr('3) BURN B (immediate) -> expect 429 cooldown');
  r = await burn(priv, pubHex, addr, 5);
  console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 429 && /cooldown/i.test(r.body.error || ''), 'should be blocked by cooldown');

  // C) after cooldown, a burn that trips the system daily cap
  hr('4) wait cooldown, BURN C (20 MORM) -> expect 429 system cap');
  await sleep(3200);
  r = await burn(priv, pubHex, addr, 20);
  console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 429 && /system daily/i.test(r.body.error || ''), 'should be blocked by system daily cap');

  hr('PHASE 2-③ VALVE PROVEN');
  console.log('within-cap burn OK (balance dropped), cooldown blocks rapid re-burn,');
  console.log('system 0.5%/day cap blocks over-cash-out. Price reference protected.');
}
main().catch((e) => { console.error(e); process.exit(1); });
