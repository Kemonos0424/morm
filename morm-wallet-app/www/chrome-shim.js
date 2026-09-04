// chrome.* shim for the mobile app. The wallet UI (popup.js/wallet.js) is reused
// verbatim from the extension; only its storage substrate differs:
//   chrome.storage.local  -> iOS Keychain / Android Keystore via
//                            capacitor-secure-storage-plugin when running in the
//                            app (hardware-encrypted, device-lock bound); falls
//                            back to Capacitor Preferences, then localStorage
//                            (for a plain browser during dev).
//   chrome.storage.session-> in-memory (RAM only; gone when the app is killed).
// The stored value is already AES-GCM ciphertext (the seed is encrypted with the
// user's password/passkey before it ever reaches storage); the Keychain adds a
// second, hardware-backed layer.
// Loaded BEFORE popup.js so `window.chrome` exists when the module runs.
(function () {
  var P = (window.Capacitor && window.Capacitor.Plugins) || {};
  var SS = P.SecureStoragePlugin || null;   // Keychain / Keystore
  var Prefs = P.Preferences || null;         // UserDefaults / SharedPreferences

  // --- chrome.storage.local (callback style, as popup.js's store adapter uses) ---
  var local;
  if (SS) {
    local = {
      // SecureStoragePlugin.get REJECTS when the key is absent -> treat as empty.
      get: function (k, cb) {
        SS.get({ key: k }).then(function (r) {
          var o = {}; try { o[k] = JSON.parse(r.value); } catch (e) {} cb(o);
        }).catch(function () { cb({}); });
      },
      set: function (obj, cb) {
        Promise.all(Object.keys(obj).map(function (k) {
          return SS.set({ key: k, value: JSON.stringify(obj[k]) });
        })).then(function () { cb && cb(); }).catch(function () { cb && cb(); });
      },
      remove: function (k, cb) {
        SS.remove({ key: k }).then(function () { cb && cb(); }).catch(function () { cb && cb(); });
      }
    };
  } else if (Prefs) {
    local = {
      get: function (k, cb) { Prefs.get({ key: k }).then(function (r) { var o = {}; if (r && r.value != null) { try { o[k] = JSON.parse(r.value); } catch (e) {} } cb(o); }); },
      set: function (obj, cb) { Promise.all(Object.keys(obj).map(function (k) { return Prefs.set({ key: k, value: JSON.stringify(obj[k]) }); })).then(function () { cb && cb(); }); },
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
