"""morm-l1 — CLI for keygen, node-run, and tx submission."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from . import crypto
from .node import Node
from .rpc import Handler, RpcServer
from .tx import Transaction


def cmd_keygen(args):
    seed, pub = crypto.keygen()
    out = {
        "seed_hex": seed.hex(),
        "pubkey_hex": pub.hex(),
        "address": crypto.address(pub),
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_node(args):
    seed = bytes.fromhex(args.producer_seed)
    treasury = args.treasury
    explicit_peers = [p.strip() for p in (args.peers or "").split(",") if p.strip()]
    # Phase 30c: when --peers is empty we fall back to the federation
    # seed list (baked-in + local-mutable + discovery). The operator's
    # PUBLIC_URL env, if set, is filtered out so a node never lists itself.
    from .seed_loader import load_peer_urls
    seed_set = load_peer_urls(
        explicit_peers=explicit_peers,
        data_dir=Path(args.data_dir),
        public_url=os.environ.get("PUBLIC_URL"),
        enable_discovery=not getattr(args, "no_seed_discovery", False),
    )
    peers = seed_set.urls()
    if peers and explicit_peers:
        print(f"[seeds] explicit --peers in use ({len(peers)} entries)",
              file=sys.stderr)
    elif peers:
        src = ", ".join(f"{k}:{len(v)}" for k, v in seed_set.sources.items())
        print(f"[seeds] resolved {len(peers)} peers from federation list ({src})",
              file=sys.stderr)
    # Phase 25c: peers configured but --quic not set means no transport
    # exists for gossip. Reject early with a clear message instead of
    # silently dropping every block/tx fanout to those peers.
    if peers and not args.quic:
        print("[fatal] peers resolved but --quic not set. "
              "Phase 25c removed HTTP gossip; nodes with peers must run "
              "with --quic. Re-run with `--quic --dag-mode` (or pass "
              "`--no-seed-discovery` to start standalone).",
              file=sys.stderr)
        return 2
    node = Node(Path(args.data_dir), seed, treasury_address=treasury,
                peers=peers, produce=not args.no_produce,
                dag_mode=args.dag_mode, quic=args.quic,
                mempool_max_txs=args.mempool_max_txs,
                mempool_max_per_sender=args.mempool_max_per_sender,
                genesis_lockdown_height=args.genesis_lockdown_height)

    # Phase 25a: optional QUIC gossip transport. Lives in its own asyncio
    # thread so the producer + RPC stay synchronous. Cert is generated
    # lazily under the data dir on first start (`quic.crt` + `quic.key`).
    if args.quic:
        from . import quic as quic_mod
        cert_path, key_path = quic_mod.generate_self_signed_cert(
            crypto.address(node.producer_pub), Path(args.data_dir))
        node.quic_cert_path = cert_path
        node.quic_cert_pin = quic_mod.cert_pin_from_path(cert_path)
        node.quic_runtime = quic_mod.QuicRuntime(
            node, args.host, args.port, cert_path, key_path)
        node.quic_runtime.start()
        print(f"[quic] cert pin={node.quic_cert_pin} "
              f"path={cert_path} listening udp://{args.host}:{args.port}")

    if peers:
        node.sync_from_peers()
    node.start_producer()
    server = RpcServer((args.host, args.port), Handler)
    server.node = node
    print(f"[node] running. producer={crypto.address(node.producer_pub)} "
          f"treasury={treasury} rpc=http://{args.host}:{args.port}/ "
          f"peers={peers} produce={not args.no_produce} "
          f"dag_mode={args.dag_mode} quic={args.quic} "
          f"mempool_cap={args.mempool_max_txs}/{args.mempool_max_per_sender} "
          f"genesis_lockdown_height={args.genesis_lockdown_height}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        node.stop()
    return 0


def cmd_submit(args):
    seed = bytes.fromhex(args.seed)
    pub = crypto.pubkey_from_seed(seed)
    addr = crypto.address(pub)
    # fetch nonce
    info = json.loads(urllib.request.urlopen(f"{args.rpc}/account/{addr}").read())
    nonce = info["nonce"]

    if args.tx == "register-content":
        tx = Transaction.register_content(
            pub, nonce,
            content_id=args.content_id,
            root_hash=args.root_hash,
            generation_id=args.generation_id,
            ai_pubkey_hex=args.ai_pubkey,
            ai_signature_hex=args.ai_signature,
        )
    elif args.tx == "create-order":
        tx = Transaction.create_order(
            pub, nonce,
            order_id=args.order_id,
            content_id=args.content_id,
            seller=args.seller,
            value=int(args.value),
        )
    elif args.tx == "submit-proof":
        tx = Transaction.submit_proof(
            pub, nonce,
            order_id=args.order_id, role=args.role, proof_hash=args.proof_hash,
        )
    elif args.tx == "finalize":
        tx = Transaction.finalize(pub, nonce, order_id=args.order_id, valid=args.valid)
    elif args.tx == "stake":
        tx = Transaction.stake(pub, nonce, amount=int(args.amount))
    elif args.tx == "transfer":
        tx = Transaction.transfer(pub, nonce, to=args.to, amount=int(args.amount))
    elif args.tx == "post-job":
        tx = Transaction.post_job(pub, nonce,
            job_id=args.job_id, content_id=args.content_id,
            kind=args.kind, reward=int(args.reward))
    elif args.tx == "claim-job":
        tx = Transaction.claim_job(pub, nonce, job_id=args.job_id)
    elif args.tx == "submit-work-proof":
        tx = Transaction.submit_work_proof(pub, nonce,
            job_id=args.job_id, output_root=args.output_root)
    elif args.tx == "register-ai-service":
        tx = Transaction.register_ai_service(pub, nonce,
            ai_pubkey_hex=args.ai_pubkey, name=args.name)
    elif args.tx == "register-producer":
        tx = Transaction.register_producer(pub, nonce,
            producer_pubkey_hex=args.producer_pubkey, name=args.name)
    else:
        print(f"unknown tx kind {args.tx}", file=sys.stderr); return 2
    tx.sign(seed)

    body = json.dumps(tx.to_dict()).encode()
    req = urllib.request.Request(f"{args.rpc}/tx", method="POST",
                                  data=body, headers={"Content-Type":"application/json"})
    res = urllib.request.urlopen(req)
    print(res.read().decode())
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="morm-l1")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("keygen").set_defaults(func=cmd_keygen)

    n = sub.add_parser("node", help="run a producer + RPC")
    n.add_argument("--data-dir", required=True)
    n.add_argument("--producer-seed", required=True, help="hex 32-byte ed25519 seed")
    n.add_argument("--treasury", required=True, help="address that collects fees + finalizes")
    n.add_argument("--host", default="127.0.0.1")
    n.add_argument("--port", type=int, default=8900)
    n.add_argument("--peers", default="",
                   help="comma-separated peer URLs to gossip with. When empty, "
                        "Phase 30c federation seed list (baked-in seeds.json + "
                        "<data-dir>/seeds.json + discovery channels) is used.")
    n.add_argument("--no-seed-discovery", action="store_true",
                   help="Phase 30c: skip live discovery (DNS SRV, github raw, "
                        "IPFS) and only use baked-in + local seeds.json. "
                        "Useful for offline/air-gap testing.")
    n.add_argument("--no-produce", action="store_true",
                   help="passive node: import blocks from peers but do not produce")
    n.add_argument("--dag-mode", action="store_true",
                   help="Phase 24a: drop slot election; every producer seals "
                        "in parallel. Sibling state divergence is tolerated "
                        "(no state_root strict-match) until 24b adds "
                        "frontier-relative state.")
    n.add_argument("--quic", action="store_true",
                   help="Phase 25a: enable opt-in QUIC gossip transport "
                        "alongside HTTP. Each peer that advertises a "
                        "quic_cert_pin in /info receives blocks/txs via "
                        "QUIC streams; the rest fall back to HTTP gossip. "
                        "Self-signed cert generated under --data-dir/quic.{crt,key}.")
    # Phase 26c: mempool DoS guards. Defaults match SECURITY-DESIGN §1.1 26c.
    from .node import (MEMPOOL_MAX_TXS_DEFAULT,
                       MEMPOOL_MAX_PER_SENDER_DEFAULT)
    n.add_argument("--mempool-max-txs", type=int, default=MEMPOOL_MAX_TXS_DEFAULT,
                   help="Phase 26c global mempool size cap. submit_tx rejects "
                        "new tx once the queue holds this many; existing tx "
                        "are unaffected. Default: 5000.")
    n.add_argument("--mempool-max-per-sender", type=int, default=MEMPOOL_MAX_PER_SENDER_DEFAULT,
                   help="Phase 26c per-sender mempool quota — fee-floor stand-in. "
                        "submit_tx rejects further tx from a sender once this "
                        "many are already pending. Default: 32.")
    # Phase 26e — Genesis lockdown window. Default 100 blocks; 0 disables.
    from .state import State as _State
    n.add_argument("--genesis-lockdown-height", type=int,
                   default=_State.GENESIS_LOCKDOWN_HEIGHT_DEFAULT,
                   help="Phase 26e: while the chain has no registered producers "
                        "AND head_height is below this value, only the treasury "
                        "address may produce blocks. 0 disables (single-node "
                        "smoke tests only). Default: 100.")
    n.set_defaults(func=cmd_node)

    s = sub.add_parser("submit", help="sign + POST a tx to a running node")
    s.add_argument("--rpc", default="http://127.0.0.1:8900")
    s.add_argument("--seed", required=True, help="hex 32-byte signer seed")
    sub2 = s.add_subparsers(dest="tx", required=True)

    rc = sub2.add_parser("register-content")
    rc.add_argument("--content-id", required=True)
    rc.add_argument("--root-hash", required=True)
    rc.add_argument("--generation-id", default=None)
    rc.add_argument("--ai-pubkey", default=None,
                    help="ed25519 pubkey hex of issuing AI service (when generation_id set)")
    rc.add_argument("--ai-signature", default=None,
                    help="ed25519 signature hex over (gen_id || cid)")

    co = sub2.add_parser("create-order")
    co.add_argument("--order-id", required=True)
    co.add_argument("--content-id", required=True)
    co.add_argument("--seller", required=True)
    co.add_argument("--value", required=True)

    sp = sub2.add_parser("submit-proof")
    sp.add_argument("--order-id", required=True)
    sp.add_argument("--role", choices=["packing", "opening"], required=True)
    sp.add_argument("--proof-hash", required=True)

    fz = sub2.add_parser("finalize")
    fz.add_argument("--order-id", required=True)
    fz.add_argument("--valid", action="store_true")
    fz.add_argument("--invalid", dest="valid", action="store_false")
    fz.set_defaults(valid=True)

    st = sub2.add_parser("stake")
    st.add_argument("--amount", required=True)

    tr = sub2.add_parser("transfer")
    tr.add_argument("--to", required=True)
    tr.add_argument("--amount", required=True)

    pj = sub2.add_parser("post-job")
    pj.add_argument("--job-id", required=True)
    pj.add_argument("--content-id", required=True)
    pj.add_argument("--kind", default="transcode")
    pj.add_argument("--reward", required=True)

    cj = sub2.add_parser("claim-job")
    cj.add_argument("--job-id", required=True)

    swp = sub2.add_parser("submit-work-proof")
    swp.add_argument("--job-id", required=True)
    swp.add_argument("--output-root", required=True)

    ras = sub2.add_parser("register-ai-service")
    ras.add_argument("--ai-pubkey", required=True)
    ras.add_argument("--name", required=True)

    rp = sub2.add_parser("register-producer")
    rp.add_argument("--producer-pubkey", required=True)
    rp.add_argument("--name", required=True)

    s.set_defaults(func=cmd_submit)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
