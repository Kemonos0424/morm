// MORM Shop UI — passkey-gated P2P commerce against the MORM Chain.
//
// Flow (mirrors MORM.md §6):
//   ① pick a listing (any accepted content_id on chain becomes a "product
//      preview video" — same data structure)
//   ② createOrder for that content (passkey-signed; treasury collects 1% fee)
//   ③ seller submits packing proof (we self-mint a packing video for the demo)
//   ④ buyer submits opening proof
//   ⑤ treasury finalizes — escrow releases to seller, status transitions
//
// To keep the demo self-contained, the *same* passkey identity plays both
// buyer and seller, and a small treasury helper at /api/treasury/finalize
// performs the final step. In production each role would have its own key.

import {
  ed, listIdentities, addressFromPubkey, signTx, signTxWithConfirm,
  hexToBytes, bytesToHex,
  combineShares,
} from '/static/morm-identity.js';

const GATEWAY = '';                // same origin (passkey-morm at 8801)
const MORM_RPC = 'http://127.0.0.1:8900';

const $ = id => document.getElementById(id);
const log = (msg, cls='info') => {
  const el = document.createElement('div');
  el.className = cls;
  el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  $('log').appendChild(el);
  $('log').scrollTop = $('log').scrollHeight;
};

let identity = null;
let mormSeed = null;        // briefly held during signing; wiped after each tx
let mormPub  = null;
let order = null;           // { id, content_id, value, status, packing_hash, opening_hash }
let camStream = null;       // MediaStream from getUserMedia
let recorder  = null;       // active MediaRecorder
let recChunks = [];         // accumulating Blob chunks


// --- camera plumbing ------------------------------------------------------
async function camStart() {
  try {
    camStream = await navigator.mediaDevices.getUserMedia({
      // mobile: prefer the back camera (env) for packing/opening shoots
      video: {
        width:  { ideal: 720 },
        height: { ideal: 540 },
        facingMode: { ideal: 'environment' },
      },
      audio: false,
    });
    const v = $('cam'); v.srcObject = camStream;
    $('cam-overlay').textContent = 'MORM camera · ready';
    $('cam-start').disabled = true;
    $('cam-stop').disabled = false;
  } catch (e) {
    log(`camera blocked: ${e.message}`, 'err');
  }
}
function camStop() {
  if (camStream) camStream.getTracks().forEach(t => t.stop());
  camStream = null;
  $('cam').srcObject = null;
  $('cam-overlay').textContent = 'MORM camera · idle';
  $('cam-start').disabled = false;
  $('cam-stop').disabled = true;
}

/** Record `seconds` of camera into a webm Blob. Returns the Blob. */
async function recordWebm(seconds = 4) {
  if (!camStream) {
    log('no camera — clicking Start camera for you', 'info');
    await camStart();
    if (!camStream) throw new Error('no camera stream');
    // some browsers need a beat after permission
    await new Promise(r => setTimeout(r, 400));
  }
  recChunks = [];
  const types = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'];
  const mime = types.find(t => MediaRecorder.isTypeSupported(t)) || 'video/webm';
  recorder = new MediaRecorder(camStream, { mimeType: mime });
  recorder.ondataavailable = e => { if (e.data.size) recChunks.push(e.data); };
  $('cam-overlay').textContent = `MORM camera · REC ${seconds}s`;
  await new Promise(res => {
    recorder.onstop = () => res();
    recorder.start();
    setTimeout(() => recorder.state === 'recording' && recorder.stop(), seconds * 1000);
  });
  $('cam-overlay').textContent = 'MORM camera · ready';
  return new Blob(recChunks, { type: mime });
}

/** POST a recorded webm to the gateway → encode → return proof_hash. */
async function uploadEvidence(role, blob) {
  const url = `${GATEWAY}/api/evidence/upload?role=${role}&order_id=${order.id}`;
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'video/webm' },
    body: blob,
  });
  const j = await r.json();
  if (!j.ok) throw new Error(`upload failed: ${j.error || r.status}`);
  return j;     // { proof_hash, block_hash, tamper:{...}, evidence_dir }
}


async function loadIdentity() {
  const ids = await listIdentities();
  identity = ids[0] || null;
  $('my-id').textContent = identity ? identity.address : '— no identity —';
  if (!identity) {
    log('no MORM identity. Open / to register a passkey first.', 'err');
  }
}

async function fetchListings() {
  const r = await fetch(`${MORM_RPC}/info`);
  const info = await r.json();
  // get every block and pull contents from state — easiest: ask the L1 for
  // the latest few blocks and read their tx payloads. Or just rely on the
  // edge node's /api/contents which lists accepted screenings. We use both:
  // first try L1 directly via a small helper endpoint.
  try {
    const e = await fetch('http://127.0.0.1:8787/api/contents');
    if (e.ok) {
      const j = await e.json();
      return j.contents || [];
    }
  } catch {}
  return [];
}

function renderListings(items) {
  const root = $('items');
  if (!items.length) {
    root.innerHTML = '<div style="color:var(--muted);font-size:12px">no accepted contents on the L1 / edge yet.</div>';
    return;
  }
  root.innerHTML = '';
  for (const c of items) {
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `
      <div>
        <div class="item-cid">0x${c.content_id}</div>
        <div class="item-creator">creator: ${c.creator_id}${c.generation_id ? ' · AI-issued' : ''}</div>
      </div>
      <button class="item-buy">Buy 100k MORM</button>
    `;
    div.querySelector('.item-buy').addEventListener('click',
      () => beginOrder(c).catch(e => log(e.message, 'err')));
    root.appendChild(div);
  }
}

function renderOrder() {
  const card = $('order-card');
  const steps = $('steps');
  const ctas = $('ctas');
  if (!order) {
    card.innerHTML = '<div style="color:var(--muted);font-size:12px">no order — pick an item to start.</div>';
    steps.innerHTML = '';
    ctas.innerHTML = '';
    return;
  }
  card.innerHTML = `
    <div class="panel-row">order_id = ${order.id.slice(0, 24)}…
content    = 0x${order.content_id.slice(0, 24)}…
value      = ${order.value} MORM (1% to treasury)
status     = ${statusLabel(order.status)}</div>`;

  const stepDefs = [
    { name: 'createOrder',   need: 1, key: 'created' },
    { name: 'seller packing proof',  need: 2, key: 'packing' },
    { name: 'buyer opening proof',   need: 3, key: 'opening' },
    { name: 'treasury finalize',     need: 4, key: 'finalize' },
  ];
  steps.innerHTML = stepDefs.map((d, i) => {
    const status = order.status >= d.need ? 'done'
                 : order.status === d.need - 1 && order._working === d.key ? 'fail'
                 : '';
    return `
      <div class="step">
        <div class="num ${status}">${i + 1}</div>
        <div>
          <div class="label">${d.name}</div>
          <div class="detail">${detailFor(d.key)}</div>
        </div>
      </div>`;
  }).join('');

  ctas.innerHTML = '';
  if (order.status === 2) {
    // Phase 24-UI: irreversible commits use the slider, per UI/UX 視覚設計書 §2
    addSlider('Slide → submit opening proof',
              () => doOpening().catch(e => log(e.message, 'err')));
  }
  if (order.status === 3) {
    addSlider('Slide → finalize VALID & release funds',
              () => doFinalize(true).catch(e => log(e.message, 'err')));
    addBtn('Finalize INVALID (slash demo)', () => doFinalize(false).catch(e => log(e.message, 'err')));
  }
  if (order.status >= 4) {
    addBtn('New order', () => { order = null; renderOrder(); });
  }
}

function addBtn(label, handler, primary=false) {
  const b = document.createElement('button');
  b.textContent = label;
  if (primary) b.classList.add('primary');
  b.addEventListener('click', handler);
  $('ctas').appendChild(b);
}

// Phase 24-UI: action-slider — drag the knob ≥80% of the track to commit.
// Spawns a fresh <div> each call so multiple sliders can stack.
function addSlider(label, handler) {
  const root = document.createElement('div');
  root.className = 'action-slider';
  root.style.flex = '1 1 100%';
  root.innerHTML = `
    <div class="as-fill"></div>
    <div class="as-track-label">${label}</div>
    <div class="as-knob" role="button" aria-label="${label}"></div>`;
  $('ctas').appendChild(root);

  const knob  = root.querySelector('.as-knob');
  const fill  = root.querySelector('.as-fill');
  const track = root;
  let dragging = false, startX = 0, knobX = 0, fired = false;

  function maxX() { return track.clientWidth - knob.clientWidth - 8; }
  function setX(x) {
    knobX = Math.max(0, Math.min(maxX(), x));
    knob.style.transform = `translateX(${knobX}px)`;
    fill.style.width = `${knobX + knob.clientWidth/2}px`;
    if (!fired && knobX / maxX() > 0.8) {
      fired = true;
      track.classList.add('fired');
      knob.style.transform = `translateX(${maxX()}px)`;
      fill.style.width = '100%';
      handler();
    }
  }
  function startDrag(e) {
    if (fired) return;
    dragging = true; knob.classList.add('dragging');
    startX = (e.touches ? e.touches[0].clientX : e.clientX) - knobX;
    e.preventDefault();
  }
  function moveDrag(e) {
    if (!dragging) return;
    const x = (e.touches ? e.touches[0].clientX : e.clientX) - startX;
    setX(x);
  }
  function endDrag() {
    if (!dragging) return;
    dragging = false; knob.classList.remove('dragging');
    if (!fired) setX(0);
  }
  knob.addEventListener('mousedown',  startDrag);
  knob.addEventListener('touchstart', startDrag, { passive: false });
  window.addEventListener('mousemove', moveDrag);
  window.addEventListener('touchmove', moveDrag, { passive: false });
  window.addEventListener('mouseup',   endDrag);
  window.addEventListener('touchend',  endDrag);
}

function detailFor(key) {
  if (!order) return '';
  if (key === 'created')  return order.status >= 1 ? `tx ${order.create_tx?.slice(0,16)}…` : 'pending';
  if (key === 'packing')  return order.packing_hash ? `proof ${order.packing_hash.slice(0,18)}…` : '—';
  if (key === 'opening')  return order.opening_hash ? `proof ${order.opening_hash.slice(0,18)}…` : '—';
  if (key === 'finalize') return order.status === 4 ? 'released to seller'
                              : order.status === 5 ? 'refunded + slashed' : '—';
  return '';
}

function statusLabel(s) {
  return ({1:'Created', 2:'PackingDone', 3:'OpeningDone', 4:'Finalized', 5:'Refunded'}[s] || `status=${s}`);
}

// --- key reconstruction helper (XOR 2-of-2 against the gateway) -----------
async function withSeed(fn) {
  const sh = await fetch(`${GATEWAY}/api/dev/share`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({credential_id: identity.credential_id}),
  }).then(r => r.json());
  const seed = combineShares(sh.server_share, identity.client_share);
  const pub = await ed.getPublicKeyAsync(seed);
  try {
    return await fn(seed, pub);
  } finally {
    seed.fill(0);
  }
}

async function l1Nonce(addr) {
  const r = await fetch(`${MORM_RPC}/account/${addr}`);
  const j = await r.json();
  return j.nonce;
}

async function relay(tx) {
  const r = await fetch(`${GATEWAY}/api/relay/morm-tx`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({tx}),
  });
  return r.json();
}

// --- order lifecycle ------------------------------------------------------
async function beginOrder(content) {
  if (!identity) { log('no identity — register first', 'err'); return; }
  log(`begin order for content 0x${content.content_id.slice(0,12)}…`);

  // ensure buyer has balance — use treasury helper to credit if necessary
  const me = await fetch(`${MORM_RPC}/account/${identity.address}`).then(r => r.json());
  if (me.balance < 100_000) {
    log(`balance ${me.balance} too low; requesting treasury credit…`, 'info');
    const cr = await fetch(`${GATEWAY}/api/treasury/credit`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({to: identity.address, amount: 200_000}),
    }).then(r => r.json());
    log(`credit: ${JSON.stringify(cr)}`, 'info');
    await new Promise(r => setTimeout(r, 1500));
  }

  const orderIdBytes = new Uint8Array(32);
  crypto.getRandomValues(orderIdBytes);
  const orderId = '0x' + bytesToHex(orderIdBytes);

  order = {
    id: orderId,
    content_id: content.content_id,
    value: 100_000,
    status: 0,
    create_tx: null,
    packing_hash: null,
    opening_hash: null,
    _working: 'created',
  };
  renderOrder();

  // tx 1: createOrder (buyer = me, seller = also me for the demo)
  await withSeed(async (seed, pub) => {
    const nonce = await l1Nonce(identity.address);
    // Phase 27f: confirm dialog before passkey signing.
    const tx = await signTxWithConfirm({
      kind: 2,         // CREATE_ORDER
      senderPub: pub, senderSeed: seed, nonce,
      payload: {
        order_id: orderId,
        content_id: '0x' + content.content_id,
        seller: identity.address,   // same identity acts as both for demo
        value: 100_000,
      },
    });
    if (!tx) { log('createOrder cancelled by user', 'err'); return; }
    const res = await relay(tx);
    if (!res.ok) throw new Error(`createOrder failed: ${JSON.stringify(res)}`);
    order.create_tx = res.morm_response?.tx_hash || '';
    log(`createOrder tx ${order.create_tx.slice(0,16)}…`, 'ok');
  });
  await new Promise(r => setTimeout(r, 1500));
  await refreshOrder();
  if (order.status >= 1) await doPacking();
}

async function refreshOrder() {
  if (!order) return;
  const r = await fetch(`${MORM_RPC}/order/${order.id}`);
  if (!r.ok) return;
  const o = await r.json();
  order.status = o.status;
  order.packing_hash = o.packing_hash;
  order.opening_hash = o.opening_hash;
  renderOrder();
}

async function recordAndProve(role) {
  log(`recording ${role} proof from camera (4s)…`);
  const blob = await recordWebm(4);
  log(`uploaded ${blob.size} bytes, encoding cells + watermark…`);
  const j = await uploadEvidence(role, blob);
  if (j.tamper?.tampered) {
    log(`AI verifier flagged ${role} as tampered: ${j.tamper.reason}`, 'err');
  }
  log(`${role} proof_hash = ${j.proof_hash.slice(0, 18)}…  block ${j.block_hash.slice(0, 14)}…`,
      j.tamper?.tampered ? 'err' : 'ok');
  return j.proof_hash;
}

async function doPacking() {
  log('seller submits packing proof');
  order._working = 'packing';
  renderOrder();
  let proof;
  try {
    proof = await recordAndProve('packing');
  } catch (e) {
    log(`camera path failed (${e.message}); falling back to random proof_hash`, 'err');
    proof = '0x' + bytesToHex(crypto.getRandomValues(new Uint8Array(32)));
  }
  await withSeed(async (seed, pub) => {
    const nonce = await l1Nonce(identity.address);
    // Phase 27f: confirm dialog before passkey signing.
    const tx = await signTxWithConfirm({
      kind: 3,         // SUBMIT_PROOF
      senderPub: pub, senderSeed: seed, nonce,
      payload: { order_id: order.id, role: 'packing', proof_hash: proof },
    });
    if (!tx) { log('packing cancelled by user', 'err'); return; }
    const res = await relay(tx);
    if (!res.ok) throw new Error(`packing failed: ${JSON.stringify(res)}`);
    log(`packing tx ${res.morm_response?.tx_hash?.slice(0,16)}…`, 'ok');
  });
  await new Promise(r => setTimeout(r, 1500));
  await refreshOrder();
}

async function doOpening() {
  log('buyer submits opening proof');
  order._working = 'opening';
  renderOrder();
  let proof;
  try {
    proof = await recordAndProve('opening');
  } catch (e) {
    log(`camera path failed (${e.message}); falling back to random proof_hash`, 'err');
    proof = '0x' + bytesToHex(crypto.getRandomValues(new Uint8Array(32)));
  }
  await withSeed(async (seed, pub) => {
    const nonce = await l1Nonce(identity.address);
    // Phase 27f: confirm dialog before passkey signing.
    const tx = await signTxWithConfirm({
      kind: 3,
      senderPub: pub, senderSeed: seed, nonce,
      payload: { order_id: order.id, role: 'opening', proof_hash: proof },
    });
    if (!tx) { log('opening cancelled by user', 'err'); return; }
    const res = await relay(tx);
    if (!res.ok) throw new Error(`opening failed: ${JSON.stringify(res)}`);
    log(`opening tx ${res.morm_response?.tx_hash?.slice(0,16)}…`, 'ok');
  });
  await new Promise(r => setTimeout(r, 1500));
  await refreshOrder();
}

async function doFinalize(valid) {
  log(`treasury finalize valid=${valid}`);
  order._working = 'finalize';
  renderOrder();
  const r = await fetch(`${GATEWAY}/api/treasury/finalize`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({order_id: order.id, valid}),
  });
  const j = await r.json();
  if (!j.ok) throw new Error(`finalize failed: ${JSON.stringify(j)}`);
  log(`finalize tx ${j.morm_response?.tx_hash?.slice(0,16)}…`, 'ok');
  await new Promise(r => setTimeout(r, 1500));
  await refreshOrder();
}

async function init() {
  await loadIdentity();
  const items = await fetchListings();
  renderListings(items);
  $('cam-start').addEventListener('click', () => camStart().catch(e => log(e.message, 'err')));
  $('cam-stop').addEventListener('click', camStop);
}

init().catch(e => log(e.message, 'err'));
