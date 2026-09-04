// chrome.* shim for the mobile app. The wallet UI (popup.js/wallet.js) is reused
// verbatim from the extension; only its storage substrate differs:
//   chrome.storage.local  -> Capacitor Preferences (persistent, native secure-ish
//                            store) when running in the app; localStorage in a
//                            plain browser (for dev/testing).
//   chrome.storage.session-> in-memory (RAM only; gone when the app is killed),
//                            matching the extension's session semantics.
// Loaded BEFORE popup.js so `window.chrome` exists when the module runs.
(function () {
  var Prefs = (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Preferences) || null;

  // --- chrome.storage.local (callback style, as popup.js's store adapter uses) ---
  var local;
  if (Prefs) {
    local = {
      get: function (k, cb) { Prefs.get({ key: k }).then(function (r) { var o = {}; if (r && r.value != null) { try { o[k] = JSON.parse(r.value); } catch (e) {} } cb(o); }); },
      set: function (obj, cb) { var ks = Object.keys(obj); Promise.all(ks.map(function (k) { return Prefs.set({ key: k, value: JSON.stringify(obj[k]) }); })).then(function () { cb && cb(); }); },
      remove: function (k, cb) { Prefs.remove({ key: k }).then(function () { cb && cb(); }); }
    };
  } else {
    local = {
      get: function (k, cb) { try { var v = localStorage.getItem('kv:' + k); var o = {}; if (v != null) o[k] = JSON.parse(v); cb(o); } catch (e) { cb({}); } },
      set: function (obj, cb) { try { Object.keys(obj).forEach(function (k) { localStorage.setItem('kv:' + k, JSON.stringify(obj[k])); }); } catch (e) {} cb && cb(); },
      remove: function (k, cb) { try { localStorage.removeItem('kv:' + k); } catch (e) {} cb && cb(); }
    };
  }

  // --- chrome.storage.session (async style) : in-memory only ---
  var _sess = {};
  var session = {
    get: function (k) { var o = {}; if (k in _sess) o[k] = _sess[k]; return Promise.resolve(o); },
    set: function (obj) { Object.keys(obj).forEach(function (k) { _sess[k] = obj[k]; }); return Promise.resolve(); },
    remove: function (k) { delete _sess[k]; return Promise.resolve(); }
  };

  window.chrome = window.chrome || {};
  window.chrome.storage = { local: local, session: session };
  window.chrome.runtime = window.chrome.runtime || { lastError: null, sendMessage: function (m, cb) { cb && cb({}); } };
})();
