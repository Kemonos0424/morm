// Copy @morm/wallet-core src into extension/walletcore/ so the MV3 popup can
// import it directly (no bundler; MV3 supports ES modules). Run: node tools/build_ext.mjs
import { cpSync, rmSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "packages", "wallet-core", "src");
const dest = join(root, "extension", "walletcore");

rmSync(dest, { recursive: true, force: true });
mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true });
console.log(`copied wallet-core -> ${dest}`);
