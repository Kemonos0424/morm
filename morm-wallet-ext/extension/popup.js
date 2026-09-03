// MORM Wallet popup controller.
// Protection methods: passkey (same passkey as morm.one, via PRF) or password.
import {
  loadRecord, hasWallet,
  newSeedWithRecovery, seedFromRecovery, sessionForSeed,
  protectSeedWithPassword, protectWithPRF,
  unlockWithPassword, unlockWithPRF,
  bytesToB64u, b64uToBytes,
} from "./wallet.js";
import { webauthnSupported, createPasskey, passkeyPRF } from "./passkey.js";
import {
  getAccountState, resolveHandle, submitTransfer, submitBridgeBurn, getNodes,
  buildTransfer, buildBridgeBurn, signTx, mormToBaseUnits, formatBaseUnits, isValidMormAddress, hexToBytes,
} from "./walletcore/index.js";
import { API_BASE, NODE_BASE } from "./config.js";

// Base(EVM)-side actions live on the web app (MetaMask/WalletConnect). The
// extension hands off rather than embedding a second (secp256k1) signer.
const MARKET_URL = "https://market.morm.one/";
const LINK_EVM_URL = "https://www.morm.one/account.html";

const store = {
  get: (k) => new Promise((res) => chrome.storage.local.get(k, (o) => res(o[k]))),
  set: (k, v) => new Promise((res) => chrome.storage.local.set({ [k]: v }, res)),
  remove: (k) => new Promise((res) => chrome.storage.local.remove(k, res)),
};

const $ = (id) => document.getElementById(id);
const SECTIONS = ["secOnboard", "secCreatePw", "secReveal", "secImport", "secLocked", "secHome"];
function show(id) { SECTIONS.forEach((s) => $(s).classList.toggle("on", s === id)); }
function bgSend(msg) {
  return new Promise((res) => chrome.runtime.sendMessage(msg, (r) => res(chrome.runtime.lastError ? null : r)));
}
let currentAddress = null;
let currentAcc = null; // last fetched account state (balance/nonce/evmAddress/baseUnitsPerMorm)

async function goHome(session, kindLabel) {
  await bgSend({ type: "setUnlocked", ...session });
  currentAddress = session.address;
  $("homeAddr").textContent = session.address;
  $("homeKind").textContent = kindLabel || "";
  resetSend();
  show("secHome");
  refreshBalance();
}

// ---- balance / receive -----------------------------------------------------
async function refreshBalance() {
  if (!currentAddress) return;
  $("homeBal").textContent = "…";
  try {
    const acc = await getAccountState(API_BASE, currentAddress);
    currentAcc = acc;
    const c = acc.chain || {};
    $("homeBal").textContent = `${formatBaseUnits(c.balance ?? 0, acc.baseUnitsPerMorm || 1)} MORM`;
    $("homeMsg").textContent = acc.registered ? "" : "未登録アドレス（受取は可能）";
    syncBridgeEvm();
  } catch (e) { $("homeBal").textContent = "取得失敗"; $("homeMsg").textContent = String(e.message || e); }
}

// Reflect the linked Base(0x) address into the bridge view (or prompt to link).
function syncBridgeEvm() {
  const evm = currentAcc?.evmAddress || null;
  $("brNoEvm").style.display = evm ? "none" : "block";
  $("brInput").style.display = evm ? "block" : "none";
  if (evm) $("brEvm").textContent = evm;
}

// ---- home tabs -------------------------------------------------------------
function setTab(which) {
  $("tabSend").classList.toggle("on", which === "send");
  $("tabBridge").classList.toggle("on", which === "bridge");
  $("tabNode").classList.toggle("on", which === "node");
  $("viewSend").style.display = which === "send" ? "block" : "none";
  $("viewBridge").style.display = which === "bridge" ? "block" : "none";
  $("viewNode").style.display = which === "node" ? "block" : "none";
  if (which === "bridge") syncBridgeEvm();
  if (which === "node") loadNodes();
}
$("tabSend").onclick = () => setTab("send");
$("tabBridge").onclick = () => setTab("bridge");
$("tabNode").onclick = () => setTab("node");

// ---- node view (read-only; rewards are push-based, no claim) ---------------
function esc(s) { return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }

async function loadNodes() {
  if (!currentAddress) return;
  $("nodeMsg").textContent = "読み込み中…";
  $("nodeList").innerHTML = ""; $("nodeEmit").innerHTML = "";
  try {
    const d = await getNodes(NODE_BASE, currentAddress);
    const base = d.baseUnitsPerMorm || 1;
    if (d.unavailable) { $("nodeMsg").textContent = "ノード情報の取得口が未デプロイです（api.morm.one）。"; return; }
    if (!d.nodes?.length) {
      $("nodeMsg").textContent = "この口座に紐づくノードはありません。";
    } else {
      $("nodeMsg").textContent = "";
      $("nodeList").innerHTML = d.nodes.map((n) => `
        <div class="addr" style="margin-top:8px">
          <b>${esc(n.name || n.id)}</b> · <span>${esc(n.status || "?")}</span><br>
          スコア ${n.totalScore}（base ${n.baseScore} / task ${n.taskScore}）<br>
          残高 ${formatBaseUnits(n.mormBalance, base)} / 保留 ${formatBaseUnits(n.mormPending, base)} MORM
        </div>`).join("");
    }
    if (d.emissions?.length) {
      const rows = d.emissions.slice(0, 10).map((e) =>
        `<div class="muted" style="font-family:ui-monospace,monospace;font-size:11px">
           ${esc(e.epochLabel)} · ${formatBaseUnits(e.units, base)} MORM · ${esc(e.status)}</div>`).join("");
      $("nodeEmit").innerHTML = `<label>報酬履歴（自動払出し）</label>${rows}`;
    }
  } catch (e) { $("nodeMsg").textContent = "取得失敗: " + String(e.message || e); }
}
$("btnNodeRefresh").onclick = loadNodes;

// ---- Base handoffs ---------------------------------------------------------
$("btnSwapHO").onclick = () => window.open(MARKET_URL, "_blank");
$("btnDepositHO").onclick = () => window.open(MARKET_URL, "_blank");
$("btnLinkEvm").onclick = () => window.open(LINK_EVM_URL, "_blank");
$("btnRefresh").onclick = refreshBalance;
$("btnCopyAddr").onclick = async () => {
  try { await navigator.clipboard.writeText(currentAddress || ""); $("homeMsg").textContent = "アドレスをコピーしました。"; }
  catch { $("homeMsg").textContent = "コピーできませんでした。"; }
};

// ---- send ------------------------------------------------------------------
let sendCtx = null; // { to, handle, amountBase (BigInt), amountDisplay }

function resetSend() {
  sendCtx = null;
  $("sendInput").style.display = "block";
  $("sendConfirm").style.display = "none";
  $("sendResult").style.display = "none";
  $("toInput").value = ""; $("amtInput").value = "";
  $("sendErr").textContent = ""; $("cfErr").textContent = "";
  resetBridge();
  setTab("send");
}
$("btnSendMore").onclick = () => { resetSend(); refreshBalance(); };
$("btnSendCancel").onclick = () => { $("sendConfirm").style.display = "none"; $("sendInput").style.display = "block"; };

$("btnSendReview").onclick = async () => {
  $("sendErr").textContent = "";
  const raw = $("toInput").value.trim();
  const amtStr = $("amtInput").value.trim();
  if (!raw) return void ($("sendErr").textContent = "送金先を入力してください");
  if (!amtStr) return void ($("sendErr").textContent = "金額を入力してください");
  try {
    // Resolve recipient: handle (@name) via API, or a pasted m0r address.
    let to = null, handle = null;
    if (isValidMormAddress(raw)) {
      to = raw;
    } else {
      const h = raw.replace(/^@/, "");
      const r = await resolveHandle(API_BASE, h);
      if (!r.found) return void ($("sendErr").textContent = `@${h} は見つかりません`);
      to = r.address; handle = r.handle;
    }
    // Amount -> base units using the LIVE baseUnitsPerMorm (never hardcode).
    const acc = await getAccountState(API_BASE, currentAddress);
    const base = acc.baseUnitsPerMorm || 1;
    const amountBase = mormToBaseUnits(amtStr, base);
    // Sufficient-funds check (BigInt).
    if (BigInt(acc.chain?.balance ?? 0) < amountBase) {
      return void ($("sendErr").textContent = "残高が不足しています");
    }
    sendCtx = { to, handle, amountBase, amountDisplay: formatBaseUnits(amountBase, base) };
    $("cfTo").textContent = to;
    $("cfHandle").textContent = handle ? `@${handle}` : "（ハンドル無し／アドレス直接指定）";
    $("cfAmt").textContent = `${sendCtx.amountDisplay} MORM`;
    $("cfErr").textContent = "";
    $("sendInput").style.display = "none";
    $("sendConfirm").style.display = "block";
  } catch (e) { $("sendErr").textContent = String(e.message || e); }
};

$("btnSendGo").onclick = async () => {
  if (!sendCtx) return;
  $("cfErr").textContent = "送信中…";
  $("btnSendGo").disabled = true;
  let seed;
  try {
    const session = await bgSend({ type: "getSession" });
    if (!session?.seedHex) throw new Error("ロックされています。解錠し直してください");
    // Fresh nonce right before signing (avoids stale-nonce rejects).
    const acc = await getAccountState(API_BASE, currentAddress);
    const nonce = Number(acc.chain?.nonce ?? 0);
    const body = buildTransfer({ senderPubkeyHex: session.pubkeyHex, nonce, to: sendCtx.to, amount: sendCtx.amountBase });
    seed = hexToBytes(session.seedHex);
    const signed = await signTx(body, seed);
    const res = await submitTransfer(API_BASE, signed);
    $("rsHash").textContent = res.txHash || "(受理)";
    $("sendConfirm").style.display = "none";
    $("sendResult").style.display = "block";
  } catch (e) {
    $("cfErr").textContent = "送信失敗: " + String(e.message || e);
  } finally {
    if (seed) seed.fill(0);
    $("btnSendGo").disabled = false;
  }
};

// ---- routing ---------------------------------------------------------------
async function route() {
  const state = await bgSend({ type: "getState" });
  if (state && !state.locked && state.address) {
    currentAddress = state.address;
    $("homeAddr").textContent = state.address;
    resetSend();
    show("secHome");
    refreshBalance();
    return;
  }
  const rec = await loadRecord(store);
  if (rec) {
    $("lockPasskey").style.display = rec.kdf === "prf" ? "block" : "none";
    $("lockPassword").style.display = rec.kdf === "pbkdf2" ? "block" : "none";
    show("secLocked");
  } else {
    show("secOnboard");
  }
}

// ---- reveal (shared by create flows) ---------------------------------------
let pendingRecovery = null;
let pendingSession = null;
let pendingKind = "";
let clipTimer = null;

function startReveal(recoveryKey, session, kindLabel) {
  pendingRecovery = recoveryKey;
  pendingSession = session;
  pendingKind = kindLabel;
  $("revAddr").textContent = session.address;
  $("revRk").textContent = recoveryKey;
  $("revRk").classList.add("masked");
  $("btnRevToggle").textContent = "表示";
  $("revAck").checked = false;
  $("btnRevDone").disabled = true;
  $("copyNote").textContent = "";
  show("secReveal");
}

$("btnRevToggle").onclick = () => {
  const masked = $("revRk").classList.toggle("masked");
  $("btnRevToggle").textContent = masked ? "表示" : "隠す";
};
$("btnRevCopy").onclick = async () => {
  try {
    await navigator.clipboard.writeText(pendingRecovery || "");
    $("copyNote").textContent = "コピーしました。20秒後にクリップボードを自動消去します。";
    if (clipTimer) clearTimeout(clipTimer);
    clipTimer = setTimeout(async () => {
      try { await navigator.clipboard.writeText(""); $("copyNote").textContent = "クリップボードを消去しました。"; } catch {}
    }, 20000);
  } catch { $("copyNote").textContent = "コピーできませんでした。手動で控えてください。"; }
};
$("revAck").onchange = () => { $("btnRevDone").disabled = !$("revAck").checked; };
$("btnRevDone").onclick = async () => {
  const session = pendingSession;
  const kind = pendingKind;
  pendingRecovery = null; pendingSession = null;
  $("revRk").textContent = "";
  try { await navigator.clipboard.writeText(""); } catch {}
  await goHome(session, kind);
};

// ---- onboarding ------------------------------------------------------------
$("btnNewPassword").onclick = () => { $("cpw1").value = $("cpw2").value = ""; $("cpwErr").textContent = ""; show("secCreatePw"); };
$("btnImport").onclick = () => { $("impRk").value = $("ipw1").value = ""; $("impErr").textContent = ""; show("secImport"); };
$("btnCreateBack").onclick = () => route();
$("btnImportBack").onclick = () => route();
// Forgot password / lost device / passkey: re-import via recovery key.
$("btnForgot").onclick = () => {
  $("impRk").value = ""; $("ipw1").value = ""; $("impErr").textContent = "";
  show("secImport");
};

// create with passkey (same passkey as morm.one)
$("btnNewPasskey").onclick = async () => {
  $("onboardErr").textContent = "";
  if (!webauthnSupported()) return void ($("onboardErr").textContent = "この環境はパスキーに非対応です。パスワードをご利用ください。");
  $("btnNewPasskey").disabled = true;
  let seed;
  try {
    const gen = await newSeedWithRecovery(); seed = gen.seed;
    const { credId, prf } = await createPasskey();
    await protectWithPRF(store, seed, prf, bytesToB64u(credId));
    const session = await sessionForSeed(seed);
    startReveal(gen.recoveryKey, session, "パスキー保護");
  } catch (e) {
    $("onboardErr").textContent = "パスキー作成に失敗: " + String(e.message || e);
  } finally {
    if (seed) seed.fill(0);
    $("btnNewPasskey").disabled = false;
  }
};

// ---- create with password --------------------------------------------------
$("btnCreateGo").onclick = async () => {
  const p1 = $("cpw1").value, p2 = $("cpw2").value;
  if (p1.length < 8) return void ($("cpwErr").textContent = "パスワードは8文字以上");
  if (p1 !== p2) return void ($("cpwErr").textContent = "パスワードが一致しません");
  $("cpwErr").textContent = "";
  let seed;
  try {
    const gen = await newSeedWithRecovery(); seed = gen.seed;
    await protectSeedWithPassword(store, seed, p1);
    const session = await sessionForSeed(seed);
    $("cpw1").value = $("cpw2").value = "";
    startReveal(gen.recoveryKey, session, "パスワード保護");
  } catch (e) { $("cpwErr").textContent = String(e.message || e); }
  finally { if (seed) seed.fill(0); }
};

// ---- import ----------------------------------------------------------------
async function importWith(protect, kindLabel) {
  const rk = $("impRk").value.trim();
  if (!rk) return void ($("impErr").textContent = "リカバリーキーを入力してください");
  $("impErr").textContent = "";
  let seed;
  try {
    seed = seedFromRecovery(rk);
  } catch (e) {
    return void ($("impErr").textContent = "リカバリーキーが不正です");
  }
  try {
    await protect(seed);
    const session = await sessionForSeed(seed);
    $("impRk").value = ""; $("ipw1").value = "";
    await goHome(session, kindLabel);
  } catch (e) {
    $("impErr").textContent = "復元に失敗: " + String(e.message || e);
  } finally { seed.fill(0); }
}
$("btnImpPasskey").onclick = async () => {
  if (!webauthnSupported()) return void ($("impErr").textContent = "この環境はパスキーに非対応です。");
  await importWith(async (seed) => {
    const { credId, prf } = await createPasskey();
    await protectWithPRF(store, seed, prf, bytesToB64u(credId));
  }, "パスキー保護");
};
$("btnImpPassword").onclick = async () => {
  const pw = $("ipw1").value;
  if (pw.length < 8) return void ($("impErr").textContent = "パスワードは8文字以上");
  await importWith((seed) => protectSeedWithPassword(store, seed, pw), "パスワード保護");
};

// ---- bridge (L1 -> Base, BRIDGE_BURN kind 21) ------------------------------
let bridgeCtx = null; // { evm, amountBase (BigInt), amountDisplay }

function resetBridge() {
  bridgeCtx = null;
  $("brInput").style.display = currentAcc?.evmAddress ? "block" : "none";
  $("brConfirm").style.display = "none";
  $("brResult").style.display = "none";
  $("brAmt").value = "";
  $("brErr").textContent = ""; $("brcfErr").textContent = "";
}
$("btnBridgeMore").onclick = () => { resetBridge(); refreshBalance(); };
$("btnBridgeCancel").onclick = () => { $("brConfirm").style.display = "none"; syncBridgeEvm(); };

$("btnBridgeReview").onclick = async () => {
  $("brErr").textContent = "";
  const amtStr = $("brAmt").value.trim();
  const evm = currentAcc?.evmAddress;
  if (!evm) return void ($("brErr").textContent = "先に Base アドレスを連携してください");
  if (!amtStr) return void ($("brErr").textContent = "金額を入力してください");
  try {
    const acc = await getAccountState(API_BASE, currentAddress);
    currentAcc = acc;
    const base = acc.baseUnitsPerMorm || 1;
    const amountBase = mormToBaseUnits(amtStr, base);
    if (BigInt(acc.chain?.balance ?? 0) < amountBase) {
      return void ($("brErr").textContent = "残高が不足しています");
    }
    bridgeCtx = { evm, amountBase, amountDisplay: formatBaseUnits(amountBase, base) };
    $("brcfTo").textContent = evm;
    $("brcfAmt").textContent = `${bridgeCtx.amountDisplay} MORM → wMORM`;
    $("brcfErr").textContent = "";
    $("brInput").style.display = "none";
    $("brConfirm").style.display = "block";
  } catch (e) { $("brErr").textContent = String(e.message || e); }
};

$("btnBridgeGo").onclick = async () => {
  if (!bridgeCtx) return;
  $("brcfErr").textContent = "送信中…";
  $("btnBridgeGo").disabled = true;
  let seed;
  try {
    const session = await bgSend({ type: "getSession" });
    if (!session?.seedHex) throw new Error("ロックされています。解錠し直してください");
    const acc = await getAccountState(API_BASE, currentAddress);
    const nonce = Number(acc.chain?.nonce ?? 0);
    const body = buildBridgeBurn({ senderPubkeyHex: session.pubkeyHex, nonce, amount: bridgeCtx.amountBase, evmRecipient: bridgeCtx.evm });
    seed = hexToBytes(session.seedHex);
    const signed = await signTx(body, seed);
    const res = await submitBridgeBurn(API_BASE, signed);
    $("brHash").textContent = res.txHash || res.tx_hash || "(受理)";
    $("brConfirm").style.display = "none";
    $("brResult").style.display = "block";
  } catch (e) {
    $("brcfErr").textContent = "ブリッジ失敗: " + String(e.message || e);
  } finally {
    if (seed) seed.fill(0);
    $("btnBridgeGo").disabled = false;
  }
};

// ---- unlock / lock ---------------------------------------------------------
$("btnUnlock").onclick = async () => {
  try {
    const s = await unlockWithPassword(store, $("upw").value);
    $("upw").value = ""; $("upwErr").textContent = "";
    await goHome(s, "パスワード保護");
  } catch (e) { $("upwErr").textContent = String(e.message || e); }
};
$("btnUnlockPasskey").onclick = async () => {
  $("upwErr").textContent = "";
  try {
    const rec = await loadRecord(store);
    const prf = await passkeyPRF(b64uToBytes(rec.credIdB64u));
    if (!prf) throw new Error("パスキーから鍵を取得できませんでした");
    const s = await unlockWithPRF(store, prf);
    await goHome(s, "パスキー保護");
  } catch (e) { $("upwErr").textContent = "解錠に失敗: " + String(e.message || e); }
};
$("btnLock").onclick = async () => { await bgSend({ type: "lock" }); await route(); };

// ---- password show/hide toggles -------------------------------------------
document.querySelectorAll("button.eye").forEach((btn) => {
  btn.onclick = () => {
    const inp = document.getElementById(btn.dataset.for);
    const reveal = inp.type === "password";
    inp.type = reveal ? "text" : "password";
    btn.textContent = reveal ? "🙈" : "👁";
    btn.setAttribute("aria-pressed", String(reveal));
    inp.focus();
  };
});

route();
