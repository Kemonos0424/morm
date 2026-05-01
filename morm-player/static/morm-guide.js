// MORM onboarding guide — sequential modal walkthrough.
//
// Each page registers a `pageKey` ("upload" / "player" / "wallet") and a
// list of step ids (e.g. ['guide.upload.0', 'guide.upload.1', ...]). On
// first visit (no `morm-guide-seen-v1` localStorage marker for that key),
// the guide auto-opens. The user can: Next/Prev between steps, Skip, or
// check "Don't show again" before clicking Got it. A small "?" pill in
// the topbar re-triggers the guide on demand.
//
// Strings come from morm-i18n.js — every step id maps to two keys:
//   `<id>.title` → modal title
//   `<id>.body`  → modal paragraph
//
// Language toggle inside the guide is automatic: the modal listens to
// `morm-lang-changed` events and rewrites the visible step text.

import { t, currentLang } from '/static/morm-i18n.js';

const SEEN_KEY = 'morm-guide-seen-v1';

function _seenSet() {
  try {
    const raw = localStorage.getItem(SEEN_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch { return new Set(); }
}
function _markSeen(pageKey) {
  const s = _seenSet(); s.add(pageKey);
  try { localStorage.setItem(SEEN_KEY, JSON.stringify([...s])); } catch {}
}

/** Show a modal walkthrough of `steps` for the given `pageKey`. Resolves
 * to `'done'`, `'skip'`, or `'dismiss'`. The caller does not usually
 * await the result — this is fire-and-forget. */
export function showGuide(pageKey, stepIds) {
  return new Promise(resolve => {
    let idx = 0;
    let dontShow = false;

    const overlay = document.createElement('div');
    overlay.style.cssText = `
      position: fixed; inset: 0; background: rgba(0,0,0,0.78);
      display: flex; align-items: center; justify-content: center;
      z-index: 99998; font-family: -apple-system, BlinkMacSystemFont, sans-serif;
      padding: 20px;
    `;
    const box = document.createElement('div');
    box.style.cssText = `
      background: #11151b; color: #e6e9ee;
      border: 1px solid #4dd2ff; border-radius: 14px;
      padding: 22px; max-width: 460px; width: 100%;
      box-shadow: 0 0 28px rgba(77,210,255,0.35);
      max-height: 85vh; overflow-y: auto;
    `;

    // Top — step counter + skip
    const top = document.createElement('div');
    top.style.cssText =
      'display:flex; justify-content:space-between; align-items:center; ' +
      'margin-bottom: 14px;';
    const counter = document.createElement('span');
    counter.style.cssText =
      'color:#6a7a90; font-size:11px; font-family: monospace; ' +
      'letter-spacing: 0.04em; text-transform: uppercase;';
    const skip = document.createElement('button');
    skip.style.cssText =
      'background: transparent; color: #6a7a90; border: 1px solid #3a4150;' +
      'border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 11px;';
    top.appendChild(counter); top.appendChild(skip);

    // Title + body
    const title = document.createElement('h3');
    title.style.cssText = 'margin: 0 0 12px; color: #4dd2ff; font-size: 18px;';
    const body = document.createElement('div');
    body.style.cssText =
      'font-size: 14px; line-height: 1.65; color: #e6e9ee; ' +
      'margin-bottom: 20px;';

    // Don't-show-again checkbox (only useful on the LAST step)
    const ackRow = document.createElement('label');
    ackRow.style.cssText =
      'display: flex; gap: 8px; align-items: center; margin-bottom: 14px; ' +
      'cursor: pointer; font-size: 12px; color: #6a7a90;';
    const ackBox = document.createElement('input');
    ackBox.type = 'checkbox';
    ackBox.style.cssText = 'width: 16px; height: 16px;';
    ackBox.onchange = () => { dontShow = ackBox.checked; };
    const ackTxt = document.createElement('span');
    ackRow.appendChild(ackBox); ackRow.appendChild(ackTxt);

    // Buttons
    const btnRow = document.createElement('div');
    btnRow.style.cssText =
      'display: flex; gap: 8px; justify-content: flex-end;';
    const prev = document.createElement('button');
    prev.style.cssText =
      'padding: 8px 14px; background: #2b2f37; color: #e6e9ee;' +
      'border: 1px solid #3a4150; border-radius: 6px; cursor: pointer; font-size: 13px;';
    const next = document.createElement('button');
    next.style.cssText =
      'padding: 8px 16px; background: #4dd2ff; color: #0a1218;' +
      'border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px;';
    btnRow.appendChild(prev); btnRow.appendChild(next);

    box.appendChild(top);
    box.appendChild(title);
    box.appendChild(body);
    box.appendChild(ackRow);
    box.appendChild(btnRow);
    overlay.appendChild(box);
    document.body.appendChild(overlay);

    function paint() {
      const id = stepIds[idx];
      counter.textContent = t('guide.step_of', { n: idx + 1, total: stepIds.length });
      skip.textContent = t('guide.skip');
      title.textContent = t(`${id}.title`);
      body.textContent = t(`${id}.body`);
      prev.textContent = t('guide.prev');
      ackTxt.textContent = t('guide.dont_show');
      ackRow.style.visibility = (idx === stepIds.length - 1) ? 'visible' : 'hidden';
      const isLast = idx === stepIds.length - 1;
      next.textContent = isLast ? t('guide.done') : t('guide.next');
      prev.disabled = (idx === 0);
      prev.style.opacity = prev.disabled ? '0.4' : '1';
      prev.style.cursor  = prev.disabled ? 'not-allowed' : 'pointer';
    }

    function done(reason) {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('morm-lang-changed', paint);
      overlay.remove();
      if (dontShow) _markSeen(pageKey);
      resolve(reason);
    }
    function onKey(e) {
      if (e.key === 'Escape') done('dismiss');
      else if (e.key === 'Enter') (idx === stepIds.length - 1 ? done('done') : (idx++, paint()));
      else if (e.key === 'ArrowLeft' && idx > 0) { idx--; paint(); }
      else if (e.key === 'ArrowRight' && idx < stepIds.length - 1) { idx++; paint(); }
    }

    skip.onclick = () => done('skip');
    prev.onclick = () => { if (idx > 0) { idx--; paint(); } };
    next.onclick = () => {
      if (idx === stepIds.length - 1) done('done');
      else { idx++; paint(); }
    };
    overlay.onclick = e => { if (e.target === overlay) done('dismiss'); };

    window.addEventListener('keydown', onKey);
    window.addEventListener('morm-lang-changed', paint);

    paint();
    setTimeout(() => next.focus(), 50);
  });
}

/** First-time auto-launch: only show the guide if `pageKey` hasn't been
 * marked seen. Returns the promise from showGuide, or undefined if
 * skipped. */
export function maybeShowFirstTimeGuide(pageKey, stepIds) {
  if (_seenSet().has(pageKey)) return undefined;
  return showGuide(pageKey, stepIds);
}

/** Mount a small "?" pill next to other topbar items that re-opens the
 * guide for the current page on click. Returns the element so the
 * caller can place it via appendChild / replace some placeholder. */
export function mountHelpButton(parent, pageKey, stepIds) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.textContent = t('guide.help_btn');
  btn.setAttribute('aria-label', t('guide.help_label'));
  btn.setAttribute('title', t('guide.help_label'));
  btn.style.cssText = `
    width: 22px; height: 22px;
    border-radius: 999px;
    background: transparent; color: #4dd2ff;
    border: 1px solid #4dd2ff;
    cursor: pointer; font-size: 12px; font-weight: 700;
    line-height: 0; padding: 0;
    pointer-events: auto;
  `;
  btn.onclick = () => showGuide(pageKey, stepIds);
  // Refresh aria-label/title when language flips so screen readers
  // pick up the localized hover hint.
  window.addEventListener('morm-lang-changed', () => {
    btn.setAttribute('aria-label', t('guide.help_label'));
    btn.setAttribute('title', t('guide.help_label'));
  });
  parent.appendChild(btn);
  return btn;
}

// Convenience: page step lists. Defined here so any page can reuse the
// same constants; the page just imports `STEPS.upload` etc.
export const STEPS = {
  upload: ['guide.upload.0', 'guide.upload.1', 'guide.upload.2', 'guide.upload.3'],
  player: ['guide.player.0', 'guide.player.1', 'guide.player.2'],
  wallet: ['guide.wallet.0', 'guide.wallet.1', 'guide.wallet.2'],
  swap:   ['guide.swap.0',   'guide.swap.1',   'guide.swap.2',   'guide.swap.3'],
};
