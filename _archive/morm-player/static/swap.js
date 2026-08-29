// MORM Bridge UI — Phase 28a.
//
// Two-tab page that drives the EVM↔MORM swap via the existing
// MORMBridge contract + relayer.py. The bridge core (Solidity, L1 tx
// kinds 20/21, relayer, forge tests) was completed in Phase 12/13;
// this page only adds the browser entry-points.
//
//   Lock side  (ETH → MORM mint):
//     - MetaMask is REQUIRED — passkeys can't sign Ethereum tx, and
//       the lock must originate from an EOA that holds ETH on the
//       EVM. Falls back to a copy-pasteable `cast send` command if
//       window.ethereum isn't injected.
//     - calldata = selector(lock(bytes20)) || left-padded mormAddr
//     - we wait for the receipt and then poll /account/<mormAddr>
//       for the BRIDGE_MINT to land (relayer typically <2s).
//
//   Burn side (MORM → ETH unlock):
//     - completely walletless: signTxWithConfirm() drives the existing
//       27f confirm dialog + 27g/h policy gates. The signed tx hits
//       /api/relay/morm-tx, then we poll /bridge/burns?only_pending=1
//       until the relayer marks evm_unlocked=1.
//
//   Bridge status panel:
//     - reads MORMBridge.lockNonce / unlockNonce + eth_getBalance
//       directly via JSON-RPC, plus the L1 pending-burns count.

import {
  ed, listIdentities, signTxWithConfirm, combineShares,
  hexToBytes, bytesToHex,
} from '/static/morm-identity.js';
import { t, mountLangToggle, applyDom } from '/static/morm-i18n.js';
import { maybeShowFirstTimeGuide, mountHelpButton, STEPS } from '/static/morm-guide.js';

const GATEWAY = window.location.origin;
let MORM_RPC   = null;     // resolved from /api/morm/info
let BRIDGE_CFG = null;     // { bridge_addr, evm_rpc, evm_chain_id }

// Function selectors (keccak256(sig)[:4]) for MORMBridge.sol.
const SEL_LOCK         = '0x9de746a5';   // lock(bytes20)
const SEL_LOCK_NONCE   = '0xb5a9096e';   // lockNonce()
const SEL_UNLOCK_NONCE = '0xdd926714';   // unlockNonce()
// Phase 28b — ERC-20 / MORMBridgeERC20 selectors.
const SEL_LOCK_TOKEN   = '0x8b1a8f0d';   // lockToken(address,uint256,bytes20)
const SEL_APPROVE      = '0x095ea7b3';   // approve(address,uint256)
const SEL_BALANCE_OF   = '0x70a08231';   // balanceOf(address)
const SEL_ALLOWANCE    = '0xdd62ed3e';   // allowance(address,address)
const SEL_DECIMALS     = '0x313ce567';   // decimals()
const SEL_MINT         = '0x40c10f19';   // mint(address,uint256) — MockUSDC PoC faucet

// USDC convention: 6 decimals. We display "USDC" units to the user but
// the on-chain amount is `units * 10**6`. The L1 BRIDGE_MINT receives
// the raw 6-decimal integer too (no implicit conversion in state.py).
const USDC_DECIMALS = 6;

const $ = id => document.getElementById(id);

// ---- log helpers --------------------------------------------------------
function logTo(elId, msg, cls = 'info') {
  const log = $(elId);
  if (!log) return;
  const line = document.createElement('div');
  line.className = cls;
  const ts = new Date().toLocaleTimeString();
  line.textContent = `[${ts}] ${msg}`;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}
const logLock = (m, c) => logTo('lock-log', m, c);
const logBurn = (m, c) => logTo('burn-log', m, c);

// ---- bootstrap ---------------------------------------------------------
async function bootstrap() {
  // Resolve MORM RPC (gateway-proxied) + bridge config concurrently.
  const [info, bridge] = await Promise.all([
    fetch(`${GATEWAY}/api/morm/info`).then(r => r.ok ? r.json() : null).catch(() => null),
    fetch(`${GATEWAY}/api/morm/bridge`).then(r => r.ok ? r.json() : null).catch(() => null),
  ]);
  if (info && info.rpc) MORM_RPC = info.rpc;
  BRIDGE_CFG = bridge || {};

  if (!BRIDGE_CFG.bridge_addr) {
    $('disabled-banner').style.display = 'block';
    $('lock-btn').disabled = true;
    $('burn-btn').disabled = true;
    $('mm-connect').disabled = true;
  }
  $('bs-contract').textContent = BRIDGE_CFG.bridge_addr || '—';
  $('bs-rpc').textContent      = MORM_RPC || '—';
  $('bs-chain').textContent    = BRIDGE_CFG.evm_chain_id != null
    ? `${BRIDGE_CFG.evm_chain_id} (${BRIDGE_CFG.evm_rpc})`
    : (BRIDGE_CFG.evm_rpc || '—');

  // Phase 28b: unhide the USDC tab + status block when both ERC-20
  // bridge addresses are configured.
  if (BRIDGE_CFG.erc20_bridge_addr && BRIDGE_CFG.usdc_addr) {
    $('tab-usdc').style.display = '';
    $('panel-usdc').style.display = '';
    $('bs-usdc-block').style.display = '';
    $('bs-usdc-token').textContent  = BRIDGE_CFG.usdc_addr;
    $('bs-usdc-bridge').textContent = BRIDGE_CFG.erc20_bridge_addr;
  }
}

// ---- identity -----------------------------------------------------------
async function currentIdentity() {
  try {
    const ids = await listIdentities();
    return ids[0] || null;
  } catch { return null; }
}

async function paintIdentity() {
  const id = await currentIdentity();
  $('ident-addr').textContent = id ? id.address : t('common.identity_unset');
}

// ---- EVM JSON-RPC plumbing (raw, no ethers) -----------------------------
let _rpcId = 0;
async function evmRpc(method, params = []) {
  const r = await fetch(BRIDGE_CFG.evm_rpc, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0', id: ++_rpcId, method, params,
    }),
  });
  const j = await r.json();
  if (j.error) throw new Error(`EVM RPC ${method}: ${j.error.message || JSON.stringify(j.error)}`);
  return j.result;
}

function hexToBigInt(h) {
  return BigInt(h);
}
function padHex(h, bytes) {
  // strip 0x, left-pad with zeros, lowercase
  let v = h.replace(/^0x/i, '').toLowerCase();
  const target = bytes * 2;
  if (v.length > target) v = v.slice(-target);
  return '0x' + v.padStart(target, '0');
}

// ---- tab switching ------------------------------------------------------
function setTab(which) {
  for (const id of ['lock', 'burn', 'usdc']) {
    const tab = $(`tab-${id}`);
    const panel = $(`panel-${id}`);
    if (!tab || !panel) continue;
    tab.classList.toggle('active', id === which);
    // For the USDC tab/panel, both `display:none` (hidden when not
    // configured) and `display:""` (configured + active) need to coexist
    // with the .active class. Keep the toggle simple; if the tab itself
    // isn't shown the user can't reach this code path.
    panel.classList.toggle('active', id === which);
  }
}
$('tab-lock').onclick = () => setTab('lock');
$('tab-burn').onclick = () => setTab('burn');
$('tab-usdc').onclick = () => setTab('usdc');

// ============================================================
//   LOCK side — MetaMask required
// ============================================================
let mmAccount = null;   // 0x… checksummed (lowercased here)

async function detectMetaMask() {
  return Boolean(window.ethereum && window.ethereum.request);
}

async function ensureChain() {
  // Switch (or add) to the configured chain. Anvil's 31337 is normally
  // not in MetaMask by default — we add it then switch.
  const want = BRIDGE_CFG.evm_chain_id;
  if (want == null) return;
  const wantHex = '0x' + want.toString(16);
  try {
    await window.ethereum.request({
      method: 'wallet_switchEthereumChain',
      params: [{ chainId: wantHex }],
    });
  } catch (e) {
    // 4902 = unrecognized chain → add then switch
    if (e && (e.code === 4902 || (e.data && e.data.originalError && e.data.originalError.code === 4902))) {
      await window.ethereum.request({
        method: 'wallet_addEthereumChain',
        params: [{
          chainId: wantHex,
          chainName: want === 31337 ? 'Anvil (local)' : `EVM ${want}`,
          rpcUrls: [BRIDGE_CFG.evm_rpc],
          nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
        }],
      });
    } else {
      throw e;
    }
  }
}

async function connectMetaMask() {
  if (!await detectMetaMask()) {
    logLock(t('swap.lock.no_metamask'), 'err');
    showFallbackCmd();
    return;
  }
  try {
    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
    if (!accounts || !accounts.length) throw new Error('no accounts returned');
    mmAccount = accounts[0].toLowerCase();
    await ensureChain();
    paintMmChip();
    logLock(t('swap.lock.connected', { addr: mmAccount }), 'ok');
  } catch (e) {
    logLock(`MetaMask: ${e.message || e}`, 'err');
  }
}

function paintMmChip() {
  const chip = $('mm-chip');
  const status = $('mm-status');
  if (mmAccount) {
    chip.classList.add('ok');
    status.textContent = t('swap.lock.connected',
      { addr: mmAccount.slice(0, 8) + '…' + mmAccount.slice(-4) });
    $('mm-connect').style.display = 'none';
  } else {
    chip.classList.remove('ok');
    status.textContent = t('swap.lock.connect');
    $('mm-connect').style.display = '';
  }
  // Phase 28b — same connection drives the USDC chip.
  if (typeof paintUmmChip === 'function') paintUmmChip();
  // Refresh per-account USDC stats whenever connect state flips.
  if (typeof refreshUsdcEvmStats === 'function'
      && BRIDGE_CFG && BRIDGE_CFG.usdc_addr) {
    refreshUsdcEvmStats();
  }
}

$('mm-connect').onclick = connectMetaMask;

// "use mine" autofill — pulls the active passkey identity's m0r address.
$('lock-use-mine').onclick = async () => {
  const id = await currentIdentity();
  if (!id) { logLock(t('swap.burn.no_identity'), 'err'); return; }
  // We need the bytes20 form; the lock(bytes20) call expects raw bytes.
  // The passkey identity is stored as `0x…40 hex` (already 20 bytes).
  // We render the human m0r form in the input but stash the hex for use.
  $('lock-recipient').value = id.address;
};

// Convert input recipient into 20 bytes hex. Accepts either:
//   m0r…  (base32)        → blake2b address
//   0x…40hex              → raw bytes20
async function recipientBytes20Hex(s) {
  s = (s || '').trim();
  if (/^0x[0-9a-fA-F]{40}$/.test(s)) return s.toLowerCase();
  if (s.startsWith('m0r')) {
    // Cheap base32 decode (RFC 4648, no padding, lowercase).
    // The body length is fixed at 32 chars for a 20-byte address.
    const body = s.slice(3).toUpperCase();
    const ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    let bits = 0, value = 0;
    const bytes = [];
    for (const ch of body) {
      const v = ALPHA.indexOf(ch);
      if (v < 0) throw new Error(`bad m0r char: ${ch}`);
      value = (value << 5) | v;
      bits += 5;
      if (bits >= 8) {
        bytes.push((value >> (bits - 8)) & 0xff);
        bits -= 8;
      }
    }
    if (bytes.length !== 20) throw new Error(`m0r decoded to ${bytes.length} bytes, want 20`);
    return '0x' + bytes.map(b => b.toString(16).padStart(2, '0')).join('');
  }
  // Some passkey identities store the address as 0x…40hex already.
  if (/^0x[0-9a-fA-F]{40}$/.test(s)) return s.toLowerCase();
  throw new Error('recipient must be m0r… or 0x…40hex');
}

function showFallbackCmd() {
  // Minimal cast command the user can paste into a terminal.
  const addr = BRIDGE_CFG.bridge_addr || '<bridge_addr>';
  const recipient = $('lock-recipient').value || '<m0r…>';
  const amount = $('lock-amount').value || '0.5';
  const cmd = `cast send ${addr} "lock(bytes20)" 0x<bytes20-of-${recipient}> \\
  --value ${amount}ether \\
  --rpc-url ${BRIDGE_CFG.evm_rpc} \\
  --private-key 0x<your-evm-key>`;
  $('fallback-pre').textContent = cmd;
  $('fallback-cmd').style.display = 'block';
}

// ETH → wei (BigInt). Caller passes a decimal string like "0.5".
function ethToWei(ethStr) {
  const s = String(ethStr).trim();
  if (!/^\d+(\.\d+)?$/.test(s)) throw new Error('amount must be decimal ETH');
  const [intPart, fracPart = ''] = s.split('.');
  const frac = (fracPart + '000000000000000000').slice(0, 18);
  return BigInt(intPart) * 10n ** 18n + BigInt(frac || '0');
}

async function pollMintFor(mormAddr, expectedBalAtLeast, timeoutMs = 30_000) {
  const t0 = Date.now();
  let bal = -1n;
  while (Date.now() - t0 < timeoutMs) {
    try {
      const r = await fetch(`${MORM_RPC}/account/${mormAddr}`);
      if (r.ok) {
        const j = await r.json();
        bal = BigInt(j.balance || 0);
        if (bal >= expectedBalAtLeast) return bal;
      }
    } catch {}
    await sleep(800);
  }
  return bal;
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function lockEth() {
  if (!BRIDGE_CFG.bridge_addr) return;
  const btn = $('lock-btn');
  btn.disabled = true;
  const oldText = btn.textContent;
  btn.textContent = t('swap.lock.btn_busy');
  try {
    if (!await detectMetaMask()) {
      throw new Error(t('swap.lock.no_metamask'));
    }
    if (!mmAccount) await connectMetaMask();
    if (!mmAccount) throw new Error('not connected');

    const recipientHex = await recipientBytes20Hex($('lock-recipient').value);
    const amountWei = ethToWei($('lock-amount').value);
    if (amountWei === 0n) throw new Error('amount must be > 0');

    // calldata = selector || left-pad-32(bytes20) (Solidity ABI: bytes20 is
    // a value type, padded to 32 bytes).
    const data = SEL_LOCK + recipientHex.slice(2).padEnd(64, '0');

    // Ask MetaMask to send the tx. Value is hex-encoded wei; gas is left
    // for the wallet to estimate.
    const txHash = await window.ethereum.request({
      method: 'eth_sendTransaction',
      params: [{
        from: mmAccount,
        to:   BRIDGE_CFG.bridge_addr,
        value: '0x' + amountWei.toString(16),
        data,
      }],
    });
    logLock(t('swap.lock.tx_sent', { hash: txHash }), 'info');

    // Poll for receipt — MetaMask returns the hash before mining.
    let receipt = null;
    for (let i = 0; i < 60; i++) {
      receipt = await evmRpc('eth_getTransactionReceipt', [txHash]).catch(() => null);
      if (receipt) break;
      await sleep(500);
    }
    if (!receipt) throw new Error('receipt timeout');
    if (receipt.status !== '0x1') {
      throw new Error(`reverted (status=${receipt.status})`);
    }
    logLock(t('swap.lock.tx_mined', { block: parseInt(receipt.blockNumber, 16) }), 'ok');

    // Poll the L1 for the BRIDGE_MINT.
    const id = await currentIdentity();
    if (id && id.address && (id.address.startsWith('m0r') || /^0x[0-9a-f]{40}$/i.test(id.address))) {
      // If recipient matches active identity, we can show their balance live.
      const recipientForPoll = $('lock-recipient').value.trim() || id.address;
      logLock(t('swap.lock.waiting_mint'), 'muted');
      const before = await fetch(`${MORM_RPC}/account/${recipientForPoll}`).then(r => r.json()).catch(() => ({balance: 0}));
      const baseline = BigInt(before.balance || 0);
      const newBal = await pollMintFor(recipientForPoll, baseline + amountWei);
      if (newBal >= baseline + amountWei) {
        logLock(t('swap.lock.minted', {
          amount: (newBal - baseline).toString(),
          addr: recipientForPoll,
        }), 'ok');
      } else {
        logLock('mint poll timed out — check relayer', 'err');
      }
    }
    refreshStatus();   // bridge balance / nonces
  } catch (e) {
    logLock(t('swap.lock.tx_failed', { err: e.message || e }), 'err');
    showFallbackCmd();
  } finally {
    btn.disabled = false;
    btn.textContent = oldText;
  }
}
$('lock-btn').onclick = lockEth;

// ============================================================
//   BURN side — passkey only
// ============================================================
async function burnMorm() {
  if (!BRIDGE_CFG.bridge_addr) return;
  const btn = $('burn-btn');
  btn.disabled = true;
  const oldText = btn.textContent;
  btn.textContent = t('swap.burn.btn_busy');
  let seed = null;
  try {
    const id = await currentIdentity();
    if (!id) throw new Error(t('swap.burn.no_identity'));

    const amount = Number($('burn-amount').value);
    if (!Number.isFinite(amount) || amount <= 0) {
      throw new Error('amount must be > 0');
    }
    const evmRecipient = $('burn-recipient').value.trim();
    if (!/^0x[0-9a-fA-F]{40}$/.test(evmRecipient)) {
      throw new Error('EVM recipient must be 0x… 40 hex');
    }

    // 1) reconstruct seed via 2-of-2 share split
    const sh = await fetch(`${GATEWAY}/api/dev/share`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential_id: id.credential_id }),
    }).then(r => r.json());
    if (!sh.server_share) throw new Error('share fetch failed');
    seed = combineShares(sh.server_share, id.client_share);
    const pub = await ed.getPublicKeyAsync(seed);

    // 2) fetch nonce
    const acct = await fetch(`${MORM_RPC}/account/${id.address}`).then(r => r.json());
    const nonce = acct.nonce;

    // 3) sign BRIDGE_BURN with the 27f confirm dialog + 27g/h policy gate
    const tx = await signTxWithConfirm({
      kind: 21,
      senderPub: pub,
      senderSeed: seed,
      nonce,
      payload: {
        amount,
        evm_recipient: evmRecipient,
        token: 'MORM',
      },
    });
    if (!tx) {
      logBurn(t('swap.burn.cancelled'), 'err');
      return;
    }

    // 4) relay
    const relay = await fetch(`${GATEWAY}/api/relay/morm-tx`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tx }),
    }).then(r => r.json());
    if (!relay.ok) throw new Error(`relay failed: ${JSON.stringify(relay)}`);
    const burnHash = relay.morm_response.tx_hash;
    logBurn(t('swap.burn.signed', { hash: burnHash }), 'ok');

    // 5) wipe seed before polling
    seed.fill(0); seed = null;

    // 6) poll until evm_unlocked=1
    logBurn(t('swap.burn.waiting_unlock'), 'muted');
    const t0 = Date.now();
    while (Date.now() - t0 < 30_000) {
      try {
        const r = await fetch(`${MORM_RPC}/bridge/burns`).then(r => r.json());
        const row = (r.burns || []).find(b => b.burn_tx_hash === burnHash);
        if (row && row.evm_unlocked) {
          logBurn(t('swap.burn.unlocked', {
            amount: row.amount.toString(),
            addr:   row.evm_recipient,
          }), 'ok');
          refreshStatus();
          return;
        }
      } catch {}
      await sleep(800);
    }
    logBurn('unlock poll timed out — check relayer', 'err');
  } catch (e) {
    logBurn(t('swap.burn.failed', { err: e.message || e }), 'err');
  } finally {
    if (seed) seed.fill(0);
    btn.disabled = false;
    btn.textContent = oldText;
  }
}
$('burn-btn').onclick = burnMorm;

// ============================================================
//   STATUS panel
// ============================================================
async function refreshStatus() {
  if (!BRIDGE_CFG.bridge_addr || !BRIDGE_CFG.evm_rpc) return;
  try {
    const [balHex, lockNHex, unlockNHex, l1Burns] = await Promise.all([
      evmRpc('eth_getBalance', [BRIDGE_CFG.bridge_addr, 'latest']).catch(() => '0x0'),
      evmRpc('eth_call', [{ to: BRIDGE_CFG.bridge_addr, data: SEL_LOCK_NONCE }, 'latest']).catch(() => '0x0'),
      evmRpc('eth_call', [{ to: BRIDGE_CFG.bridge_addr, data: SEL_UNLOCK_NONCE }, 'latest']).catch(() => '0x0'),
      MORM_RPC ? fetch(`${MORM_RPC}/bridge/burns?only_pending=1`).then(r => r.ok ? r.json() : { burns: [] }).catch(() => ({ burns: [] })) : Promise.resolve({ burns: [] }),
    ]);
    const balWei = hexToBigInt(balHex);
    const lockNonce = Number(hexToBigInt(lockNHex));
    const unlockNonce = Number(hexToBigInt(unlockNHex));
    const pending = (l1Burns.burns || []).length;

    // Format ETH with 4 decimals.
    const ethWhole = balWei / 10n ** 18n;
    const ethFrac  = (balWei % 10n ** 18n).toString().padStart(18, '0').slice(0, 4);
    $('bs-locked').textContent = `${ethWhole}.${ethFrac} ETH (${balWei} wei)`;
    $('bs-lock-nonce').textContent = String(lockNonce);
    $('bs-unlock-nonce').textContent = String(unlockNonce);
    $('bs-pending-burns').textContent = String(pending);
  } catch (e) {
    console.warn('[swap] status refresh failed', e);
  }
}

// ============================================================
//   USDC tab (Phase 28b) — Lock USDC / Burn USDC
// ============================================================

const logUsdc = (m, c) => logTo('usdc-log', m, c);

// USDC sub-tab toggling (Lock / Burn within the USDC panel)
function setUsdcSub(which) {
  $('usdc-tab-lock').classList.toggle('active', which === 'lock');
  $('usdc-tab-burn').classList.toggle('active', which === 'burn');
  $('usdc-panel-lock').style.display = which === 'lock' ? '' : 'none';
  $('usdc-panel-burn').style.display = which === 'burn' ? '' : 'none';
  if (which === 'burn') refreshUsdcL1Balance();
}

// MetaMask chip mirrors the ETH side (same mmAccount), so paint when
// the user enters the USDC tab if connection happens here first.
function paintUmmChip() {
  const chip = $('umm-chip');
  const status = $('umm-status');
  if (mmAccount) {
    chip.classList.add('ok');
    status.textContent = t('swap.lock.connected',
      { addr: mmAccount.slice(0, 8) + '…' + mmAccount.slice(-4) });
  } else {
    chip.classList.remove('ok');
    status.textContent = t('swap.lock.connect');
  }
}

// USDC -> raw 6-decimal int (BigInt). "100" → 100_000_000n.
function usdcToRaw(s) {
  const v = String(s).trim();
  if (!/^\d+(\.\d+)?$/.test(v)) throw new Error('amount must be decimal USDC');
  const [intPart, fracPart = ''] = v.split('.');
  const frac = (fracPart + '000000').slice(0, USDC_DECIMALS);
  return BigInt(intPart) * 10n ** BigInt(USDC_DECIMALS) + BigInt(frac || '0');
}

// raw 6-decimal int -> "X.YYYYYY" display
function rawToUsdc(rawBig) {
  const whole = rawBig / 10n ** BigInt(USDC_DECIMALS);
  const frac  = (rawBig % 10n ** BigInt(USDC_DECIMALS))
    .toString().padStart(USDC_DECIMALS, '0').replace(/0+$/, '') || '0';
  return frac === '0' ? `${whole}` : `${whole}.${frac}`;
}

function padAddrTo32(hexAddr) {
  return hexAddr.replace(/^0x/i, '').toLowerCase().padStart(64, '0');
}

function bigIntToHex32(b) {
  return b.toString(16).padStart(64, '0');
}

// ABI-decode a single uint256 from an eth_call result
function decodeUint(hex) {
  return BigInt(hex || '0x0');
}

async function evmCall(to, data) {
  return await evmRpc('eth_call', [{ to, data }, 'latest']);
}

async function fetchUsdcBalance(addr) {
  const data = SEL_BALANCE_OF + padAddrTo32(addr);
  return decodeUint(await evmCall(BRIDGE_CFG.usdc_addr, data));
}

async function fetchUsdcAllowance(owner, spender) {
  const data = SEL_ALLOWANCE + padAddrTo32(owner) + padAddrTo32(spender);
  return decodeUint(await evmCall(BRIDGE_CFG.usdc_addr, data));
}

async function refreshUsdcEvmStats() {
  if (!BRIDGE_CFG.usdc_addr || !BRIDGE_CFG.erc20_bridge_addr) return;
  // status panel: total USDC locked in bridge
  try {
    const locked = await fetchUsdcBalance(BRIDGE_CFG.erc20_bridge_addr);
    $('bs-usdc-locked').textContent = `${rawToUsdc(locked)} USDC (${locked} raw)`;
  } catch {}
  // user-side stats only when MetaMask connected
  if (!mmAccount) {
    $('usdc-mybal').textContent = '—';
    $('usdc-allow').textContent = '—';
    return;
  }
  try {
    const [bal, allow] = await Promise.all([
      fetchUsdcBalance(mmAccount),
      fetchUsdcAllowance(mmAccount, BRIDGE_CFG.erc20_bridge_addr),
    ]);
    $('usdc-mybal').textContent = `${rawToUsdc(bal)} USDC`;
    $('usdc-allow').textContent = `${rawToUsdc(allow)} USDC`;
  } catch (e) {
    console.warn('[28b] usdc stats refresh failed', e);
  }
}

async function refreshUsdcL1Balance() {
  const id = await currentIdentity();
  if (!id || !MORM_RPC) { $('usdc-l1bal').textContent = '—'; return; }
  try {
    const acct = await fetch(`${MORM_RPC}/account/${id.address}`).then(r => r.json());
    const tokens = acct.tokens || {};
    const usdc = BigInt(tokens.USDC || 0);
    $('usdc-l1bal').textContent = `${rawToUsdc(usdc)} USDC.morm (${usdc} raw)`;
  } catch (e) {
    $('usdc-l1bal').textContent = '—';
    console.warn('[28b] L1 USDC balance failed', e);
  }
}

// ---- USDC faucet (PoC MockUSDC.mint) ----
$('usdc-faucet').onclick = async () => {
  if (!await detectMetaMask()) {
    logUsdc(t('swap.lock.no_metamask'), 'err');
    return;
  }
  if (!mmAccount) await connectMetaMask();
  if (!mmAccount) return;
  const amount = 1000n * 10n ** BigInt(USDC_DECIMALS);
  // mint(addr, uint256)
  const data = SEL_MINT + padAddrTo32(mmAccount) + bigIntToHex32(amount);
  try {
    const txHash = await window.ethereum.request({
      method: 'eth_sendTransaction',
      params: [{ from: mmAccount, to: BRIDGE_CFG.usdc_addr, data }],
    });
    logUsdc(t('swap.usdc.faucet_done', { addr: mmAccount }), 'ok');
    logUsdc(`evm tx ${txHash}`, 'muted');
    setTimeout(refreshUsdcEvmStats, 1500);
  } catch (e) {
    logUsdc(`faucet: ${e.message || e}`, 'err');
  }
};

$('usdc-lock-use-mine').onclick = async () => {
  const id = await currentIdentity();
  if (!id) { logUsdc(t('swap.burn.no_identity'), 'err'); return; }
  $('usdc-lock-recipient').value = id.address;
};

// USDC sub-tab buttons
$('usdc-tab-lock').onclick = () => setUsdcSub('lock');
$('usdc-tab-burn').onclick = () => setUsdcSub('burn');

// ---- USDC approve ----
$('usdc-approve-btn').onclick = async () => {
  const btn = $('usdc-approve-btn');
  btn.disabled = true;
  const oldText = btn.textContent;
  btn.textContent = t('swap.usdc.approve_busy');
  try {
    if (!await detectMetaMask()) throw new Error(t('swap.lock.no_metamask'));
    if (!mmAccount) await connectMetaMask();
    if (!mmAccount) throw new Error('not connected');
    const amount = usdcToRaw($('usdc-lock-amount').value || '0');
    if (amount === 0n) throw new Error('amount must be > 0');
    const data = SEL_APPROVE
      + padAddrTo32(BRIDGE_CFG.erc20_bridge_addr)
      + bigIntToHex32(amount);
    const txHash = await window.ethereum.request({
      method: 'eth_sendTransaction',
      params: [{ from: mmAccount, to: BRIDGE_CFG.usdc_addr, data }],
    });
    logUsdc(`approve tx ${txHash}`, 'info');
    // wait for receipt
    let receipt = null;
    for (let i = 0; i < 40; i++) {
      receipt = await evmRpc('eth_getTransactionReceipt', [txHash]).catch(() => null);
      if (receipt) break;
      await sleep(500);
    }
    if (!receipt || receipt.status !== '0x1') throw new Error(`approve reverted`);
    logUsdc(t('swap.usdc.approve_done', { amount: rawToUsdc(amount) }), 'ok');
    $('usdc-lock-btn').disabled = false;
    refreshUsdcEvmStats();
  } catch (e) {
    logUsdc(`approve: ${e.message || e}`, 'err');
  } finally {
    btn.disabled = false;
    btn.textContent = oldText;
  }
};

// ---- USDC lock ----
$('usdc-lock-btn').onclick = async () => {
  const btn = $('usdc-lock-btn');
  btn.disabled = true;
  const oldText = btn.textContent;
  btn.textContent = t('swap.usdc.lock_busy');
  try {
    if (!mmAccount) throw new Error('not connected');
    const amount = usdcToRaw($('usdc-lock-amount').value || '0');
    if (amount === 0n) throw new Error('amount must be > 0');
    // pre-flight: allowance >= amount
    const allow = await fetchUsdcAllowance(mmAccount, BRIDGE_CFG.erc20_bridge_addr);
    if (allow < amount) {
      throw new Error(t('swap.usdc.need_approve',
        { allow: rawToUsdc(allow), amount: rawToUsdc(amount) }));
    }
    const recipientHex = await recipientBytes20Hex($('usdc-lock-recipient').value);
    // calldata = SEL_LOCK_TOKEN || pad32(usdc_addr) || pad32(amount) || pad32(bytes20)
    const data = SEL_LOCK_TOKEN
      + padAddrTo32(BRIDGE_CFG.usdc_addr)
      + bigIntToHex32(amount)
      + recipientHex.slice(2).padEnd(64, '0');
    const txHash = await window.ethereum.request({
      method: 'eth_sendTransaction',
      params: [{ from: mmAccount, to: BRIDGE_CFG.erc20_bridge_addr, data }],
    });
    logUsdc(t('swap.lock.tx_sent', { hash: txHash }), 'info');
    let receipt = null;
    for (let i = 0; i < 60; i++) {
      receipt = await evmRpc('eth_getTransactionReceipt', [txHash]).catch(() => null);
      if (receipt) break;
      await sleep(500);
    }
    if (!receipt || receipt.status !== '0x1') throw new Error(`lockToken reverted`);
    logUsdc(t('swap.lock.tx_mined', { block: parseInt(receipt.blockNumber, 16) }), 'ok');
    // poll L1 USDC.morm balance for the recipient
    const recipientForPoll = $('usdc-lock-recipient').value.trim();
    logUsdc(t('swap.lock.waiting_mint'), 'muted');
    const before = await fetch(`${MORM_RPC}/account/${recipientForPoll}`).then(r => r.json()).catch(() => ({tokens:{}}));
    const baseline = BigInt((before.tokens || {}).USDC || 0);
    const t0 = Date.now();
    while (Date.now() - t0 < 30_000) {
      try {
        const a = await fetch(`${MORM_RPC}/account/${recipientForPoll}`).then(r => r.json());
        const cur = BigInt((a.tokens || {}).USDC || 0);
        if (cur >= baseline + amount) {
          logUsdc(t('swap.usdc.locked', {
            amount: rawToUsdc(cur - baseline),
            addr: recipientForPoll,
          }), 'ok');
          break;
        }
      } catch {}
      await sleep(800);
    }
    refreshUsdcEvmStats();
    refreshUsdcL1Balance();
  } catch (e) {
    logUsdc(t('swap.lock.tx_failed', { err: e.message || e }), 'err');
  } finally {
    btn.disabled = false;
    btn.textContent = oldText;
  }
};

// ---- USDC burn (passkey-signed BRIDGE_BURN with token=USDC) ----
$('usdc-burn-btn').onclick = async () => {
  const btn = $('usdc-burn-btn');
  btn.disabled = true;
  const oldText = btn.textContent;
  btn.textContent = t('swap.usdc.burn_busy');
  let seed = null;
  try {
    const id = await currentIdentity();
    if (!id) throw new Error(t('swap.burn.no_identity'));

    const amount = usdcToRaw($('usdc-burn-amount').value || '0');
    if (amount === 0n) throw new Error('amount must be > 0');
    const evmRecipient = $('usdc-burn-recipient').value.trim();
    if (!/^0x[0-9a-fA-F]{40}$/.test(evmRecipient)) {
      throw new Error('EVM recipient must be 0x… 40 hex');
    }

    const sh = await fetch(`${GATEWAY}/api/dev/share`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential_id: id.credential_id }),
    }).then(r => r.json());
    if (!sh.server_share) throw new Error('share fetch failed');
    seed = combineShares(sh.server_share, id.client_share);
    const pub = await ed.getPublicKeyAsync(seed);

    const acct = await fetch(`${MORM_RPC}/account/${id.address}`).then(r => r.json());
    const nonce = acct.nonce;

    const tx = await signTxWithConfirm({
      kind: 21,
      senderPub: pub,
      senderSeed: seed,
      nonce,
      payload: {
        amount: Number(amount),  // L1 expects int; 6-decimal USDC fits in i64
        evm_recipient: evmRecipient,
        token: 'USDC',
        token_address: BRIDGE_CFG.usdc_addr,
      },
    });
    if (!tx) {
      logUsdc(t('swap.burn.cancelled'), 'err');
      return;
    }
    const relay = await fetch(`${GATEWAY}/api/relay/morm-tx`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tx }),
    }).then(r => r.json());
    if (!relay.ok) throw new Error(`relay failed: ${JSON.stringify(relay)}`);
    const burnHash = relay.morm_response.tx_hash;
    logUsdc(t('swap.burn.signed', { hash: burnHash }), 'ok');

    seed.fill(0); seed = null;

    logUsdc(t('swap.burn.waiting_unlock'), 'muted');
    const t0 = Date.now();
    while (Date.now() - t0 < 30_000) {
      try {
        const r = await fetch(`${MORM_RPC}/bridge/burns`).then(r => r.json());
        const row = (r.burns || []).find(b => b.burn_tx_hash === burnHash);
        if (row && row.evm_unlocked) {
          logUsdc(t('swap.usdc.unlocked', {
            amount: rawToUsdc(BigInt(row.amount)),
            addr: row.evm_recipient,
          }), 'ok');
          refreshUsdcEvmStats();
          refreshUsdcL1Balance();
          return;
        }
      } catch {}
      await sleep(800);
    }
    logUsdc('unlock poll timed out — check relayer', 'err');
  } catch (e) {
    logUsdc(t('swap.burn.failed', { err: e.message || e }), 'err');
  } finally {
    if (seed) seed.fill(0);
    btn.disabled = false;
    btn.textContent = oldText;
  }
};

// ---- init --------------------------------------------------------------
window.addEventListener('morm-lang-changed', () => {
  applyDom();
  paintMmChip();
  paintIdentity();
});

(async function init() {
  mountLangToggle($('lang-toggle'));
  mountHelpButton($('help-btn'), 'swap', STEPS.swap);
  await bootstrap();
  await paintIdentity();
  refreshStatus();
  setInterval(refreshStatus, 5000);
  // Phase 28b — keep USDC stats live whenever the tab is configured.
  if (BRIDGE_CFG.erc20_bridge_addr && BRIDGE_CFG.usdc_addr) {
    refreshUsdcEvmStats();
    refreshUsdcL1Balance();
    setInterval(refreshUsdcEvmStats, 5000);
    setInterval(refreshUsdcL1Balance, 5000);
  }
  // First-visit walkthrough.
  maybeShowFirstTimeGuide('swap', STEPS.swap);
})();
