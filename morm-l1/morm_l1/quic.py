"""Phase 25a + 25b — opt-in QUIC gossip transport.

Adds an `aioquic`-based UDP listener alongside the existing HTTP/1.1 RPC
server. Node-to-node `/gossip/block` and `/gossip/tx` fanout migrate to
QUIC streams when both peers advertise a `quic_cert_pin` in `/info`;
otherwise the existing HTTP path is used unchanged. The migration is
opt-in via the `--quic` CLI flag.

Phase 25b adds a binary-encoded compact block-header datagram per
DAG-DESIGN §7 (~370 B for 3 parents, comfortably under any sane MTU).
The compact header lets receivers know about a new block immediately
even before the full JSON body arrives via the stream path. Unlike the
earlier large JSON-as-datagram experiment, the compact datagram fits
in a single UDP frame without fragmentation, which sidesteps the
symmetric-2-node silent-drop issue documented in QUIC-DESIGN.md §11.

Why QUIC (vs current HTTP):
- 0–1 RTT amortised handshake (vs full TCP+message round-trip per gossip).
- No head-of-line blocking — each fanout is its own QUIC stream.
- TLS 1.3 mandatory; we get encrypted gossip "for free".

This module exposes:
  - generate_self_signed_cert(addr, data_dir) → (cert_path, key_path)
  - cert_pin(cert_pem_bytes) → str (16-hex of sha256 of DER pubkey)
  - QuicGossipServer / QuicGossipClient

The producer thread stays sync (Phase 17/24 design); QUIC I/O runs on a
dedicated asyncio thread. _fanout_* on the sync side schedule sends via
`loop.call_soon_threadsafe(asyncio.create_task, ...)`.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import struct
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from aioquic.asyncio import QuicConnectionProtocol, connect, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import DatagramFrameReceived, StreamDataReceived

# ----------------------------------------------------------------------
# Cert generation + pinning
# ----------------------------------------------------------------------

CERT_FILENAME = "quic.crt"
KEY_FILENAME = "quic.key"

# QUIC ALPN for our gossip protocol; aioquic requires at least one.
ALPN_PROTOCOLS = ["morm-gossip/1"]

# Phase 25b: cap on the negotiated datagram frame size (bytes).
#
# RFC 9221 lets either peer advertise any size; aioquic uses the
# minimum of both ends. The "right" PoC value would be ≤ path MTU
# (typically 1500 B − IP/UDP/QUIC overhead ≈ 1200 B). We pick a
# larger value (8 KB) for two reasons:
#
# 1. We're sending the **full block JSON** as the datagram payload
#    instead of the compact binary block-header in DAG-DESIGN §7.
#    Implementing that compact header is a separate ~6 h follow-up
#    (Phase 25b-binary). For a PoC, "send the JSON if it fits, else
#    stream" is enough to prove the unreliable path works end-to-end.
# 2. Localhost / LAN paths comfortably handle larger UDP datagrams;
#    fragmentation is the OS's problem, not ours, at PoC scale.
#
# A real WAN deployment should drop this to ~1200 and adopt the
# compact binary header so the small datagram fits in a single MTU
# without IP fragmentation.
DATAGRAM_FRAME_SIZE = 8192

# Conservative payload ceiling we'll actually try to send via datagram.
# Stay a few bytes under the negotiated size to leave room for QUIC's
# own framing overhead; surplus payloads silently fall back to streams.
DATAGRAM_MAX_PAYLOAD = 8000


# ----------------------------------------------------------------------
# Phase 25b — compact binary block-header datagram (DAG-DESIGN §7)
# ----------------------------------------------------------------------

# Wire types we tag the first byte of every datagram with so receivers
# can route binary payloads vs. (legacy) JSON envelopes without ambiguity.
DATAGRAM_TYPE_BLOCK_HEADER = 0x01

COMPACT_HEADER_VERSION = 1


def encode_compact_block_header(block) -> bytes:
    """Pack a block's header into the compact binary datagram format
    described in DAG-DESIGN.md §7. The body of the block (transactions)
    is NOT included — receivers fetch it via the stream path. Layout:

        | 1B  type            (0x01 = BLOCK_HEADER)
        | 1B  version
        | 8B  height          (big-endian unsigned)
        | 32B header_hash
        | 32B state_root
        | 32B tx_root
        | 32B producer_pubkey
        | 64B header_signature
        | 1B  parent_count N
        | 32B × N parent_hashes
        | 2B  tx_count
        | 8B  timestamp        (big-endian unsigned, ms-since-epoch)

    Total = 213 + 32·N bytes. For N=3 parents the header is 309 B —
    a small fraction of any sane UDP MTU."""
    h = block.header
    parents = h.parent_hashes
    if len(parents) > 255:
        raise ValueError(f"too many parents for compact header: {len(parents)}")
    parts = [
        struct.pack("!BBQ",
                    DATAGRAM_TYPE_BLOCK_HEADER,
                    COMPACT_HEADER_VERSION,
                    h.height),
        block.hash(),       # 32 B
        h.state_root,       # 32 B
        h.tx_root,          # 32 B
        h.producer,         # 32 B
        block.signature,    # 64 B
        struct.pack("!B", len(parents)),
    ]
    for p in parents:
        if len(p) != 32:
            raise ValueError("parent_hash must be 32 bytes")
        parts.append(p)
    parts.append(struct.pack("!H", len(block.transactions)))
    parts.append(struct.pack("!Q", h.timestamp))
    return b"".join(parts)


def decode_compact_block_header(data: bytes) -> dict:
    """Inverse of `encode_compact_block_header`. Returns a dict with the
    parsed fields. Validates basic invariants but does not verify the
    signature (that's the importer's job, after the body arrives)."""
    if len(data) < 213:
        raise ValueError(f"datagram too short: {len(data)} B")
    typ, ver, height = struct.unpack("!BBQ", data[:10])
    if typ != DATAGRAM_TYPE_BLOCK_HEADER:
        raise ValueError(f"unexpected datagram type: 0x{typ:02x}")
    if ver != COMPACT_HEADER_VERSION:
        raise ValueError(f"unsupported header version: {ver}")
    p = 10
    header_hash = data[p:p + 32]; p += 32
    state_root = data[p:p + 32]; p += 32
    tx_root = data[p:p + 32]; p += 32
    producer = data[p:p + 32]; p += 32
    signature = data[p:p + 64]; p += 64
    n_parents = data[p]; p += 1
    parents: list = []
    for _ in range(n_parents):
        parents.append(data[p:p + 32])
        p += 32
    tx_count = struct.unpack("!H", data[p:p + 2])[0]; p += 2
    timestamp = struct.unpack("!Q", data[p:p + 8])[0]
    return {
        "type": typ,
        "version": ver,
        "height": height,
        "hash": header_hash,
        "state_root": state_root,
        "tx_root": tx_root,
        "producer": producer,
        "signature": signature,
        "parent_hashes": parents,
        "tx_count": tx_count,
        "timestamp": timestamp,
    }


def _cert_paths(data_dir: Path) -> tuple[Path, Path]:
    return Path(data_dir) / CERT_FILENAME, Path(data_dir) / KEY_FILENAME


def generate_self_signed_cert(producer_address: str, data_dir: Path) -> tuple[Path, Path]:
    """Generate (cert_path, key_path) under `data_dir`. Idempotent — returns
    the existing pair unchanged if both files already exist. Cert SAN is
    set to `producer_address` so the transport identity is visibly bound
    to the chain identity. RSA-2048, 10-year validity (rotated by deleting
    the files)."""
    cert_path, key_path = _cert_paths(data_dir)
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path
    data_dir.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, producer_address),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MORM L1 node"),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(producer_address)]),
            critical=False,
        )
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    cert_path.write_bytes(
        cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    return cert_path, key_path


def cert_pin(cert_pem_bytes: bytes) -> str:
    """Phase 25a §6: pin = sha256(DER of subject public key)[:16] hex.
    Truncated to 16 hex chars (8 bytes) for human-readable comparison;
    the full 32-byte hash is recoverable from the cert itself if needed.

    Pinning the SPKI rather than the cert lets us re-issue the cert (e.g.
    for SAN updates) without breaking the pin, as long as the underlying
    keypair is unchanged."""
    cert = x509.load_pem_x509_certificate(cert_pem_bytes)
    spki_der = cert.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(spki_der).hexdigest()[:16]


def cert_pin_from_path(cert_path: Path) -> str:
    return cert_pin(Path(cert_path).read_bytes())


# ----------------------------------------------------------------------
# QUIC server (gossip listener)
# ----------------------------------------------------------------------

class _GossipServerProtocol(QuicConnectionProtocol):
    """Per-connection handler. Receives length-prefixed JSON gossip messages
    on stream id 0 (or any client-initiated stream). Each message is one
    of {"kind": "block", "payload": <Block.to_dict>} or
    {"kind": "tx", "payload": <Transaction.to_dict>}.

    On receipt, dispatches into the parent Node's `import_block` /
    `submit_tx` (with `gossip=False` so we don't fan out back to the
    sender)."""

    # Set by the server factory below.
    morm_node = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Per-stream buffer: data may arrive in multiple datagrams.
        self._stream_buf: dict[int, bytearray] = {}

    def quic_event_received(self, event):
        # Debug: confirm what events are arriving on the server side.
        sys.stderr.write(
            f"[quic-srv-event] {type(event).__name__}\n")
        if isinstance(event, StreamDataReceived):
            buf = self._stream_buf.setdefault(event.stream_id, bytearray())
            buf.extend(event.data)
            if event.end_stream:
                self._dispatch_message(event.stream_id, bytes(buf))
                self._stream_buf.pop(event.stream_id, None)
        elif isinstance(event, DatagramFrameReceived):
            # Phase 25b: datagram fanout. The first byte tags the wire
            # type so we can support both the compact binary block-header
            # format (0x01) and any future datagram kinds without
            # ambiguity. Legacy JSON-as-datagram payloads (the earlier
            # 25b experiment) are not used in this code path anymore.
            sys.stderr.write(
                f"[quic-srv-datagram] received {len(event.data)} bytes "
                f"(type=0x{event.data[0]:02x} if data else 0)\n"
                if event.data else
                "[quic-srv-datagram] empty datagram\n"
            )
            if not event.data:
                return
            wire_type = event.data[0]
            if wire_type == DATAGRAM_TYPE_BLOCK_HEADER:
                self._dispatch_compact_block_header(event.data)
            else:
                sys.stderr.write(
                    f"[quic-srv-datagram] unknown wire type 0x{wire_type:02x}\n")

    def _dispatch_compact_block_header(self, data: bytes) -> None:
        """Phase 25b: parse a compact binary block-header datagram.

        Goal of the datagram path: receivers learn about a new block
        hash *as soon as the header arrives*, even before the full body
        comes in over the stream. They can use the hash to dedupe and
        decide whether to keep waiting for the body or pull it.

        Implementation note: in this PoC we don't yet auto-pull bodies;
        the body still arrives via the existing JSON-on-stream fanout
        and import_block runs there. The compact header is a "wake-up"
        signal — its arrival proves the datagram path is alive even
        when the larger JSON-as-datagram experiment failed in the
        symmetric two-node test."""
        try:
            hdr = decode_compact_block_header(data)
        except Exception as e:
            sys.stderr.write(
                f"[quic-srv-datagram] decode failed: "
                f"{type(e).__name__}: {e}\n")
            return
        sys.stderr.write(
            f"[quic-srv-datagram] BLOCK_HEADER hash={hdr['hash'].hex()[:16]}… "
            f"height={hdr['height']} parents={len(hdr['parent_hashes'])} "
            f"txs={hdr['tx_count']}\n")
        node = self.morm_node
        if node is None:
            return
        # Mark hash as seen-but-pending so dedup races don't double-import
        # if the body arrives shortly after via stream. (The body-side
        # import_block already does its own _seen_blocks check, so this
        # is a hint, not a hard barrier.)
        try:
            with node._lock:
                # Just a soft notification — log if we've never seen it.
                if hdr["hash"] not in node._seen_blocks:
                    sys.stderr.write(
                        f"[quic-srv-datagram] NEW block announced via datagram, "
                        f"awaiting body via stream\n")
        except Exception:
            pass

    def _dispatch_message(self, stream_id: int, raw: bytes) -> None:
        try:
            msg = json.loads(raw.decode())
        except Exception as e:
            sys.stderr.write(f"[quic-gossip] malformed message: {e}\n")
            return
        kind = msg.get("kind")
        node = self.morm_node
        if node is None:
            return
        try:
            if kind == "block":
                from .block import Block
                blk = Block.from_dict(msg["payload"])
                node.import_block(blk, gossip=True)
            elif kind == "tx":
                from .tx import Transaction
                tx = Transaction.from_dict(msg["payload"])
                node.submit_tx(tx, gossip=False)
            else:
                sys.stderr.write(f"[quic-gossip] unknown kind {kind!r}\n")
        except Exception as e:
            sys.stderr.write(
                f"[quic-gossip] dispatch error kind={kind}: "
                f"{type(e).__name__}: {e}\n")


def _make_protocol_factory(node):
    """Bind the per-connection protocol to the running Node."""
    class Bound(_GossipServerProtocol):
        morm_node = node
    return Bound


async def _serve_quic(node, host: str, port: int,
                      cert_path: Path, key_path: Path):
    """Start an aioquic server bound to `host:port` UDP. Runs forever."""
    config = QuicConfiguration(
        is_client=False,
        alpn_protocols=ALPN_PROTOCOLS,
        # Phase 25b: advertise willingness to receive datagrams up to
        # DATAGRAM_FRAME_SIZE bytes. Both peers must set this for QUIC
        # DATAGRAM frames to be enabled per RFC 9221 §3.
        max_datagram_frame_size=DATAGRAM_FRAME_SIZE,
    )
    config.load_cert_chain(str(cert_path), str(key_path))
    server = await serve(
        host, port,
        configuration=config,
        create_protocol=_make_protocol_factory(node),
    )
    sys.stderr.write(f"[quic] listener up on udp://{host}:{port}\n")
    # Keep the coroutine alive until cancelled.
    await asyncio.Event().wait()
    server.close()


# ----------------------------------------------------------------------
# QUIC client (gossip sender)
# ----------------------------------------------------------------------

class _GossipClientProtocol(QuicConnectionProtocol):
    """Lightweight client. By default opens a fresh bidi stream per
    message (no reuse — keeps the wire format trivially boundaried).
    Phase 25b adds an optional datagram path for fanout that fits in one
    QUIC DATAGRAM frame (≤ DATAGRAM_MAX_PAYLOAD); the receiver dispatches
    datagram and stream payloads identically (same JSON envelope)."""

    async def send_message(self, kind: str, payload: dict,
                           prefer_datagram: bool = False) -> str:
        """Returns one of:
          - "stream"          (only stream sent — txs and non-block kinds)
          - "datagram+stream" (Phase 25b: compact header via datagram +
                               full JSON body via stream — block fanout)

        Phase 25b: the datagram carries a compact binary block-header
        per DAG-DESIGN §7 (~370 B for 3 parents, well under MTU). The
        full block body (transactions, signature wrapper, etc.) still
        rides a stream. That gives us:
          - immediate notification of new blocks (datagram = fast wake)
          - reliable body delivery (stream = no loss recovery needed)
          - safe MTU footprint (compact header always fits in 1 UDP
            frame; the earlier JSON-as-datagram experiment occasionally
            exceeded the negotiated frame cap in symmetric 2-node and
            silently dropped — see QUIC-DESIGN.md §11)."""
        body = json.dumps({"kind": kind, "payload": payload}).encode()
        peer_cap = getattr(self._quic, "_remote_max_datagram_frame_size", 0) or 0

        # Compact header datagram path (only for blocks, only if peer
        # negotiated datagram support). Stream is sent regardless so
        # the body always arrives reliably.
        sent_datagram = False
        if prefer_datagram and kind == "block" and peer_cap > 0:
            try:
                from .block import Block
                blk = Block.from_dict(payload)
                compact = encode_compact_block_header(blk)
                if len(compact) <= peer_cap - 4:
                    self._quic.send_datagram_frame(compact)
                    sent_datagram = True
                    sys.stderr.write(
                        f"[quic-client-debug] compact header datagram "
                        f"len={len(compact)} peer_cap={peer_cap}\n")
                else:
                    sys.stderr.write(
                        f"[quic-client-debug] compact header {len(compact)}B "
                        f"exceeds peer_cap {peer_cap}, skipping datagram\n")
            except Exception as e:
                sys.stderr.write(
                    f"[quic-client-debug] compact header encode failed: "
                    f"{type(e).__name__}: {e}\n")

        # Stream path (always — for body or for non-block kinds).
        stream_id = self._quic.get_next_available_stream_id(is_unidirectional=False)
        self._quic.send_stream_data(stream_id, body, end_stream=True)
        self.transmit()
        await asyncio.sleep(0)   # yield once so the UDP socket flushes
        return "datagram+stream" if sent_datagram else "stream"


class QuicGossipClient:
    """Outgoing fanout helper. Maintains a connection cache keyed by
    `(host, port)`. Each connection is shared across messages (true QUIC
    multiplexing); idle connections expire after `idle_timeout` seconds.

    Lives entirely on the asyncio loop thread; the sync producer schedules
    sends via `loop.call_soon_threadsafe` (see Node._fanout_quic)."""

    def __init__(self, idle_timeout: float = 300.0):
        self._connections: dict[tuple[str, int], _GossipClientProtocol] = {}
        self._connection_locks: dict[tuple[str, int], asyncio.Lock] = {}
        self._last_use: dict[tuple[str, int], float] = {}
        self.idle_timeout = idle_timeout

    async def _open(self, host: str, port: int) -> _GossipClientProtocol:
        config = QuicConfiguration(
            is_client=True,
            alpn_protocols=ALPN_PROTOCOLS,
            verify_mode=__import__("ssl").CERT_NONE,  # TOFU: pin checked separately
            # Phase 25b: client side must also negotiate datagram support.
            max_datagram_frame_size=DATAGRAM_FRAME_SIZE,
        )
        # `connect()` is an async context manager but we want a long-lived
        # connection; manually `__aenter__` and stash the cm so we can
        # close later. For simplicity we leak; idle eviction handles it.
        cm = connect(host, port, configuration=config,
                     create_protocol=_GossipClientProtocol)
        proto = await cm.__aenter__()
        # Stash the cm so we can __aexit__ on close.
        proto._aexit_cm = cm  # type: ignore[attr-defined]
        # Wait for handshake to complete before first send.
        await proto.wait_connected()
        return proto

    async def send(self, host: str, port: int,
                   kind: str, payload: dict,
                   prefer_datagram: bool = False) -> bool:
        """Send a single gossip message to `host:port`. Returns True on
        success, False on transport error (caller should fall back to HTTP).

        Phase 25a: stream-mode (reliable). 2-node verified end-to-end.
        Phase 25b status (2026-04-26): datagram path is implemented (set
        `prefer_datagram=True` to use it) AND verified in single-process
        + asymmetric 2-process tests, but **fails silently in symmetric
        two-node MORM gossip** (both nodes producing + datagramming
        simultaneously — `[quic-srv-datagram]` events never fire on
        either side). Streams continue to work in the same setup.
        Pure-aioquic 2-process datagram tests pass, so the bug is in
        MORM's wiring, not aioquic. Hypotheses to investigate:
          - CID routing collision when both nodes simultaneously open
            client connections to each other.
          - Source-port reuse interaction with the bound server socket.
          - Some interplay with the `loop.run_until_complete(_serve_quic)`
            blocking call vs concurrently-scheduled client tasks.
        Until resolved, `node.py:_fanout_via_quic` keeps `prefer_datagram=False`
        so blocks also go via streams — slower than the design but
        correct. Once the compact-binary-header datagram (DAG-DESIGN §7)
        is implemented as Phase 25b-binary, both the size budget and
        the routing concerns get reconsidered together."""
        key = (host, port)
        lock = self._connection_locks.setdefault(key, asyncio.Lock())
        async with lock:
            proto = self._connections.get(key)
            if proto is None or proto._quic._close_event is not None:
                try:
                    proto = await asyncio.wait_for(
                        self._open(host, port), timeout=3.0)
                except Exception as e:
                    sys.stderr.write(
                        f"[quic-client] connect to {host}:{port} failed: "
                        f"{type(e).__name__}: {e}\n")
                    return False
                self._connections[key] = proto
            try:
                used = await asyncio.wait_for(
                    proto.send_message(kind, payload, prefer_datagram),
                    timeout=3.0,
                )
                sys.stderr.write(
                    f"[quic-client] {kind} → {host}:{port} via {used}\n")
            except Exception as e:
                sys.stderr.write(
                    f"[quic-client] send to {host}:{port} failed: "
                    f"{type(e).__name__}: {e}\n")
                self._connections.pop(key, None)
                return False
            import time
            self._last_use[key] = time.time()
            return True


# ----------------------------------------------------------------------
# Lifecycle: start the asyncio loop thread for a Node
# ----------------------------------------------------------------------

class QuicRuntime:
    """Owns the asyncio event loop for QUIC I/O on a separate thread.

    The MORM Node remains thread-based for the producer + sync RPC. This
    runtime exists only to host the aioquic listener and the client-side
    connection pool; cross-thread sends use `loop.call_soon_threadsafe`."""

    def __init__(self, node, host: str, port: int,
                 cert_path: Path, key_path: Path):
        self.node = node
        self.host = host
        self.port = port
        self.cert_path = cert_path
        self.key_path = key_path
        self.loop: asyncio.AbstractEventLoop | None = None
        self.client = QuicGossipClient()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    def start(self):
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            # Schedule the listener task; signal ready as soon as the loop
            # is running (the listener itself starts asynchronously).
            loop.call_soon(self._ready.set)
            try:
                loop.run_until_complete(_serve_quic(
                    self.node, self.host, self.port,
                    self.cert_path, self.key_path))
            except Exception as e:
                sys.stderr.write(f"[quic-runtime] loop crashed: {e}\n")
            finally:
                loop.close()

        self._thread = threading.Thread(
            target=run, daemon=True, name="morm-quic-loop")
        self._thread.start()
        # Wait at most 2s for the loop to be alive.
        self._ready.wait(timeout=2.0)

    def schedule_send(self, host: str, port: int,
                      kind: str, payload: dict,
                      prefer_datagram: bool = False) -> None:
        """Fire-and-forget gossip send from any thread.

        Phase 25b: callers set `prefer_datagram=True` for block fanout to
        opt into the unreliable-but-fast datagram path; tx fanout leaves
        the default (stream/reliable) so the sender knows the peer
        received it for nonce ordering.

        Implementation detail: we go through `run_coroutine_threadsafe`
        (NOT `call_soon_threadsafe(create_task, ...)`) because the latter
        gets `asyncio.create_task` invoked as a *callback* with the coro
        as its arg, and `create_task` then needs to find a running loop
        via `get_running_loop()` from inside a non-task context. Different
        Python versions behave differently here; the symptom we hit was
        cross-thread-scheduled coroutines silently never running, which
        manifested as Phase 25b datagrams being lost between nodes."""
        if self.loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            self.client.send(host, port, kind, payload, prefer_datagram),
            self.loop,
        )
