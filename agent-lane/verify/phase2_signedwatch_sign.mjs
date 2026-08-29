// Sign a "watch" envelope EXACTLY like morm-play/index.html does (same canon()
// + Ed25519 over canon(env)), then print the wire JSON. A Python verifier feeds
// this to play_server.verify_signed to prove JS canon == Python canonical (the
// view_by_other earning path depends on this cross-language signature match).
import crypto from 'crypto';
import { addressFromPubkey } from '../../morm-dashboard/app/lib/morm-address.js';

// canon() copied verbatim from index.html (line 329-330).
function canon(v) {
  if (v === null) return 'null';
  if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']';
  if (typeof v === 'object') return '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}';
  return JSON.stringify(v);
}
const hex = (b) => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');

const seed = crypto.randomBytes(32);
const priv = crypto.createPrivateKey({ key: Buffer.concat([Buffer.from('302e020100300506032b657004220420', 'hex'), seed]), format: 'der', type: 'pkcs8' });
const spki = crypto.createPublicKey(priv).export({ format: 'der', type: 'spki' });
const pub = spki.subarray(spki.length - 32);
const PUBHEX = pub.toString('hex');
const addr = addressFromPubkey(pub);

// same shape index.html sends for a signed watch beacon
const payload = { id: '0x' + crypto.randomBytes(8).toString('hex'), watched: 5, completed: true };
const nonce = Date.now() + '-' + Math.random().toString(36).slice(2, 6);
const env = { kind: 'watch', sender: PUBHEX, nonce, payload };
const sig = hex(crypto.sign(null, Buffer.from(canon(env), 'utf8'), priv));

process.stdout.write(JSON.stringify({ kind: 'watch', sender: PUBHEX, nonce, payload, sig, expected_addr: addr }));
