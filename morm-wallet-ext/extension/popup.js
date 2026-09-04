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
  getAccountState, resolveHandle, submitTransfer, submitBridgeBurn, getNodes, getHistory,
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

// Transient success/info toast.
let _toastTimer = null;
function toast(msg) {
  const t = $("toast");
  if (!t) return;
  t.textContent = msg;
  t.classList.add("show");
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
}
// Unlocked session lives in chrome.storage.session (RAM only, never disk,
// cleared when the browser closes) so it survives MV3 service-worker eviction —
// unlike an in-SW variable, which vanishes after ~30s idle and caused
// "ロックされています" at sign time. Idle auto-lock via a lockAt timestamp.
const SESSION_KEY = "session";
const IDLE_MS = 5 * 60 * 1000;
async function sessionGet() {
  try {
    const o = await chrome.storage.session.get(SESSION_KEY);
    const s = o[SESSION_KEY];
    if (!s) return null;
    if (Date.now() > s.lockAt) { await chrome.storage.session.remove(SESSION_KEY); return null; }
    return s;
  } catch { return null; }
}
async function sessionSet(sess) {
  await chrome.storage.session.set({ [SESSION_KEY]: { ...sess, lockAt: Date.now() + IDLE_MS } });
}
async function sessionClear() { try { await chrome.storage.session.remove(SESSION_KEY); } catch {} }

let currentAddress = null;
let currentAcc = null; // last fetched account state (balance/nonce/evmAddress/baseUnitsPerMorm)
let currentKdf = null; // "pbkdf2" | "prf" — how the stored seed is protected

// Reflect / update the "protection method" control on the home screen. The
// switch re-encrypts the CURRENTLY UNLOCKED seed (from the session) with the
// other method — no recovery key needed.
async function refreshProtection() {
  const rec = await loadRecord(store);
  currentKdf = rec?.kdf || null;
  $("protMethod").textContent = "保護: " + (currentKdf === "prf" ? "パスキー" : "パスワード");
  $("btnSwitchProt").textContent = currentKdf === "prf" ? "パスワードに切り替え" : "パスキーに切り替え";
  $("switchPwForm").style.display = "none";
  $("spw1").value = ""; $("spw2").value = "";
}

async function goHome(session, kindLabel) {
  await sessionSet(session);
  currentAddress = session.address;
  $("homeAddr").textContent = session.address;
  $("homeKind").textContent = kindLabel || "";
  resetSend();
  show("secHome");
  refreshBalance();
  refreshProtection();
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
  $("tabHistory").classList.toggle("on", which === "history");
  $("viewSend").style.display = which === "send" ? "block" : "none";
  $("viewBridge").style.display = which === "bridge" ? "block" : "none";
  $("viewNode").style.display = which === "node" ? "block" : "none";
  $("viewHistory").style.display = which === "history" ? "block" : "none";
  if (which === "bridge") syncBridgeEvm();
  if (which === "node") loadNodes();
  if (which === "history") loadHistory();
}
$("tabSend").onclick = () => setTab("send");
$("tabBridge").onclick = () => setTab("bridge");
$("tabNode").onclick = () => setTab("node");
$("tabHistory").onclick = () => setTab("history");

// ---- history view ----------------------------------------------------------
function shortAddr(a) { return typeof a === "string" && a.length > 14 ? a.slice(0, 8) + "…" + a.slice(-4) : (a || "—"); }
async function loadHistory() {
  if (!currentAddress) return;
  $("histMsg").textContent = "読み込み中…";
  $("histList").innerHTML = "";
  try {
    const d = await getHistory(API_BASE, currentAddress);
    const base = currentAcc?.baseUnitsPerMorm || 1;
    if (!d.items?.length) { $("histMsg").textContent = "取引履歴はまだありません。"; return; }
    $("histMsg").textContent = "";
    $("histList").innerHTML = d.items.map((it) => {
      const io = it.direction === "in";
      const sign = io ? "+" : "−";
      const when = (it.at || "").slice(0, 16).replace("T", " ");
      return `<div class="hist">
        <div><div class="amt ${io ? "in" : "out"}">${sign}${formatBaseUnits(it.amount, base)} MORM</div>
        <div class="muted">${esc(it.kind || "transfer")} · ${esc(when)}</div></div>
        <div class="cp">${io ? "from" : "to"} ${esc(shortAddr(it.counterparty))}</div>
      </div>`;
    }).join("");
  } catch (e) { $("histMsg").textContent = "取得失敗: " + String(e.message || e); }
}
$("btnHistRefresh").onclick = loadHistory;

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
// B1: bind this wallet as the node reward address via node.morm.one (member sets
// reward-address = this m0r). Copy the address, then open node.morm.one.
$("btnCopyMorm").onclick = async () => {
  try { await navigator.clipboard.writeText(currentAddress || ""); $("nodeConnectMsg").textContent = "node.morm.one の報酬アドレス欄に貼り付けてください。"; toast("m0r をコピーしました"); }
  catch { $("nodeConnectMsg").textContent = "コピーできませんでした。"; }
};
$("btnOpenNode").onclick = () => window.open(NODE_BASE, "_blank");

// ---- switch protection method (password <-> passkey) -----------------------
$("btnSwitchProt").onclick = async () => {
  $("protMsg").textContent = "";
  if (currentKdf === "prf") {
    // -> password: reveal the inline form (needs a new password).
    $("switchPwForm").style.display = "block";
    return;
  }
  // -> passkey: re-encrypt the current seed with a passkey (no recovery key).
  const session = await sessionGet();
  if (!session?.seedHex) return void ($("protMsg").textContent = "ロックされています。解錠し直してください");
  await sessionSet(session);
  $("btnSwitchProt").disabled = true;
  let seed;
  try {
    seed = hexToBytes(session.seedHex);
    const { credId, prf } = await createPasskey();
    await protectWithPRF(store, seed, prf, bytesToB64u(credId));
    await refreshProtection();
    $("protMsg").textContent = "パスキー保護に切り替えました。"; toast("パスキー保護に切り替えました");
  } catch (e) {
    $("protMsg").textContent = "切り替え失敗: " + String(e.message || e);
  } finally {
    if (seed) seed.fill(0);
    $("btnSwitchProt").disabled = false;
  }
};
$("btnSwitchPwCancel").onclick = () => { $("switchPwForm").style.display = "none"; $("spw1").value = ""; $("spw2").value = ""; };
$("btnSwitchPwGo").onclick = async () => {
  const p1 = $("spw1").value, p2 = $("spw2").value;
  if (p1.length < 8) return void ($("protMsg").textContent = "パスワードは8文字以上");
  if (p1 !== p2) return void ($("protMsg").textContent = "パスワードが一致しません");
  const session = await sessionGet();
  if (!session?.seedHex) return void ($("protMsg").textContent = "ロックされています。解錠し直してください");
  await sessionSet(session);
  let seed;
  try {
    seed = hexToBytes(session.seedHex);
    await protectSeedWithPassword(store, seed, p1);
    await refreshProtection();
    $("protMsg").textContent = "パスワード保護に切り替えました。"; toast("パスワード保護に切り替えました");
  } catch (e) {
    $("protMsg").textContent = "切り替え失敗: " + String(e.message || e);
  } finally {
    if (seed) seed.fill(0);
  }
};

// ---- Base handoffs ---------------------------------------------------------
$("btnSwapHO").onclick = () => window.open(MARKET_URL, "_blank");
$("btnDepositHO").onclick = () => window.open(MARKET_URL, "_blank");
$("btnLinkEvm").onclick = () => window.open(LINK_EVM_URL, "_blank");
$("btnRefresh").onclick = refreshBalance;
$("btnCopyAddr").onclick = async () => {
  try { await navigator.clipboard.writeText(currentAddress || ""); toast("アドレスをコピーしました"); }
  catch { toast("コピーできませんでした"); }
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
    const session = await sessionGet();
    if (!session?.seedHex) throw new Error("ロックされています。解錠し直してください");
    await sessionSet(session); // touch: extend idle lock on activity
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
    toast("送信しました ✓");
  } catch (e) {
    $("cfErr").textContent = "送信失敗: " + String(e.message || e);
  } finally {
    if (seed) seed.fill(0);
    $("btnSendGo").disabled = false;
  }
};

// ---- routing ---------------------------------------------------------------
async function route() {
  const s = await sessionGet();
  if (s && s.address) {
    currentAddress = s.address;
    $("homeAddr").textContent = s.address;
    resetSend();
    show("secHome");
    refreshBalance();
    refreshProtection();
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
    const session = await sessionGet();
    if (!session?.seedHex) throw new Error("ロックされています。解錠し直してください");
    await sessionSet(session); // touch: extend idle lock on activity
    const acc = await getAccountState(API_BASE, currentAddress);
    const nonce = Number(acc.chain?.nonce ?? 0);
    const body = buildBridgeBurn({ senderPubkeyHex: session.pubkeyHex, nonce, amount: bridgeCtx.amountBase, evmRecipient: bridgeCtx.evm });
    seed = hexToBytes(session.seedHex);
    const signed = await signTx(body, seed);
    const res = await submitBridgeBurn(API_BASE, signed);
    $("brHash").textContent = res.txHash || res.tx_hash || "(受理)";
    $("brConfirm").style.display = "none";
    $("brResult").style.display = "block";
    toast("ブリッジを送信しました ✓");
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
$("btnLock").onclick = async () => { await sessionClear(); await route(); };

// ---- password show/hide toggles -------------------------------------------
document.querySelectorAll("button.eye").forEach((btn) => {
  btn.onclick = () => {
    const inp = document.getElementById(btn.dataset.for);
    const reveal = inp.type === "password";
    inp.type = reveal ? "text" : "password";
    btn.textContent = reveal ? "隠す" : "表示";
    btn.setAttribute("aria-pressed", String(reveal));
    inp.focus();
  };
});

route();
