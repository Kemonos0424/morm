// Phase 1 verification client — drives the /api/lane/* routes over real HTTP
// against a locally-running Next dev server wired to an ephemeral L1.
// Proves: register (did:key) -> publish (signed kind1) -> feed -> me -> earn (signed).
import crypto from 'crypto';
import { addressFromPubkey, registerMessage, laneEarnMessage } from '../../morm-dashboard/app/lib/morm-address.js';

const BASE = process.env.BASE || 'http://127.0.0.1:3010';

// ---- ed25519 helpers (mirror morm-l1 crypto) -----------------------------
function keygen() {
  const seed = crypto.randomBytes(32);
  const priv = crypto.createPrivateKey({
    key: Buffer.concat([Buffer.from('302e020100300506032b657004220420', 'hex'), seed]),
    format: 'der', type: 'pkcs8',
  });
  const spki = crypto.createPublicKey(priv).export({ format: 'der', type: 'spki' });
  const pub = spki.subarray(spki.length - 32);
  return { priv, pub };
}
function signMsg(priv, msgStr) {
  return crypto.sign(null, Buffer.from(msgStr, 'utf8'), priv).toString('hex');
}
function canonicalize(o) {
  if (Array.isArray(o)) return o.map(canonicalize);
  if (o && typeof o === 'object') {
    const out = {}; for (const k of Object.keys(o).sort()) out[k] = canonicalize(o[k]); return out;
  }
  return o;
}
function signTx(priv, tx) {
  const body = canonicalize({ kind: tx.kind, sender: tx.sender, nonce: tx.nonce, payload: tx.payload });
  const msg = Buffer.from(JSON.stringify(body), 'utf8');
  return crypto.sign(null, msg, priv).toString('hex');
}
async function jget(path) {
  const r = await fetch(BASE + path); return { status: r.status, body: await r.json().catch(() => ({})) };
}
async function jpost(path, body) {
  const r = await fetch(BASE + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return { status: r.status, body: await r.json().catch(() => ({})) };
}
function hr(t) { console.log('\n' + '='.repeat(66) + `\n${t}\n` + '='.repeat(66)); }
function assert(c, m) { if (!c) { console.error('ASSERT FAILED:', m); process.exit(1); } }

async function main() {
  // agent identity
  const { priv, pub } = keygen();
  const pubHex = pub.toString('hex');
  const addr = addressFromPubkey(pub);

  hr('0) AGENT IDENTITY');
  console.log('addr  :', addr);
  console.log('pubkey:', pubHex);

  // 1) register (proof of key possession) — also drips faucet from treasury
  const rsig = signMsg(priv, registerMessage(addr));
  let r = await jpost('/api/wallet/register', { address: addr, pubkey: pubHex, sig: rsig });
  hr('1) REGISTER (did:key + faucet)'); console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.ok, 'register failed');

  // nonce from /api/lane/me
  let me = await jget(`/api/lane/me?addr=${addr}`);
  console.log('me after register:', JSON.stringify(me.body));
  const nonce = Number(me.body?.chain?.nonce || 0);

  // 2) publish (agent-signed REGISTER_CONTENT kind1)
  const cid = '0x' + crypto.randomBytes(16).toString('hex');
  const root = '0x' + crypto.randomBytes(32).toString('hex');
  const tx = { kind: 1, sender: pubHex, nonce, payload: { content_id: cid, root_hash: root, generation_id: null } };
  tx.signature = signTx(priv, tx);
  r = await jpost('/api/lane/publish', { tx, caption: 'phase1 test post', media_ref: 'hls://demo' });
  hr('2) PUBLISH (kind:1, agent-signed)'); console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.ok && r.body.creator === addr, 'publish failed / creator mismatch');
  console.log('=> on-chain content published, creator == agent  OK');

  // 3) feed
  r = await jget('/api/lane/feed?limit=10');
  hr('3) FEED'); console.log(r.status, 'count=', r.body.count);
  const mine = (r.body.items || []).find((it) => it.content_id === cid);
  assert(mine && mine.creator === addr, 'published content not in feed');
  console.log('=> our post is in the feed  OK:', JSON.stringify(mine));

  // 4) me (published count)
  me = await jget(`/api/lane/me?addr=${addr}`);
  hr('4) ME'); console.log(me.status, JSON.stringify(me.body));
  assert(me.body?.lane?.published >= 1, 'published count not reflected');

  const balBefore = Number(me.body?.chain?.balance || 0);

  // 5) earn (signed claim -> real treasury payout)
  const kind = 'view', ref = 'c' + cid.slice(2, 22);
  const esig = signMsg(priv, laneEarnMessage(addr, kind, ref));
  r = await jpost('/api/lane/earn', { addr, pubkey: pubHex, kind, ref, sig: esig });
  hr('5) EARN (signed claim -> kind:6 payout)'); console.log(r.status, JSON.stringify(r.body));
  assert(r.status === 200 && r.body.ok && r.body.txHash, 'earn failed');

  // replay must be rejected
  const dup = await jpost('/api/lane/earn', { addr, pubkey: pubHex, kind, ref, sig: esig });
  console.log('replay attempt:', dup.status, JSON.stringify(dup.body));
  assert(dup.status === 409, 'replay was NOT rejected');
  console.log('=> earn paid once, replay blocked  OK');

  // confirm balance rose on-chain
  let bal = 0;
  for (let i = 0; i < 20; i++) {
    me = await jget(`/api/lane/me?addr=${addr}`);
    bal = Number(me.body?.chain?.balance || 0);
    if (bal > balBefore) break;
    await new Promise((s) => setTimeout(s, 600));
  }
  hr('RESULT'); console.log('balance before earn:', balBefore, '-> after:', bal);
  assert(bal > balBefore, 'earn payout did not land on-chain');
  console.log('\nPHASE 1 LANE LOOP PROVEN OVER REAL HTTP  OK');
  console.log('register -> publish(kind1) -> feed -> me -> earn(kind6) all green.');
}
main().catch((e) => { console.error(e); process.exit(1); });
