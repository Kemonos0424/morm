// Phase 25Vb upload + Phase 25-Video portrait camera-first creator UI.
//
// Flow:
//   idle → "Start camera" → live preview (9:16, MediaStream)
//   live → "Record"        → MediaRecorder fills a buffer
//   recording → "Stop"     → playback the captured Blob
//   captured → "Upload"    → POST /api/video/upload + poll job
//   uploaded → "Record again" → discards, back to live preview
//
// File drop is preserved as a small fallback below the primary action;
// dropping a file skips straight to the upload step.

import { listIdentities } from '/static/morm-identity.js';
import { t, mountLangToggle } from '/static/morm-i18n.js';
import { maybeShowFirstTimeGuide, mountHelpButton, STEPS } from '/static/morm-guide.js';

const $ = id => document.getElementById(id);
const cam      = $('cam');
const camEmpty = $('cam-empty');
const action   = $('action');
const recBadge = $('rec-badge');
const recTime  = $('rec-time');
const flipBtn  = $('cam-flip');
const discardBtn = $('cam-discard');
const dropEl   = $('drop');
const fileIn   = $('file');
const picked   = $('picked');
const prog     = $('prog');
const hud      = $('hud');
const joblog   = $('joblog');
const openFeed = $('open-feed');

let stream      = null;          // active MediaStream
let recorder    = null;          // MediaRecorder
let recChunks   = [];
let recStartAt  = 0;
let recTimerId  = null;
let captured    = null;          // {blob, mime}
let facing      = 'environment'; // start with rear camera; flip toggles
let mode        = 'idle';        // idle | live | recording | captured | uploading | done
let pollHandle  = null;

const TARGET_W = 1080;
const TARGET_H = 1920;
const MAX_RECORD_MS = 60_000;    // hard cap so the buffer can't grow without bound

// ---- identity HUD --------------------------------------------------------
async function refreshIdentity() {
  try {
    const ids = await listIdentities();
    $('ident-addr').textContent = ids[0]?.address || t('common.identity_unset');
  } catch {
    $('ident-addr').textContent = t('common.identity_unset');
  }
}
refreshIdentity();
// Mount the language toggle + help (?) button into the topbar before any
// text is rendered. The auto-launched guide depends on these slots.
mountLangToggle($('lang-toggle'));
mountHelpButton($('help-btn'), 'upload', STEPS.upload);
// Re-paint the action button when the language flips so the state-machine
// label refreshes immediately (other strings refresh via data-i18n).
window.addEventListener('morm-lang-changed', () => setMode(mode));
// First-time onboarding — walks through camera → record → upload → feed.
maybeShowFirstTimeGuide('upload', STEPS.upload);

// ---- helpers -------------------------------------------------------------
function fmtBytes(n) {
  if (!n && n !== 0) return '—';
  const u = ['B','KB','MB','GB'];
  let i = 0; let v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return v.toFixed(v < 10 && i > 0 ? 2 : 0) + ' ' + u[i];
}
function fmtElapsed(s) {
  if (s === null || s === undefined) return '—';
  return s < 60 ? s.toFixed(1) + 's' : (s/60).toFixed(2) + 'm';
}
function logLine(line, cls = '') {
  joblog.style.display = '';
  const span = document.createElement('span');
  span.className = cls;
  span.textContent = line + '\n';
  joblog.appendChild(span);
  joblog.scrollTop = joblog.scrollHeight;
}

// MediaRecorder MIME selection — prefer mp4/h264 (better compat with the
// FFmpeg encoder + smaller upload), fall back to webm/vp9 then vp8.
function pickRecorderMime() {
  const candidates = [
    'video/mp4;codecs=avc1.42E01E,mp4a.40.2',  // H.264 + AAC
    'video/mp4',
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
  ];
  for (const m of candidates) {
    if (typeof MediaRecorder === 'undefined') return null;
    if (MediaRecorder.isTypeSupported?.(m)) return m;
  }
  return null;
}
function extForMime(mime) {
  if (!mime) return 'webm';
  if (mime.startsWith('video/mp4')) return 'mp4';
  if (mime.startsWith('video/webm')) return 'webm';
  return 'bin';
}

// ---- camera lifecycle ----------------------------------------------------
async function startCamera() {
  if (stream) return;
  const constraints = {
    audio: true,
    video: {
      facingMode: { ideal: facing },
      // Phase 25-Video portrait — request 9:16 at HD.  Browsers may
      // negotiate down (e.g. desktop webcam = landscape sensor); the
      // FFmpeg pipeline crops to 9:16 anyway, so this is just a hint.
      width:  { ideal: TARGET_W },
      height: { ideal: TARGET_H },
      aspectRatio: { ideal: 9 / 16 },
    },
  };
  try {
    stream = await navigator.mediaDevices.getUserMedia(constraints);
  } catch (e) {
    logLine(t('upload.cam_err', { err: e.message }), 'err');
    setMode('idle');
    return;
  }
  cam.srcObject = stream;
  camEmpty.style.display = 'none';
  flipBtn.disabled = false;
  setMode('live');
}
function stopCamera() {
  if (recorder && recorder.state !== 'inactive') {
    try { recorder.stop(); } catch {}
  }
  if (stream) {
    for (const t of stream.getTracks()) t.stop();
    stream = null;
  }
  cam.srcObject = null;
}

async function flipCamera() {
  facing = (facing === 'user') ? 'environment' : 'user';
  stopCamera();
  await startCamera();
}

// ---- recording -----------------------------------------------------------
function startRecording() {
  if (!stream) return;
  const mime = pickRecorderMime();
  if (!mime) {
    logLine(t('upload.unsupported'), 'err');
    return;
  }
  recChunks = [];
  recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 4_000_000 });
  recorder.ondataavailable = e => { if (e.data && e.data.size) recChunks.push(e.data); };
  recorder.onstop = () => {
    const blob = new Blob(recChunks, { type: mime });
    captured = { blob, mime, durationMs: Date.now() - recStartAt };
    // swap preview to playback the captured clip so the user can confirm
    cam.srcObject = null;
    cam.muted = false;
    cam.controls = true;
    cam.src = URL.createObjectURL(blob);
    cam.loop = true;
    cam.play().catch(() => {});
    setMode('captured');
    logLine(t('upload.log.captured', {
      size: fmtBytes(blob.size),
      sec:  (captured.durationMs/1000).toFixed(1),
      mime,
    }), 'ok');
  };
  recorder.start(250);   // 250ms timeslice — keeps memory in line for long captures
  recStartAt = Date.now();
  recBadge.classList.add('on');
  setMode('recording');
  recTimerId = setInterval(() => {
    const s = Math.floor((Date.now() - recStartAt) / 1000);
    recTime.textContent = `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
    if (Date.now() - recStartAt > MAX_RECORD_MS) stopRecording();
  }, 200);
}
function stopRecording() {
  if (recTimerId) { clearInterval(recTimerId); recTimerId = null; }
  recBadge.classList.remove('on');
  if (recorder && recorder.state !== 'inactive') {
    try { recorder.stop(); } catch {}
  }
}

function discardCapture() {
  if (captured?.blob) try { URL.revokeObjectURL(cam.src); } catch {}
  captured = null;
  cam.removeAttribute('src'); cam.controls = false; cam.muted = true; cam.loop = false;
  // restart live preview from the existing stream
  if (stream) cam.srcObject = stream;
  setMode(stream ? 'live' : 'idle');
}

// ---- upload --------------------------------------------------------------
function uploadWithProgress(file, filename, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const url = `/api/video/upload?filename=${encodeURIComponent(filename)}`;
    xhr.open('POST', url);
    xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
    xhr.upload.onprogress = e => {
      if (e.lengthComputable && onProgress) onProgress((e.loaded / e.total) * 100);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)); }
        catch (e2) { reject(new Error('bad json: ' + e2.message)); }
      } else {
        reject(new Error(`HTTP ${xhr.status}: ${xhr.responseText.slice(0, 200)}`));
      }
    };
    xhr.onerror = () => reject(new Error('network error'));
    xhr.send(file);
  });
}

async function upload(blob, filename) {
  setMode('uploading');
  prog.style.display = 'block'; prog.value = 0;
  hud.style.display = ''; joblog.style.display = '';
  $('job-bytes').textContent = fmtBytes(blob.size);
  try {
    const t0 = performance.now();
    const job = await uploadWithProgress(blob, filename, p => { prog.value = p; });
    const ms = performance.now() - t0;
    logLine(t('upload.log.uploaded', { sec: (ms/1000).toFixed(1), id: job.job_id }), 'ok');
    $('job-id').textContent = job.job_id;
    $('job-state').textContent = job.state;
    pollJob(job.job_id);
  } catch (e) {
    logLine(t('upload.log.upload_fail', { err: e.message }), 'err');
    setMode('captured');   // let the user retry
  }
}

function pollJob(jobId) {
  if (pollHandle) clearInterval(pollHandle);
  let lastTail = -1;
  pollHandle = setInterval(async () => {
    try {
      const r = await fetch(`/api/video/job/${jobId}`);
      if (!r.ok) { logLine(`status ${r.status}`); return; }
      const st = await r.json();
      $('job-state').textContent = st.state;
      $('job-files').textContent = st.files_out || '—';
      $('job-cid').textContent = st.content_id || '—';
      if (st.started_at) {
        const fin = st.finished_at || (Date.now() / 1000);
        $('job-elapsed').textContent = fmtElapsed(fin - st.started_at);
      }
      if (st.log_tail && st.log_tail.length > lastTail + 1) {
        for (let i = Math.max(0, lastTail + 1); i < st.log_tail.length; i++) {
          logLine(st.log_tail[i]);
        }
        lastTail = st.log_tail.length - 1;
      }
      if (st.state === 'done' || st.state === 'error') {
        clearInterval(pollHandle); pollHandle = null;
        if (st.state === 'done' && st.content_id) {
          openFeed.href = `/player-hls?cid=${st.content_id}`;
          openFeed.textContent = t('upload.feed_link', { cid: st.content_id.slice(0, 12) });
          logLine(t('upload.log.done'), 'ok');
          setMode('done');
        } else if (st.error) {
          logLine(t('upload.log.err', { err: st.error }), 'err');
          setMode('captured');
        }
      }
    } catch (e) {
      logLine(t('upload.log.poll_fail', { err: e.message }), 'err');
    }
  }, 800);
}

// ---- mode/UI state machine ----------------------------------------------
function setMode(next) {
  mode = next;
  switch (mode) {
    case 'idle':
      action.textContent = t('upload.action.idle');
      action.classList.remove('rec'); action.disabled = false;
      flipBtn.disabled = true; discardBtn.disabled = true;
      camEmpty.style.display = '';
      break;
    case 'live':
      action.textContent = t('upload.action.live');
      action.classList.add('rec'); action.disabled = false;
      flipBtn.disabled = false; discardBtn.disabled = true;
      camEmpty.style.display = 'none';
      break;
    case 'recording':
      action.textContent = t('upload.action.recording');
      action.classList.add('rec'); action.disabled = false;
      flipBtn.disabled = true; discardBtn.disabled = true;
      break;
    case 'captured':
      action.textContent = t('upload.action.captured');
      action.classList.remove('rec'); action.disabled = false;
      flipBtn.disabled = true; discardBtn.disabled = false;
      break;
    case 'uploading':
      action.textContent = t('upload.action.uploading');
      action.classList.remove('rec'); action.disabled = true;
      flipBtn.disabled = true; discardBtn.disabled = true;
      break;
    case 'done':
      action.textContent = t('upload.action.done');
      action.classList.remove('rec'); action.disabled = false;
      flipBtn.disabled = true; discardBtn.disabled = false;
      break;
  }
}

action.addEventListener('click', async () => {
  if (mode === 'idle') return startCamera();
  if (mode === 'live') return startRecording();
  if (mode === 'recording') return stopRecording();
  if (mode === 'captured') {
    const ext = extForMime(captured.mime);
    return upload(captured.blob, `clip-${Date.now()}.${ext}`);
  }
  if (mode === 'done') return discardCapture();
});
flipBtn.addEventListener('click', flipCamera);
discardBtn.addEventListener('click', discardCapture);

// ---- file fallback -------------------------------------------------------
dropEl.addEventListener('dragover', e => { e.preventDefault(); dropEl.classList.add('hi'); });
dropEl.addEventListener('dragleave', () => dropEl.classList.remove('hi'));
dropEl.addEventListener('drop', e => {
  e.preventDefault(); dropEl.classList.remove('hi');
  const f = e.dataTransfer?.files?.[0];
  if (f) { picked.textContent = `${f.name} · ${fmtBytes(f.size)}`; upload(f, f.name); }
});
fileIn.addEventListener('change', () => {
  const f = fileIn.files?.[0];
  if (f) { picked.textContent = `${f.name} · ${fmtBytes(f.size)}`; upload(f, f.name); }
});

// Initial state — no camera yet, no file picked.
setMode('idle');
