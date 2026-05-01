// Wallet UI — Phase 27g/h/i policy manager.
//
// Renders the persisted localStorage policy state, lets the user edit
// per-app caps + kind whitelists, and exposes the 1-tap "Revoke all"
// button (27i). All policy enforcement lives in morm-policy.js; this
// file only shows / mutates the persisted state.

import { listIdentities } from '/static/morm-identity.js';
import {
  TX_KIND_NAMES, listPolicies, getPolicy, setPolicy,
  getSpentLast24h, revokeAll,
} from '/static/morm-policy.js';
import { t, mountLangToggle } from '/static/morm-i18n.js';
import { maybeShowFirstTimeGuide, mountHelpButton, STEPS } from '/static/morm-guide.js';

const GATEWAY = window.location.origin;
let MORM_RPC = 'http://127.0.0.1:8900';
async function _resolveRpc() {
  try {
    const r = await fetch(`${GATEWAY}/api/morm/info`);
    if (r.ok) {
      const j = await r.json();
      if (j.rpc) MORM_RPC = j.rpc;
    }
  } catch {}
}

const $ = id => document.getElementById(id);

// Apps we always show even if the user hasn't visited them — gives the
// user a complete view of every page that COULD spend from this wallet.
const KNOWN_APPS = ['shop', 'auth-morm', 'admin', 'player-hls', 'upload', 'wallet'];

// ---- identity / balance ------------------------------------------------
async function refreshIdentity() {
  let identity = null;
  try {
    const ids = await listIdentities();
    identity = ids[0] || null;
  } catch {}
  if (!identity) {
    $('ident-addr').textContent = t('common.identity_unset');
    $('addr-full').textContent  = t('wallet.no_identity');
    $('bal-full').textContent   = '—';
    $('nonce-full').textContent = '—';
    return;
  }
  $('ident-addr').textContent = identity.address;
  $('addr-full').textContent  = identity.address;
  try {
    const r = await fetch(`${MORM_RPC}/account/${identity.address}`);
    if (r.ok) {
      const a = await r.json();
      $('bal-full').textContent  = `${a.balance} MORM`;
      $('nonce-full').textContent = a.nonce;
    } else {
      $('bal-full').textContent = `— (RPC ${r.status})`;
    }
  } catch {
    $('bal-full').textContent = t('wallet.balance_unreach');
  }
}

// ---- policy table ------------------------------------------------------
function renderPolicies() {
  const tbody = $('policy-tbody');
  tbody.innerHTML = '';
  const stored = listPolicies();
  // Union of stored apps and KNOWN_APPS — known apps not yet visited
  // render with their default policy ("preview" mode).
  const apps = [...new Set([...Object.keys(stored), ...KNOWN_APPS])].sort();
  for (const appKey of apps) {
    const policy = getPolicy(appKey);  // lazy-seeds defaults
    const spent = getSpentLast24h(appKey);
    const cap   = policy.dailyCapMorm;
    const pct   = cap > 0 ? Math.min(100, (spent / cap) * 100) : 0;

    const tr = document.createElement('tr');

    const tdApp = document.createElement('td');
    tdApp.className = 'app';
    tdApp.textContent = appKey;
    if (policy.isDefault) {
      const b = document.createElement('span');
      b.className = 'badge-default'; b.textContent = t('wallet.fallback');
      tdApp.appendChild(b);
    }
    tr.appendChild(tdApp);

    const tdKinds = document.createElement('td');
    tdKinds.className = 'kinds';
    tdKinds.textContent = policy.allowedKinds
      .map(k => TX_KIND_NAMES[k] || `kind=${k}`).join(', ')
      || t('block.allowed_none');
    tr.appendChild(tdKinds);

    const tdCap = document.createElement('td');
    tdCap.className = 'cap';
    tdCap.innerHTML = cap > 0
      ? `<span class="spent">${spent}</span> / ${cap} MORM`
      : `<span style="color:#6a7a90">${t('wallet.no_spend')}</span>`;
    tr.appendChild(tdCap);

    const tdProg = document.createElement('td');
    tdProg.className = 'progress-cell';
    if (cap > 0) {
      const bar = document.createElement('div');
      bar.className = 'progress';
      const fill = document.createElement('div');
      fill.className = 'fill';
      fill.style.width = `${pct}%`;
      if (pct >= 100) fill.classList.add('over');
      else if (pct >= 80) fill.classList.add('high');
      bar.appendChild(fill);
      tdProg.appendChild(bar);
    }
    tr.appendChild(tdProg);

    const tdAct = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.className = 'ghost';
    editBtn.textContent = t('common.edit');
    editBtn.onclick = () => toggleEditor(appKey, tr);
    tdAct.appendChild(editBtn);
    tr.appendChild(tdAct);

    tbody.appendChild(tr);
  }
}

function toggleEditor(appKey, tr) {
  // collapse any open editor first
  document.querySelectorAll('.editor.on').forEach(e => {
    e.classList.remove('on');
    e.parentElement.remove();
  });
  // attach a new editor row beneath this row
  const editor = buildEditor(appKey);
  const wrap = document.createElement('tr');
  const td = document.createElement('td');
  td.colSpan = 5;
  td.appendChild(editor);
  wrap.appendChild(td);
  tr.parentElement.insertBefore(wrap, tr.nextSibling);
  editor.classList.add('on');
}

function buildEditor(appKey) {
  const policy = getPolicy(appKey);
  const editor = document.createElement('div');
  editor.className = 'editor';

  const lblCap = document.createElement('label');
  lblCap.textContent = t('wallet.editor.cap');
  const inpCap = document.createElement('input');
  inpCap.type = 'number'; inpCap.min = 0;
  inpCap.value = policy.dailyCapMorm;

  const lblKinds = document.createElement('label');
  lblKinds.textContent = t('wallet.editor.kinds');
  const grid = document.createElement('div');
  grid.className = 'kind-grid';
  const allKinds = Object.keys(TX_KIND_NAMES).map(Number).sort((a,b) => a - b);
  const checks = {};
  for (const k of allKinds) {
    const row = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = policy.allowedKinds.includes(k);
    checks[k] = cb;
    const txt = document.createElement('span');
    txt.textContent = `${k} ${TX_KIND_NAMES[k]}`;
    row.appendChild(cb); row.appendChild(txt);
    grid.appendChild(row);
  }

  const actions = document.createElement('div');
  actions.className = 'actions';
  const cancel = document.createElement('button');
  cancel.className = 'ghost'; cancel.textContent = t('common.cancel');
  cancel.onclick = () => { editor.parentElement.parentElement.remove(); };
  const save = document.createElement('button');
  save.className = 'primary'; save.textContent = t('common.save');
  save.onclick = () => {
    const newKinds = allKinds.filter(k => checks[k].checked);
    setPolicy(appKey, {
      allowedKinds: newKinds,
      dailyCapMorm: Math.max(0, Number(inpCap.value) || 0),
    });
    renderPolicies();
  };
  actions.appendChild(cancel); actions.appendChild(save);

  editor.appendChild(lblCap); editor.appendChild(inpCap);
  editor.appendChild(lblKinds); editor.appendChild(grid);
  editor.appendChild(actions);
  return editor;
}

// ---- 27i revocation ---------------------------------------------------
$('revoke-btn').addEventListener('click', () => {
  if (!confirm(t('wallet.revoke_confirm'))) return;
  revokeAll();
  $('revoke-status').textContent = t('wallet.revoke_done',
    { time: new Date().toLocaleTimeString() });
  renderPolicies();
});
$('refresh').addEventListener('click', renderPolicies);

// Re-render dynamic JS-built strings whenever the language toggle fires.
window.addEventListener('morm-lang-changed', () => {
  renderPolicies();
  refreshIdentity();
});

// ---- init -------------------------------------------------------------
(async function init() {
  // Mount language toggle + help (?) button into the topbar slots before
  // anything renders, so the auto-launched guide finds them in place.
  mountLangToggle($('lang-toggle'));
  mountHelpButton($('help-btn'), 'wallet', STEPS.wallet);
  await _resolveRpc();
  await refreshIdentity();
  setInterval(refreshIdentity, 10_000);
  renderPolicies();
  // refresh table every 5s so the spend column stays live
  setInterval(renderPolicies, 5000);
  // First-time onboarding — explains per-app caps, kind whitelists,
  // 1-tap revoke. Idempotent: localStorage marker prevents re-prompt
  // unless user resets via "show again" (?) button.
  maybeShowFirstTimeGuide('wallet', STEPS.wallet);
})();
