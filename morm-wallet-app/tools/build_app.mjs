// Assemble www/ for the Capacitor app by reusing the extension's web assets
// verbatim (popup.js/wallet.js/passkey.js/config.js/walletcore/icons) and
// generating index.html from popup.html with the chrome-shim injected and a
// mobile-responsive layout. Run: node tools/build_app.mjs
import { cpSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const ext = join(root, "..", "morm-wallet-ext");
const extWeb = join(ext, "extension");
const www = join(root, "www");

// Ensure wallet-core is built into the extension (walletcore/ is gitignored).
execSync("node tools/build_ext.mjs", { cwd: ext, stdio: "ignore" });

// Reuse the extension's JS/assets verbatim.
for (const f of ["popup.js", "wallet.js", "passkey.js", "config.js", "qr.min.js"]) {
  cpSync(join(extWeb, f), join(www, f));
}
cpSync(join(extWeb, "walletcore"), join(www, "walletcore"), { recursive: true });
cpSync(join(extWeb, "icons"), join(www, "icons"), { recursive: true });

// index.html = popup.html + chrome-shim (before popup.js) + mobile layout.
let html = readFileSync(join(extWeb, "popup.html"), "utf8");

// App viewport: disable pinch/double-tap zoom and the input-focus auto-zoom
// (native apps don't zoom the whole UI); handle the notch with viewport-fit.
html = html.replace(
  '<meta name="viewport" content="width=device-width, initial-scale=1" />',
  '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover" />'
);

// Mobile layout: the extension fixes body width:340px; make it responsive.
const mobileCss = `
  <style>
    /* mobile app overrides (Capacitor) */
    body { width: 100% !important; max-width: 520px; margin: 0 auto; min-height: 100vh;
           padding-top: max(18px, env(safe-area-inset-top)); }
    html, body { -webkit-text-size-adjust: 100%; }
    /* >=16px inputs stop iOS from zooming when a field is focused */
    input, select, textarea { font-size: 16px; }
    /* no grey tap flash / long-press callout on an app-like UI */
    * { -webkit-tap-highlight-color: transparent; -webkit-touch-callout: none; }
  </style>`;
html = html.replace("</style>", "</style>" + mobileCss);

// Load the shim before the popup module so window.chrome exists.
html = html.replace(
  '<script type="module" src="popup.js"></script>',
  '<script src="chrome-shim.js"></script>\n  <script type="module" src="popup.js"></script>'
);

writeFileSync(join(www, "index.html"), html);

if (!existsSync(join(www, "chrome-shim.js"))) {
  throw new Error("www/chrome-shim.js missing — it must be committed alongside this tool.");
}
console.log("built www/ from extension (reused popup/wallet/passkey/walletcore + shim + mobile layout)");
