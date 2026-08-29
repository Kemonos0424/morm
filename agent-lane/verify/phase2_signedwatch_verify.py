#!/usr/bin/env python3
"""Read a JS-signed 'watch' envelope from stdin and verify it with
play_server.verify_signed. Passing = JS canon() + Ed25519 exactly matches the
server's canonical() + ed25519_verify, so signed watch beacons will earn in prod."""
import os, sys, json, tempfile
os.environ.setdefault("CATALOG_DB", tempfile.mktemp(suffix="_swverify.db"))
sys.path.insert(0, "/Users/akihisayachida/Desktop/MORM/morm-play")
import play_server as ps

data = json.load(sys.stdin)
expected = data.pop("expected_addr")
m0r, payload = ps.verify_signed(data, "watch")
print("verify_signed ->", m0r, "| payload:", payload)
if not m0r:
    print("ASSERT FAILED: signature did not verify (JS canon != Python canonical):", payload); sys.exit(1)
if m0r != expected:
    print(f"ASSERT FAILED: recovered {m0r} != expected {expected}"); sys.exit(1)
print("OK: JS-signed watch verifies server-side; recovered m0r == signer address.")
print("=> view_by_other earning path is cross-language compatible.")
