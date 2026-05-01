# MORM 実装ステータス — Whitepaper 執筆用ファクトシート

> このドキュメントは **`docs/ja/WHITEPAPER.md` の執筆セッションが参照するための
> 唯一の真実 (single source of truth)** です。Whitepaper で「実装済み」「検証済み」
> と記述する箇所は、すべてここに対応する Phase 番号 + ファイルパス + 観測値を
> 持つこと。「設計のみ」と記述する箇所は §3 のリストにあること。
>
> Last sync: 2026-05-02 (Phase 1-27i + 25Va/Vb/Vc + 22-Video + 26c/e/f/q/r/s/y + 24b throughput+incremental + portrait pivot + swipe feed + camera upload + wallet policy + Solidity audit + i18n EN/JA + onboarding guide + **Phase 28a /swap UI (ETH↔MORM)** + **Phase 28b USDC tab (ERC-20↔USDC.morm)** + **BRIDGE-DESIGN.md 設計ノート** + **Phase 13b-PoC M-of-N quorum bridge E2E** + **Phase 30a-e Docker compose federated installer (3 image multi-arch ghcr.io publish + curl\|sh installer + federation seed list)** 完了 — TikTok creator-to-viewer 全 loop + chain hardening + DAG O(N)→O(K) + wallet policy gate + Slither High=0 + Echidna 4/4 PASS + 日本語 UI + 初回チュートリアル + multi-currency bridge UI + 2-of-3 federated bridge protocol + OS-independent self-hosted node distribution)

---

## 1. ハイレベル実装サマリ

| 領域 | Whitepaper 章 | 実装 Phase | コードロケーション | 検証ステータス |
|---|---|---|---|---|
| **MORM Cells (3秒WebMセグメント)** | §5.1 | Phase 1 | `morm-core/morm_core/encoder.py` | ✅ 実機 |
| **V-Hash (pHash + 音声FP)** | §7.1 | Phase 2 | `morm-core/morm_core/vhash.py` | ✅ 実機 |
| **重複処理スクリーニング** | §7.2 | Phase 2/8/16 | `morm-core/morm_core/screening.py` | ✅ 実機 (4シナリオ PASS) |
| **Player + 50/10サイクル** | §5.2 | Phase 3 | `morm-player/static/player.js` | ✅ 実機 |
| **Solidity MORMEscrow** | §8.3 (legacy) | Phase 4 | `morm-chain/src/MORMEscrow.sol` | ✅ Forge **11/11 PASS** |
| **Proof of Physical Evidence** | §8.1, §8.2 | Phase 5/16 | `morm-core/morm_core/evidence.py` | ✅ 実機 (clean / spliced / static 3シナリオ) |
| **P2P Mesh (origin/mirrors)** | §4.1 | Phase 6 | `morm-player/server.py` | ✅ 実機 |
| **Walletless ID (Passkey + 2-of-2 XOR)** | §6.1, §6.2 | Phase 7/9 | `morm-player/passkey_*.py`, `auth.py` | ✅ 実機 |
| **AI動体解析 (cut_score)** | §8.2 | Phase 8/15c | `morm-core/morm_core/evidence.py:cut_score()` | ✅ 実機 |
| **MORM Chain (独自L1, ed25519, DAG-ready blocks)** | §4.3 | Phase 10a-e | `morm-l1/morm_l1/{node,state,tx,block,crypto,rpc}.py` | ✅ 実機 |
| **PoUW worker rewards** | §9.3 | Phase 10b | `morm-l1/morm_l1/state.py` (worker_stats) | ✅ 実機 |
| **HTTP gossip → state sync** | §4.2 (現行) | Phase 10c | `morm-l1/morm_l1/node.py:_fanout_*, sync_from_peers` | ✅ 実機 |
| **EVM ↔ MORM Bridge** | §9.5 (multi通貨 §9.5) | Phase 12 | `morm-chain/src/MORMBridge.sol` + `relayer.py` | ✅ Forge **7/7** + e2e |
| **ERC-20 (USDC) Bridge** | §9.5 | Phase 13a | `morm-chain/src/MORMBridgeERC20.sol` | ✅ Forge **4/4** + e2e |
| **Multi-sig relayer** | §13 (緊急対応) | Phase 13b | `morm-chain/src/MORMBridgeMS.sol` | ✅ Forge **5/5** |
| **AIサービス (Generation ID)** | §7.3 | Phase 14 | `morm-aiservice/aiservice.py` + L1 register tx | ✅ 実機 (6シナリオ PASS) |
| **MORM Shop UX (4ステップ)** | §8 全般 | Phase 15a | `morm-player/static/shop.{html,js}` | ✅ 実機 |
| **3-of-5 Shamir (鍵分割)** | §13 (DAO脱退時) | Phase 15b | `morm-l1/morm_l1/shamir.py` | ✅ 全 5C3=10通り |
| **実カメラ → 証拠生成** | §8.1 | Phase 16a | `shop.html` getUserMedia + 16a server-side encode | ✅ smoke (実カメラはClaudePreview iframe外で動作確認要) |
| **Multi-producer Slot Rotation** | §4.3 | Phase 17 | `morm-l1/morm_l1/state.py:slot_owner` | ✅ 実機 (2 producer, deterministic election) |
| **K-depth Finality** | §4.3 | Phase 17b | `morm-l1/morm_l1/__init__.py:FINALITY_DEPTH=3` | ✅ 実機 (head-3 finalized) |
| **m0r-prefix Native Address** | §4.3 | Phase 18 | `morm-l1/morm_l1/crypto.py:address(), parse_address()` | ✅ 実機 |
| **µMORM → MORM 単位統一** | §9.1 | Phase 18 | 全モジュール | ✅ |
| **node招待 (`invite-node.sh`) + `/admin` UI** | §11 (DAO node onboarding) | Phase 19 | `morm-l1/ops/invite-node.sh`, `morm-player/static/admin.{html,js}` | ✅ 実機 |
| **Testnet 公開手順** | (運用文書) | Phase 20 | `morm-l1/ops/TESTNET.md` | 文書のみ (Cloudflare Tunnel/Tailscale/ngrok 3方式) |
| **PWA (manifest + Service Worker + iOS/Android)** | §6.2, §11.1 (Mobile) | Phase 21 | `morm-player/static/{manifest.webmanifest,sw.js}` | ✅ 実機 |
| **WebRTC P2P mesh (browser↔browser cell中継)** | §4.1, §5.4 | Phase 22 | `morm-player/static/morm-p2p.js` + signaling endpoints | ✅ 実機 (preview) |
| **TURN サーバー対応 (coturn use-auth-secret)** | §4.1 (NAT越え) | Phase 22b | `morm-l1/ops/turn/`, `passkey_morm.py:ice_servers_for()` | ✅ Mac Mini で coturn 稼働 + HMAC ephemeral creds 検証済 |
| **3-node testnet (state収束 + finality)** | §4.3 | Phase 23 | `morm-l1/ops/3NODE-TESTNET.md` | ✅ localhost 3-node, state_root 一致 |
| **Mempool dedup-on-import** | §4.3 | Phase 23a | `morm-l1/morm_l1/node.py:import_block` | ✅ slot分布が A=23/B=9/C=0 → A=13/B=11/C=9 に改善 |
| **Concurrent DAG Sealing (slot election 撤廃)** | §4.3 (DAGの本旨) | Phase 24a | `morm-l1/morm_l1/{node,state}.py` (`--dag-mode`) | ✅ 3-node で max_width=3 観測 |
| **DAG frontier-relative state (canonical merge order)** | §4.3 (DAGの完成) | Phase 24b | `morm-l1/morm_l1/state.py:_canonical_tx_order, compute_frontier_state_root, _rebuild_materialized_state, _apply_block_dag` + `node.py:_produce_dag` + `rpc.py:/info.frontier_root, GET /frontier` | ✅ **3-node correctness 達成** — state_root + frontier_root が3ノード完全一致 (max_w=3, head_w=3 のDAG下で) |
| **DAG common-ancestor finality** | §4.3 | Phase 24c | `morm-l1/morm_l1/state.py:_all_ancestors, common_ancestors, finalized_height_dag` + `rpc.py:/info finality dispatch` | ✅ 3-node で `finalized=head-1` (witness threshold ⅔×N producers) 動作。`finality_rule` フィールドも `/info` に追加 |
| **DAG per-producer rate limit + spam control** | §4.3, §12 | Phase 24d | `morm-l1/morm_l1/state.py:_producer_weight, _producer_seal_count_in_window, producer_rate_limit_ok, producer_rate_window` + `_apply_block_dag` rate-check + `rpc.py:/info producer_rate_window` | ✅ 単一ノード R=1 で実測 **10004ms ブロック間隔** (10s window) 動作、3-node DAG で全 producers cap 維持 + 全 15 tx 完走 + state収束 |
| **QUIC opt-in gossip transport** | §4.2 (現行 HTTP/1.1 → QUIC 移行) | Phase 25a | `morm-l1/morm_l1/quic.py` (cert + pin + aioquic server/client + asyncio runtime), `node.py:_fanout_via_quic` (hybrid HTTP/QUIC), `rpc.py:/info quic_cert_pin`, `cli.py --quic` | ✅ 2-node 実機で **block + tx fanout が QUIC ストリーム経由** 動作 (state収束維持)、HTTP fallback path も保持。aioquic 1.3.0、自己署名 RSA-2048、SPKI-pinned TOFU |
| **QUIC datagram block fanout (RFC 9221, compact binary header)** | §4.2 (高速化) | Phase 25b | `quic.py:encode_compact_block_header / decode_compact_block_header` (DAG-DESIGN §7 binary, ~245B for 1-tx block), `_GossipServerProtocol._dispatch_compact_block_header`, `QuicGossipClient.send_message(prefer_datagram=True)` で datagram(header) + stream(body) 並送、`node.py:_fanout_via_quic` で `prefer_datagram = (kind == "block")` | ✅ **symmetric 2-node 完全動作** — 双方向 `[quic-srv-datagram] BLOCK_HEADER` 発火、state収束 `a936668c495e06e6`、head=2。Root cause 確定: 旧 JSON-as-datagram (1.4KB) が path MTU 超過で silent fragmentation drop だった。compact 245B はsafe。詳細は `QUIC-DESIGN.md §12` resolution log |
| **HTTP gossip removal (QUIC-only)** | §4.2 (legacy 削除) | Phase 25c | `rpc.py:do_POST` で `/gossip/{tx,block}` → **HTTP 410** (with "removed_in: Phase 25c" pointer)、`node.py:_fanout_*` から HTTP fallback削除 (peer に pin なければ DROP+log)、`cli.py` で `--peers` w/o `--quic` → fatal exit、`/info.gossip_transport = "quic-only"` 公開 | ✅ 2-node 検証済: 410 返却、state収束 `ede7304a49cb9ae5`、compact datagram path も維持。CLI guard 動作確認 |
| **Treasury Multi-sig (M-of-N, 公開前 must-have)** | §15 (リスク対策) | Phase 26a | `tx.py: REGISTER_TREASURY_SIGNERS / MULTISIG_TX` + `multisig_signing_bytes(inner_kind, payload, treasury_addr, treasury_nonce)`、`state.py: treasury_signers / treasury_config` schema、`_tx_register_treasury_signers / _tx_multisig_tx`、`_TREASURY_ONLY_KINDS = {BRIDGE_MINT, REGISTER_AI_SERVICE, REGISTER_PRODUCER, FINALIZE}` ガード | ✅ E2E 検証: bootstrap (single-key) → 単一鍵 REGISTER_PRODUCER reject "treasury multi-sig active" → MULTISIG_TX 2-of-3 wrapper accept (producer "M2of3" 追加) → 1-of-3 reject "insufficient cosignatures" → wrong-nonce reject "treasury_nonce mismatch"。詳細は `SECURITY-DESIGN.md §1.1, §5` |
| **Per-producer rate limit (24d 兼 26b)** | §15 (DoS対策) | Phase 26b = Phase 24d | (Phase 24d で実装済) | ✅ Phase 24d 実装で `26b` カバー — single-node R=1 で実測 10004ms きっかりブロック間隔 |
| **CSRF + strict CORS (gateway hardening)** | §15 (gateway/RPC) | Phase 26u + 26v | `morm-player/passkey_morm.py: _check_csrf_or_reject / _origin_matched / _cors`, `--allowed-origins` CLI flag (repeatable) | ✅ Legacy mode (no flag) `*` CORS+no CSRF check (dev compat); strict mode: cross-origin POST → **403** + JSON explanation, allowed Origin → handler に通る、CORS は matched origin echo + Vary: Origin |
| **Production guard (dev-mode hard-disable)** | §15 (gateway) | Phase 26w | `MORM_PRODUCTION=1` env: `--dev-mode` を fatal exit、ランタイム `httpd.dev_mode=False` を force | ✅ 検証: production env + --dev-mode → "[fatal] forbidden" exit; production env なし + --dev-mode → 通常通り; production marker を startup log に表示 |
| **Treasury keyfile (`ps` leakage 防止)** | §15 (gateway) | Phase 26x | `--treasury-key-file` 新設 (mode 0600 + 64-hex 必須、`--treasury-seed` と mutex) | ✅ 検証: 0644 → fatal "expected 0o600"、0600 → accepted (treasury=keyfile)、両指定 → mutex fatal、wrong length → fatal |
| **Tx confirm dialog (passkey 署名前 modal)** | §15 (browser/PWA) | Phase 27f | `morm-identity.js: showTxConfirmDialog (kind+payload+nonce+sender, kind別 field rendering: TRANSFER→to/amount, BRIDGE_BURN→evm_recipient/amount, CREATE_ORDER→seller/value, FINALIZE→outcome, etc.) + signTxWithConfirm wrapper (skipConfirm option for VIEW_REWARD exempt)`、`shop.js: createOrder/SUBMIT_PROOF (packing+opening) wired`、`auth-morm.js: REGISTER_CONTENT wired` | ✅ Browser preview 検証済: TRANSFER + BRIDGE_BURN dialog 視覚確認 (screenshot 取得)、Confirm→resolved=true、Cancel→resolved=false、overlay cleanup、ESC/Enter キーバインド、kind 別 field 表示確認 |
| **UI/UX Cyber-Organic 適用** | §11 (UX) | Phase 24-UI | `morm-player/static/style.css`, admin.html/js, shop.js | ✅ preview (Swarm Map, Resource Ring, Action Slider, Pulse firefly, Cell pulse) |
| **Portrait camera-first upload UI** | §6.2 (Mobile creator UX) | Phase 25-Video portrait-upload | `morm-player/static/upload.html` 全面書換 — 9:16 portrait preview frame (`aspect-ratio: 9/16; max-width: 420px`)、単一 `.action` ボタンが状態遷移の唯一のエントリ (cyan/red 切替)、secondary row (`Flip camera / Discard clip / ▶ Feed`)、file drop fallback は下に小さく残置、録画中 `.rec` badge pulse animation。`morm-player/static/upload.js` の state machine: `idle → live (getUserMedia 9:16 hint) → recording (MediaRecorder mp4/webm 自動選択, 250ms timeslice) → captured (Blob を loop 再生) → uploading (POST /api/video/upload + 800ms job poll) → done (▶ Play link 有効化)`。MIME 選定は `video/mp4;codecs=avc1.42E01E,mp4a.40.2` 最優先 → mp4 → webm/vp9/opus → webm/vp8/opus fallback、`MAX_RECORD_MS=60_000` で暴走防止。Phase 25Vb 既存 backend (POST /api/video/upload + JobRegistry) は変更なしで再利用 | ✅ E2E 検証 (preview headless) — `/upload` レンダリング、frame ratio = 0.563 (=9/16)、`Start camera` idle 状態、9:16 badge 表示、`MediaRecorder.isTypeSupported` + `getUserMedia` API availability 両方 true 確認、fake mp4 POST で `job_id=237be7880642c7a5` 受理 + encode 起動 (Phase 25Vb 既存 pipeline が portrait UI から無変更で動作することを確認) |
| **Swipe feed (TikTok/Reels-style scroll-snap)** | §6.2 (Mobile native UX) | Phase 25-Video swipe-feed | `morm-player/static/player-hls.html` 全面書換 — `<div class="feed">` + `<article class="feed-item">` を contents 数だけ並列、`scroll-snap-type: y mandatory` + `scroll-snap-align: start` で **native gesture only** (touch swipe + mouse wheel)、各 card は `100vh` 高さ・aspect-ratio 9:16・`object-fit: cover`。`.topbar` (identity/balance/pill 常駐) + `.pager` (contents 数の dot, active highlight) + 各 `.item-hud` (cid/level/seg/claims/p2p/peers/ice 1秒更新)。`morm-player/static/player-hls.js` を `IntersectionObserver({root:feedEl, threshold:[0,0.6,1.0]})` 駆動に refactor: ratio>0.6 の item を active 認定 → `destroyActive() (hls.destroy + video.pause/removeAttribute src/load)` → `setP2PContent(cid)` → 新 video に hls.js mount + FRAG_LOADED hook で `rememberSegment + tryClaim`。同時 live hls.js は最大 1 個、O(N) contents でも live media pipeline は O(1)。 | ✅ E2E 検証 — 4 contents (`61361f4d... legacy landscape`, `78de3c4..., 78967a... auto-cropped portrait, c88e6cc... native portrait`) の feed 構築、初期 active=0 → `scrollIntoView` で portrait sample に jump → activeIdx=3, videoSize=1080×1920, prev item の `src` 解除 + paused=true, 新 hls.js 即座にattach + 再生開始確認。screenshot で縦型 9:16 frame + bottom HUD overlay (`c88e6cc025e42123 · level 1080p · seg ... · ice ...`) 視覚確認 |
| **Portrait pivot (9:16 mobile-first)** | §6.2 (Mobile native, TikTok/Reels 路線) | Phase 25-Video portrait | `morm-core/morm_core/hls_encoder.py:LADDER` を portrait 化 (1080p=1080×1920, 720p=720×1280, 480p=480×854, 360p=360×640、ladder 名は shorter-dim 採用で URL 互換)、`_build_ffmpeg_cmd` の scale filter に `force_original_aspect_ratio=increase,crop=w:h` 追加 → 入力が landscape でも auto 9:16 center-crop。`morm-player/static/player-hls.html` で `.wrap { max-width: 420px }` + `video { aspect-ratio: 9/16 }` + portrait 9:16 pill、HUD は `.hud-wrap { max-width: 720px }` で video frame と独立配置。`player-hls.js: LEVEL_SWITCHED` ラベルを `Math.min(width, height)` ベースに切替 (portrait/landscape どちらでも 1080p/720p の馴染み表示)。 | ✅ E2E 検証 — portrait testsrc 1080×1920 6s を encode → 4 ladder × 2 segments、`init_0.mp4` ffprobe で 1080p=1080×1920 / 720p=720×1280 / 360p=360×640 確認、landscape testsrc 1920×1080 入力でも auto-crop で 1080p init=1080×1920 出力 (auto-crop 機能確認)。preview gateway で portrait content (`c88e6cc025e42123`) を再生 → `videoSize=1080x1920`, `visible=282x501 (ratio=0.563=9/16)`, `curLevel=1080p · 5660kbps`, screenshot で縦型 9:16 frame + 縦縞 testsrc パターン視覚確認 |
| **HLS/CMAF Encoder + Origin + Player (Phase 25-Video)** | §5.1 (動画配信), §6.2 (Mobile native) | Phase 25Va | `morm-core/morm_core/hls_encoder.py` (FFmpeg ABR 4 ladder + V-Hash per segment + manifest), `morm-core/morm_core/cli.py:hls-encode` subcommand, `morm-player/passkey_morm.py:_serve_hls + /api/video/<cid>/* endpoints + --hls-storage-dir flag`, `morm-player/static/player-hls.{html,js}` (hls.js + iOS native fallback + VIEW_REWARD on FRAG_LOADED) | ✅ Browser preview 検証済 — 10秒 testsrc.mp4 → 4 ladder × 4 segments + 4 init.mp4 + master.m3u8 = **21 files** (1080p/720p/480p/360p, content-addressed seg_NNNNN.<vhash16>.m4s)、master.m3u8 = `application/vnd.apple.mpegurl` + `max-age=300`、.m4s = `video/iso.segment` + `max-age=31536000, immutable` (設計書 §4 通り)、Range 対応、native HLS path で 10.07s 完走、preview 内で **360p → 1080p ABR レベル切替観測**、4/4 VIEW_REWARD claims relayed (kind=7 exempt from confirm dialog per Phase 27f rule) |
| **HLS Upload Pipeline (Object Storage + Job Queue)** | §5.1 (動画投稿), §6.2 (Mobile creator) | Phase 25Vb | `morm-player/storage.py` (FS / S3-compatible 抽象, boto3 lazy import, `MORM_STORAGE_BACKEND=fs\|s3`, `MORM_S3_BUCKET` / `MORM_S3_ENDPOINT`), `morm-player/jobs.py` (in-process `ThreadPoolExecutor` + status dict + `post_encode_hook`), `passkey_morm.py: POST /api/video/upload?filename=…` (raw body, allowed extensions .mp4/.mov/.webm/.mkv/.m4v, `--max-upload-mb` cap, `--encode-workers` parallel) + `GET /api/video/job/<id>` + `GET /api/video/jobs`、`morm-player/static/upload.{html,js}` (drop zone + XMLHttpRequest progress + 800ms status polling + auto-link to `/player-hls?cid=<new>`) | ✅ E2E 検証 — 6秒 testsrc.mp4 (330KB) を `POST /api/video/upload?filename=sample6s.mp4` (raw body, Content-Type: video/mp4) → 200 + `{job_id, state:"encoding"}` → 800ms polling → **state=done in 1.18s, content_id=78de3c45669888fd, files_out=18 (= 13 HLS files + 5 misc)** → `/api/video/list` に新規 cid 出現 → `/player-hls` で content select → 6.07s 完走 + 6/6 VIEW_REWARD claims |
| **HLS Auto-Register on Chain (REGISTER_CONTENT post-encode hook)** | §5.1 (chain integration) | Phase 25Va-finish | `jobs.py:JobRegistry.post_encode_hook` callable + `passkey_morm.py:_make_register_content_hook(morm_rpc, treasury_seed_hex)` (manifest.json から content_id + master_playlist_hash を読み、treasury seed で `Transaction.register_content(...)` 署名 → POST /tx) | ✅ E2E 検証 (フレッシュ L1 8902 + gateway 8803) — upload → encode (1.18s) → post-hook が REGISTER_CONTENT 発火 (`tx_hash=c5638aaa…`, mempool_size=1) → ~1s 後 head=1 (treasury nonce 0→1) → dev/register でフレッシュ identity (m0rhc57…) 作成 (treasury fund 100000 MORM) → **2 連続 VIEW_REWARD tx (cell_index=0,1) 署名+relay → 全 mempool 受理 → 2 block produce → viewer balance 100000 → 100002 + nonce 0 → 2 = 完全 chain apply 確認**。これで「HLS encoder pipeline ↔ MORM Chain VIEW_REWARD」が end-to-end で稼働 |
| **CDN Integration (opt-in playlist rewrite + warm-up)** | §5.4 (CDN加速層, 3原則 §1) | Phase 25Vc | `passkey_morm.py: --cdn-base-url <url>` CLI flag + `_rewrite_m3u8(text, cdn_base, content_id, rel_dir)` モジュール関数 (master.m3u8 sub-playlist refs + sub-playlist の `EXT-X-MAP:URI=` + bare segment lines を absolute CDN URL に書換)、`X-MORM-CDN-Rewrite: on` ヘッダ、`/api/morm/info` に `cdn_base_url` フィールド追加、起動 banner に `cdn=` status 追加、`morm-l1/ops/warm-up.sh` (master.m3u8 → 各 ladder index → 各 ladder の先頭N segments + init.mp4 を curl で warm) | ✅ 検証済 — 同一 storage に対して **origin-only mode (8804): m3u8 unchanged, X-MORM-CDN-Rewrite absent (3原則: origin-only でも完全動作する保証)**、**CDN-rewrite mode (8805, --cdn-base-url=https://cdn.morm.example): master.m3u8 の `1080p/index.m3u8` → `https://cdn.morm.example/api/video/<cid>/1080p/index.m3u8`、360p/index.m3u8 の `EXT-X-MAP:URI="init_3.mp4"` + segment lines も同様に CDN absolute、X-MORM-CDN-Rewrite: on**。warm-up.sh smoke test: 17 URL を 1.6ms 平均で 200 で warm |
| **Service Worker version check + 24h cache TTL** | §15 (PWA, stale-code mitigation) | Phase 26y | `morm-player/passkey_morm.py: _shell_bundle_version()` (sha256(sw.js + static/**/*) process-cached、any source change で hash 更新), `GET /sw-version` endpoint で JSON `{version}` 返却。`morm-player/static/sw.js: VERSION='morm-sw-v2'` (旧 v1 ユーザに force fresh install)、`SHELL_MAX_AGE_MS=24h` を `cacheFirst._cachedTooOld()` で `Date` header 経由 enforce、`_recheckVersionAndMaybePurge()` ヘルパが `/sw-version` を fetch → `morm-meta-v1` cache の `/__morm_sw_version__` と比較 → 不一致で SHELL+CELLS 一括 `caches.delete()` + META 更新、`activate` event + `message {type:'morm-sw-recheck'}` 両 trigger (page-driven recheck で SW スクリプト未変更時もカバー)、network 失敗時は stale でも返却 (offline path 維持) | ✅ E2E 検証 — META に `STALE_DEADBEEF` inject → `navigator.serviceWorker.controller.postMessage({type:'morm-sw-recheck'}, [port])` → SW が MessageChannel で `{mismatch:true}` 返却 → `caches.keys()` が `['morm-meta-v1']` のみに purge、META が live version `3d009ac60b986a16` に更新、`/sw-version` 直 GET でも同 hash 一致確認 |
| **Signaling DoS guards (per-IP rate + mailbox + peers cap)** | §15 (P2P/WebRTC mesh, signaling layer) | Phase 26r/s | `morm-player/passkey_morm.py: PasskeyMormServer.sig_rate_take(ip)` token-bucket per-IP, `_signal_rate_guard(path)` を `do_GET/do_POST` 先頭で `/api/signal/*` 専用適用 → 429 + `Retry-After`、`sig_send` で per-peer_id mailbox cap (`--signal-mailbox-max` default 256, oldest drop on overflow)、`sig_announce` で global peers cap (`--signal-peers-max` default 10000, TTL prune→LRU last_seen evict + inbox 同期削除)、CLI: `--signal-rate-per-ip` (default 15 RPS) / `--signal-burst-per-ip` (default 60) / `--signal-mailbox-max` / `--signal-peers-max`、起動 banner に `signal_caps=rps:N/burst:M/mailbox:K/peers:L` 表示 | ✅ E2E 検証 (`burst=5 rps=2 mailbox=3 peers=4`) — (a) 7連続 announce → 1-5 OK / 6-7 `REJECT 429 (signaling rate limit)` + 3s 後 token 補充で OK 復帰、(b) cap=3 mailbox に msg-0..msg-3 を `/api/signal/send` → inbox poll が `[msg-1, msg-2, msg-3]` を返却 (msg-0 oldest dropped)、(c) cap=4 peers に bb0000..bb0005 を announce → `/api/signal/peers` が `[bb0002, bb0003, bb0004, bb0005]` のみ返却 (bb0000/bb0001 LRU evicted) |
| **P2P content poisoning防御 (SHA256 vhash verify)** | §15 (P2P/WebRTC mesh) | Phase 26q | `morm-player/static/morm-p2p.js: _VHASH_RE = /\.([0-9a-f]{16})\.m4s$/`, `_vhashFromSegId(seg_id)`, `_sha256Hex16(arrayBuf)` (Web Crypto SubtleCrypto SHA-256 → first 8 bytes hex), `_verifyBlobAgainstSegId(blob, segId)`, `p2pTryFetchSegment` で受信 blob を verify → 不一致なら `stat.p2pRejects++` + cache 書かない + rememberSegment しない + 次 candidate へ、`.mp4` init は filename に vhash が無いため P2P 除外 (origin only)。`player-hls.html` に `P2P rejects` HUD tile + `player-hls.js:refreshP2PHud` で `s.p2pRejects ?? 0` 表示 | ✅ 検証済 — 749017 byte の本物 `1080p/seg_00001.bbf448059f876670.m4s` を origin から fetch → `crypto.subtle.digest('SHA-256')[:8 bytes hex]=bbf448059f876670` = filename vhash16 完全一致、第1byte XOR 0xff で改ざんすると `c89a9e6e8a6b56c2` mismatch 確認 (verify primitive が encoder の `_rewrite_segments_with_vhash` と完全互換)。HUD の `P2P rejects` tile screenshot で確認済 |
| **First-visit onboarding guide** | §6.2 (Mobile UX, 初回オンボーディング) | Phase onboarding | `morm-player/static/morm-guide.js` 新規 — `showGuide(pageKey, stepIds)` で逐次的 modal walkthrough (Step n / N counter + Skip + Back + Next/Got it + "Don't show again" checkbox)、`maybeShowFirstTimeGuide(pageKey, steps)` で localStorage `morm-guide-seen-v1` (set of pageKeys) 参照→未見なら自動起動、`mountHelpButton(parent, pageKey, steps)` で topbar に円形 `?` pill (aria-label + title 即時 i18n)、`STEPS = {upload[4], player[3], wallet[3]}` 定数 export。`morm-i18n.js` に `guide.*` namespace 追加 (~30 keys: next/prev/skip/done/dont_show + step_of + 各 page step.title/body)。modal 内で `morm-lang-changed` リッスンで mid-walkthrough の言語切替に追従、ESC/Enter/Arrow キーバインド、backdrop click で dismiss (= seen マーク無し → 次回再表示)、Don't show again のみ seen マーク (永続)。`/upload` (4 step: ようこそ → 9:16 撮影 → アップロード → フィード公開) / `/player-hls` (3 step: スワイプ → セグメント報酬 → P2P 共有) / `/wallet` (3 step: ポリシー概要 → アプリ別編集 → 一括取り消し) の各 init() に組込 | ✅ E2E preview 検証 — 初回 /wallet 訪問で auto-launch (JA、`ステップ 1 / 3` `ウォレットへようこそ`)、Next×2 で `アプリ別に制限を変更`→`一括取り消し` 進行、最終 step で `次回から表示しない` ack box → `了解` でクローズ + `morm-guide-seen-v1=["wallet"]` 永続。`?` button 再 trigger でも guide 復活、Skip で seen マーク無し dismiss。/upload で mid-guide language 切替 → `Welcome to MORM Creator` `Step 1 of 4` `Skip/Back/Next` に live 更新 → 戻すと JA 復帰、backdrop click で dismiss (seen 無マーク = 次回再表示確認)。/player-hls の portrait 動画再生中に modal overlay 描画も screenshot で確認 |
| **i18n (EN/JA) + language toggle** | §6.2 (Mobile, JP-first ユーザベース) | Phase i18n | `morm-player/static/morm-i18n.js` 新規 — EN/JA 二言語辞書 (~110 keys、namespaces: `common.*` / `confirm.*` / `cap.*` / `block.*` / `wallet.*` / `upload.*` / `player.*`)、`t(key, params)` で `{name}` 展開、`applyDom(root)` が `data-i18n="key"` / `data-i18n-placeholder` / `data-i18n-title` / `data-i18n-aria-label` 属性を一括書換、`setLang/currentLang` を localStorage `morm-lang-v1` に永続化、`navigator.language` からの auto-detect (`ja*` → ja, それ以外 → en)、`mountLangToggle(parent)` で `EN | 日本語` pill 描画 + active highlight + `morm-lang-changed` カスタムイベント発火。**i18n 適用範囲**: (i) `/wallet` (HTML data-i18n + JS 動的文字列 + dialog)、(ii) `/upload` (state-machine label `idle/live/recording/captured/uploading/done` + camera errors + log lines + drop fallback)、(iii) `/player-hls` (topbar pill + empty states)、(iv) `morm-identity.js: showTxConfirmDialog` (Phase 27f confirm modal)、(v) `morm-policy.js: showKindBlockedDialog + showExtraCeremonyDialog` (Phase 27g/h dialog)。dynamic 動的に再描画する dialog/policy は `await import('/static/morm-i18n.js')` で lazy load (i18n 未設定環境で fallback 動作も保つ) | ✅ E2E preview 検証 — `navigator.language=ja-*` で auto-detect により全 3 ページが JA 起動、`/wallet`: `アイデンティティ / アドレス / 残高 / ノンス / アプリ別ポリシー / 許可された種別 / 使用 / 上限 (24h) / 送金不可 / 編集 / 🚨 一括取り消し (1タップ)`、`/upload`: `縦型アップロード / 「カメラ起動」をタップして開始 / カメラ起動 / カメラ切替 / 撮影破棄 / ▶ フィード / ジョブ・状態・バイト・経過・出力ファイル数・コンテンツ`、`/player-hls`: `縦型フィード`、各 topbar に `EN | 日本語` toggle pill 表示 (active=日本語 cyan highlight)。setLang('en') → setLang('ja') の往復動作 + screenshot 取得済 |
| **Solidity Slither + Echidna audit pass** | §15 (EVM Bridge, sign-off) | Phase 26f | Slither 0.11.5 を `morm-chain/` 全 Solidity に対して run、初回 28 findings (High=2/Medium=2/Low=15/Info=9) → 修正した実バグ: (a) `MORMEscrow.createOrder` の **CEI 違反 reentrancy-eth** (treasury.call が orders[orderId] 書込み前) を CEI 順に並び替え + 詳細コメント追記、(b) `MORMBridgeMS.unlock` の **arbitrary-send-eth** + uninitialized-local は M-of-N 署名 gate 済 → docstring 監査ノート + `address last = address(0); uint256 valid = 0;` 明示初期化 + `slither-disable-next-line arbitrary-send-eth` 単行抑制。再 run で **High=0 / Medium=0** baseline 達成。Echidna 2.3.2 で `morm-chain/test/echidna/EchidnaBridgeMS.sol` + `echidna.yaml` 新規 — 4 不変条件 (`unlocked` 単調性 / `lockNonce` 単調性 / `bridge balance ≥ totalLocked - totalUnlocked` solvency / `threshold` immutability) を fuzz testLimit=50000 / seqLen=50 / 4 workers で実行 | ✅ Slither High+Medium 0 件 / Echidna 4/4 PASS (50,118 calls executed, coverage 2274 instr, corpus 4 seqs) / `forge test` 32/32 PASS で regression なし。残 Low/Informational (reentrancy-events 9 + low-level-calls 6 + timestamp 4 + ...) は bridge/escrow 設計上の必然 (`recipient.call{value:}`) と documented design choice、本番 sign-off に支障なし |
| **Wallet policy (per-app cap + kind whitelist + 1-tap revoke)** | §15 (Browser/PWA, hostile-script 防御) | Phase 27g/h/i | `morm-player/static/morm-policy.js` 新規 — `getPolicy(appKey)` (lazy-seeded from `DEFAULT_POLICIES` per pathname segment: shop / admin / auth-morm / player-hls / upload / wallet)、`decideTx({kind, payload})` で 27h `kind ∉ allowedKinds → ok:false, reason:"kind-not-allowed"` 即 reject、27g `cap > 0 AND spent + amount > cap → requireExtra:true`、`recordSpend(appKey, kind, amount)` で 24h sliding window 維持 (TRANSFER/BRIDGE_BURN/CREATE_ORDER の sender 流出のみ tracking)、`revokeAll()` で `morm-policy-v1` + `morm-spend-v1` localStorage を全 wipe。`morm-identity.js: signTxWithConfirm` が confirm dialog の前に `decideTx` を call、blocked → `showKindBlockedDialog` (赤、Dismiss のみ)、over-cap → `showExtraCeremonyDialog` (赤+ack-checkbox 必須+sender hex 表示)、通常 → 既存 27f confirm dialog。`/wallet` (新規 page) で 6 行 policy table + edit 編集 inline form + 1-tap revoke button、`passkey_morm.py: do_GET` に `/wallet` route 追加 | ✅ E2E 検証 — preview /wallet でデフォルト 6 app (admin/auth-morm/player-hls/shop/upload/wallet) seeded 確認、screenshot で UI 視覚確認 (red "🚨 Revoke all (1-tap)" button + 5 列 table)。`morm-policy.decideTx` 直接 exercise: (a) `kind=31 (REGISTER_PRODUCER)` from /wallet → `{ok:false, reason:"kind-not-allowed", allowed:["TRANSFER"]}`、(b) `TRANSFER amount=1000` → `requireExtra:false`、(c) `TRANSFER amount=200000` (cap=100000) → `{requireExtra:true, after:200000, cap:100000}`、(d) `recordSpend(...,90000)` 後 `amount=30000` → `{requireExtra:true, spent:90000, after:120000}` で 24h cumulative 動作確認、(e) `revokeAll()` で localStorage 両 key が null に消去 |
| **DAG incremental rebuild (linear/absorbing case)** | §4.3 (DAG完成形 — 性能、2nd pass) | Phase 24b incremental | `morm-l1/morm_l1/state.py: State._can_incremental_apply(block, new_tips)` で `block.parents ⊆ _materialized_frontier` AND `new_tips == (_materialized_frontier - block.parents) ∪ {block.hash()}` を判定、`State._apply_block_incremental(c, block)` で `_apply_tx` を block.txs に直接適用 (skip-on-StateError 維持)。`_apply_block_dag` の `_rebuild_materialized_state` 呼び出しを `if _can_incremental_apply: _apply_block_incremental else: _rebuild_materialized_state` に置換。`MORM_FORCE_FULL_REBUILD=1` env で incremental 経路を強制無効化 (regression test 用)。canonical_tx_order が `(canonical_height, sender, nonce, hash)` でソートし、新 block の txs は最大 height 帯で末尾に並ぶため、incremental と canonical replay が **bit-for-bit equivalent**。DAG sibling ケース (parents ⊄ frontier または non-block 新 tip 出現) は wipe+replay に fall-back | ✅ Bit-for-bit 検証 — 同一 producer seed + 同一 tx 列で `MORM_FORCE_FULL_REBUILD=1` (slow path) と default (incremental) を両方走らせ、3 waves × 30 transfers で state_root `b33577a1cd63cad0…`, `afdf484b98f0de83…`, `fcbaad80b2704fbf…` が完全一致。canonical replay と等価であることを確認、incremental が `_rebuild_materialized_state` の O(total ancestor txs) を O(extras = block.txs) にする |
| **DAG canonical-replay throughput optimization** | §4.3 (DAG完成形 — 性能) | Phase 24b throughput | `morm-l1/morm_l1/state.py: State.__init__` に `_materialized_frontier: frozenset \| None` + `_materialized_root: bytes \| None` + `_merge_cache: OrderedDict[frozenset, bytes]` (LRU 256) を追加。`_merge_cache_get/_put` ヘルパ。`_try_savepoint_shortcut(frontier_hashes, extra_txs, ...)` で **frontier == _materialized_frontier** のとき `BEGIN IMMEDIATE` で extras を persistent db に直接 apply → `_compute_state_root` → `ROLLBACK` (tempfile replica + genesis replay を完全スキップ、O(ancestors) → O(extras))。`compute_frontier_state_root` は (1) shortcut → (2) `_merge_cache` 参照 → (3) 既存 tempfile 経由の順、no-extras 結果は cache に積む。`replay_with_filter` も同 shortcut パターンを採用。`_apply_block_dag` の COMMIT 後 (markers が unpersisted state を指す race を回避) に `_materialized_frontier/root` を更新 + `_merge_cache_put`。`_rebuild_materialized_state` の docstring を「caller が markers をセットする」に修正。`MORM_PRODUCER_RATE_WINDOW_MS` env で rate window を可変化 (24d benchmark 用) | ✅ E2E 検証 — 単一 producer DAG mode (lockdown disabled, 200ms rate window) で 3 wave × 30 tx を逐次 submit → 各 wave が独立 block を seal、`head=1/2/3` と `state_root e0c8cdcf… → 2716b18a… → 4e50efa9…` の決定論的進化を確認。wave 2/3 の verify path は `_materialized_frontier == frontier_hashes` でショートカット発動 (genesis 全 replay スキップ)。state_root mismatch 不発 = shortcut が slow path と同じ root を返すことを示す (strict_extras=True 経路の正当性)。`_apply_block_dag` 内の rate-limit reject ログも観測済 (24d 既存機能、rebuild の cache marker 巻戻しは raise 経由で skip = correctness 維持) |
| **Genesis lockdown window** | §15 (chain bootstrap、attacker eclipse 防御) | Phase 26e | `morm-l1/morm_l1/state.py: State.GENESIS_LOCKDOWN_HEIGHT_DEFAULT=100`, `State.__init__(..., genesis_lockdown_height=...)`, `State.genesis_lockdown_active(height)` (= `producers.empty AND height < lockdown_height`)、`apply_block` 先頭で `crypto.address(block.header.producer) != self.treasury` なら `26e genesis lockdown` raise (single-chain + dag-mode 両 path をカバー、import-side も含めて apply_block を funnel する全経路で gate)、`node.py:Node.__init__(..., genesis_lockdown_height=None)` を State に thread-through、`produce_one` 内で `crypto.address(self.producer_pub) != self.state.treasury` なら lockdown 中は自己 production を skip。`cli.py: --genesis-lockdown-height` (default 100, 0 で disable)、`rpc.py:/info` に `genesis_lockdown_height` + `genesis_lockdown_active` 露出。escape hatch: `height >= lockdown_height` または最初の REGISTER_PRODUCER で auto 解除 (silent treasury による永久 deadlock 回避) | ✅ **3 シナリオ E2E 検証**: (a) 非 treasury producer + lockdown=5 → tx submit 後 4s でも head=0 (sealed されない)、(b) 同 data dir を treasury producer 鍵で再起動 → tx 再 submit → `[producer] sealed #1` で head=1、(c) treasury が REGISTER_PRODUCER tx 投稿 → block sealed → `genesis_lockdown_active=False` に auto 切替、producers リストに `rogue` 追加、next_slot_owner が `m0rvlbsap…` (新 producer) に切替確認 |
| **Mempool DoS guards (size cap + per-sender quota)** | §15 (gateway/RPC, fee floor 代替) | Phase 26c | `morm-l1/morm_l1/node.py: MEMPOOL_MAX_TXS_DEFAULT=5000 / MEMPOOL_MAX_PER_SENDER_DEFAULT=32`, `Node.__init__(..., mempool_max_txs, mempool_max_per_sender)`, `Node.submit_tx` で signature 検証直後 + BEFORE 受理時に global cap → per-sender cap の順で enforce、`_sender_count: dict[bytes,int]` を維持、`drain_mempool` / `_reinsert_mempool` / `import_block` で counter 同期、`cli.py: --mempool-max-txs / --mempool-max-per-sender`, `rpc.py: /info` で両 cap 露出 + `/tx` 失敗時 `error: "mempool full" \| "per-sender quota exceeded" \| "tx invalid (signature/nonce)"` + `limit` 返却 | ✅ E2E 検証 — `--mempool-max-txs 8 --mempool-max-per-sender 4 --no-produce` で sender A が 5 stake tx 投入 → 1-4 OK / 5th `REJECT (per-sender quota exceeded)`、sender B が 5 stake tx 投入 → 1-4 OK / 5th `REJECT (mempool full)`、stderr に `[mempool] reject: per-sender cap reached for ... (4/4)` / `global cap reached (8/8)` 記録、 `/info` に `mempool_max_txs/per_sender` 反映。fee 機構自体は未導入のため "fee floor" は per-sender quota で代替 |
| **OS-independent federated node installer** | §11 (運用), §1 (3原則 — 法人なし運用) | Phase 30a-e | `docker/Dockerfile.l1` (slim 254MB / 56MB compressed、cryptography + aioquic) + `docker/Dockerfile.gateway` (1.05GB / 266MB、ffmpeg + numpy + webauthn + web3、Phase 25Vb HLS pipeline 含む) + `docker/Dockerfile.edge` (212MB / 46MB、stdlib only) の 3 multi-stage 構成、それぞれ `docker/entrypoints/{l1,gateway,edge}-entrypoint.sh` に env-driven CLI argv 翻訳。`docker/morm-node.docker-compose.yml` で l1+gateway+edge を internal network で wire (gateway→l1 = `http://l1:8900` named DNS)、healthcheck付き、optional cloudflared sidecar。`docker/.env.example` に Phase 28a/b bridge config + treasury keyfile bind 含む全 env 仕様。`docker/init.sh` (idempotent first-boot key gen: producer + treasury seed → 0o600 file → .env patch)。**Phase 30c federation seed list**: `morm-l1/morm_l1/seeds.json` (baked-in、append-only、`updated_at` + `discovery: { dns_seed, github_raw_seeds_url, ipfs_seed_cid }` 並列 update channel) + `morm-l1/morm_l1/seed_loader.py` (`load_peer_urls(explicit_peers, data_dir, public_url, enable_discovery)` で explicit→local-mutable→baked→discovery を dedup-merge、self exclusion、CLI inspector `python -m morm_l1.seed_loader`)、`cli.py:cmd_node` が `--peers` 空時に自動呼び出し + `--no-seed-discovery` flag 追加。**Phase 30e CI**: `.github/workflows/publish-images.yml` で multi-arch (linux/amd64 + linux/arm64) の semver tag 駆動 publish to `ghcr.io/<owner>/morm-{l1,gateway,edge}` (rationale: `morm` username が Docker Hub で別人squat、ghcr は GitHub repo namespace に紐づくので名前空間争奪なし)。**Phase 30d installer**: `docker/install.sh` (curl\|sh、Docker daemon check + repo clone/pull + init.sh 実行 + ghcr.io pull → 失敗時は build fallback + `up -d` + healthcheck poll + 完了時 URL 案内) | ✅ E2E 検証 (Docker Desktop 29.2.1) — `docker/init.sh` で producer `m0rluwixip…` + treasury `m0rmwh35qn…` 自動生成、3 image build 全成功、`docker compose up -d` で l1/gateway/edge 起動、L1 RPC `/info` 即応、Gateway `/api/morm/info` が `rpc=http://l1:8900` で internal network 解決、`/swap` HTTP 200、`/wallet` HTTP 200、`/sw-version` 588a9bbc...。`seed_loader._cli` で空 list / explicit override / no-discovery 各 path 動作、cli.py `--peers` 空時 stdout に `[seeds] resolved N peers from federation list (...)` 確認。`morm-l1/.venv` を使った fresh L1 boot も seed_loader 経由で正常 (head=0)、QUIC enforcement (`peers AND not --quic` → fatal exit) も Phase 25c の挙動を維持。**残**: ghcr.io 実 push (.github/workflows をトリガするには git remote 必要)、Phase 30f tunnel sidecar (cloudflared / Tailscale Funnel) は compose.yml に commented-out で stub のみ、Phase 30g admin UI 拡張 |
| **M-of-N quorum bridge E2E (`scenario_swap_quorum.py`)** | §1, §4, §9.5 / §15 (single-relayer trust 排除) | Phase 13b-PoC | `morm-chain/script/DeployBridgeMS.s.sol` 新規 (anvil acct #5/#6/#7 を ascending sort で signers, threshold=2) で MORMBridgeMS deploy → `0x2279B7A0a67D…`。`scenario_swap_quorum.py` 新規でフレッシュ L1 8910 + 3 ed25519 validators + treasury bootstrap key を使い、**lock-mint-burn-unlock 完全 cycle を single-key relayer 無しで** orchestration。`/tmp/quorum-keys.json` (chmod 600) に validator seeds + treasury bootstrap + producer seed。**E2E flow**: ① `REGISTER_TREASURY_SIGNERS({signers:[v0,v1,v2], threshold:2})` で single-key bootstrap → multi-sig active / ② alice (anvil #2) → `MORMBridgeMS.lock(0.05 ETH, bytes20)` / ③ 3 validators が `multisig_signing_bytes(BRIDGE_MINT, payload, treasury_addr, treasury_nonce)` を ed25519 cosign / ④ validator-0 が 2-of-3 cosigs を `MULTISIG_TX` に wrap して L1 /tx submit → state.py が threshold + signer membership + nonce match を検証して inner BRIDGE_MINT を treasury sender で dispatch → alice MORM 残高着地 / ⑤ alice 鍵で `BRIDGE_BURN({amount:0.02 ETH wei, evm_recipient:bob})` 署名 → /tx → /bridge/burns へ row 追加 / ⑥ 3 validators が EVM `unlockDigest(bob, amt, burnId)` を `eth_sign` 形式 (encode_defunct prefix) で sign / ⑦ 最小 address 2 つを ascending sorted で `MORMBridgeMS.unlock(bob, amt, burnId, sigs[])` call → bob EVM Δ confirmed | ✅ E2E PASS — alice 0.05 ETH lock → 2-of-3 cosig → L1 mint 50000000000000000 µMORM / 0.02 ETH burn → 2-of-3 EVM sig → bob receives 20000000000000000 wei、alice L1 残高 0.03 ETH (= 0.05 mint − 0.02 burn)、bridge contract balance correct, lockNonce/unlockNonce ともに動作。**no single-key relayer at any step**。残: in-process orchestration を N validator processes + HTTP cosignature gossip に分散化 (BRIDGE-DESIGN.md §5.3、~4-5h estimate) |
| **Bridge design note (`BRIDGE-DESIGN.md`)** | §1, §4, §9.5 / §15 (multi-currency, threat model, M-of-N migration plan) | Phase 28-doc | `morm-l1/ops/BRIDGE-DESIGN.md` 新規 — Phase 28a/28b の operational reference + Phase 13b M-of-N 移行設計 + threat model + 3 contract types (MORMBridge / MORMBridgeERC20 / MORMBridgeMS / MORMBridgeOptimistic) の trust model 比較 + USDC 6-decimal vs ETH 18-decimal の取り扱い + m0r/0x form 修正の設計判断 + open issues (treasury cap depletion / 実 MetaMask 検証残 / `scenario_swap.py` の `resp.ok` チェック追加要) + deployed addresses (Anvil 31337) + selectors 一覧 | ✅ 文書のみ (実装ガイド) — Whitepaper §1/§4/§9.5/§15 から引用可能 |
| **scenario_swap{,_usdc}.py m0r-form 修正** | §1 (PoC scenario) | Phase 28-fix | `scenario_swap.py:54-55` + `scenario_swap_usdc.py:45-46` で `bytes.fromhex(crypto.address(pub)[2:])` → `crypto.address_to_bytes20(crypto.address(pub))` に置換 (Phase 18 で `crypto.address` が `m0r…` を返すようになったが scenario の comment は stale `# "0x..."` のままで、`bytes.fromhex` が m 文字で fail していた) | ✅ 検証済 — `scenario_swap_usdc.py` で approve(100 USDC) → lockToken → 1s mint → BRIDGE_BURN(40 USDC) → 2s unlockToken → bob USDC Δ=40 完走、`scenario_swap.py` の m0r→bytes20 変換も `crypto.address_to_bytes20` で正常 (treasury cap depletion で 2nd run の mint は silent reject、これは別 known issue) |
| **Bridge UI USDC tab (ERC-20 ↔ USDC.morm)** | §1, §4, §9.5 (multi-currency on/off-ramp) | Phase 28b | `morm-player/static/swap.html` に 3rd tab + USDC sub-tab (Lock USDC / Burn USDC) + Bridge status panel に USDC token / bridge / locked block 追加。`swap.js` に MockUSDC 用 selectors (`approve` 0x095ea7b3 / `balanceOf` 0x70a08231 / `allowance` 0xdd62ed3e / `lockToken(address,uint256,bytes20)` 0x8b1a8f0d / `mint(address,uint256)` 0x40c10f19) + USDC 6-decimal helpers (`usdcToRaw` / `rawToUsdc`) + `fetchUsdcBalance/Allowance` + `refreshUsdcEvmStats/L1Balance` (5s auto-refresh)。**Lock USDC flow**: `approve(bridge, amount) → wait receipt → enable Lock → lockToken(usdc, amount, bytes20) → wait receipt → poll /account/<m0r…>.tokens.USDC` で BRIDGE_MINT(token=USDC) 着地確認。**Burn USDC flow**: passkey で `BRIDGE_BURN { amount, evm_recipient, token:'USDC', token_address }` 署名 → /api/relay/morm-tx → /bridge/burns polling で `evm_unlocked=1` 確認。test 用 PoC faucet button (1000 USDC mint)。`passkey_morm.py: --erc20-bridge-addr / --usdc-addr` CLI flags + `/api/morm/bridge` レスポンスに両 address 追加 (両方 set 時のみ JS が USDC tab を unhide)。`morm-i18n.js: swap.usdc.*` namespace + `swap.status.usdc_*` (~22 keys × EN/JA = 44 strings)。`morm-policy.js` の swap policy (BRIDGE_BURN whitelist + 100M cap) は USDC でもそのまま再利用 (kind=21 共通) | ✅ E2E 検証 — DeployBridgeERC20.s.sol で MockUSDC `0xe7f1725e7734…` + MORMBridgeERC20 `0x9fe46736679d…` を Anvil に deploy、relayer.py を 3argv (eth bridge / erc20 bridge / usdc) で再起動。**Lock USDC E2E**: alice (anvil acct #0, deployer, 10000 USDC initial) → approve(bridge, 100 USDC) → lockToken(USDC, 100×10⁶, m0rbccaglv…) → relayer が **1s 以内** に L1 で BRIDGE_MINT(token=USDC) で `account_tokens.USDC=100000000` を `m0rbccaglv…` に着地、`/account/<m0r>.tokens.USDC` で 100 USDC.morm 確認。**Burn USDC E2E**: 同一 alice 鍵で BRIDGE_BURN(amount=40×10⁶, evm_recipient=bob 0x90F7…, token='USDC', token_address=0xe7f17…) → relayer が **2s 以内** に EVM `unlockToken(usdc, bob, 40 USDC, burn_id)` 発火、bob USDC Δ=40 USDC、alice L1 USDC.morm 残 60、bridge USDC held 60、lockNonce=1, unlockNonce=1。Browser preview UI: USDC tab unhide、Bridge status の USDC token/bridge/locked block live、5s auto-refresh で `60 USDC (60000000 raw)` 反映、ja auto-detect で全 i18n 適用 (`USDC ブリッジ (ERC-20)` / `保有 USDC` / `ブリッジへの許可額` / `1000 USDC をミント (テスト)`)、3-tab switching + USDC sub-tab switching DOM 動作確認 |
| **Bridge UI (`/swap`, EVM↔MORM browser entry-points)** | §1, §4 (multi-currency on/off-ramp) | Phase 28a | `morm-player/static/swap.{html,js}` 新規 — 720px 幅 2-tab レイアウト (Lock / Burn) + Bridge status panel (contract addr / locked ETH / lockNonce / unlockNonce / pending burns / EVM chain / MORM RPC、5 秒間隔 auto-refresh)。Lock 側は EIP-1193 (`window.ethereum`) で MetaMask 接続 → `wallet_switchEthereumChain` (4902 → `wallet_addEthereumChain` で chain 自動追加) → calldata `selector(lock(bytes20)) ‖ left-pad-32(bytes20)` を `eth_sendTransaction` に渡し、receipt poll 後に `/account/<m0r…>` を 800ms 間隔で polling して relayer の BRIDGE_MINT 着地を確認、MetaMask 不在時は `cast send` fallback コマンドを表示。Burn 側は完全 walletless: `signTxWithConfirm({kind:21, payload:{amount, evm_recipient, token:'MORM'}})` で 27f confirm dialog + 27g/h policy gate を経由 → POST `/api/relay/morm-tx` → `/bridge/burns?only_pending=1` polling で `evm_unlocked=1` を確認。`passkey_morm.py:do_GET` に `/swap` route + `/api/morm/bridge` endpoint (`{bridge_addr, evm_rpc, evm_chain_id}`) + CLI flag `--bridge-addr / --evm-rpc / --evm-chain-id` 追加。`morm-policy.js: DEFAULT_POLICIES.swap = { allowedKinds:[21 BRIDGE_BURN], dailyCapMorm:100_000_000 }` を追加。`morm-i18n.js` に `swap.*` + `guide.swap.*` namespace (~38 keys × EN/JA = 76 strings)、`morm-guide.js: STEPS.swap` 4-step (welcome → MetaMask 接続 → Lock 操作 → Burn 操作 + 状態監視) 追加。**relayer fix (Phase 28a 副次)**: `relayer.py: _submit_mint` の `morm_addr` を `"0x" + bytes(...).hex()` → `crypto.bytes20_to_address(bytes(...))` に変更 — bridge mint 残高を m0r-native account に着地させ、`/wallet` UI と同じ口座から閲覧/送金可能にした。Phase 18 の `BRIDGE_MINT recipient may be either m0r-native or 0x-legacy` 仕様の中で native 側を選択 | ✅ E2E 検証 (preview 8801 + Anvil 8545 + Bridge `0x5fbdb2…` + relayer 27404→29253) — (a) /swap 初回訪問: status panel が live (`0.0000 ETH locked, lockNonce=0`)、ja auto-detect で全 i18n 適用、onboarding guide auto-launch (4-step、JA)、language toggle EN/JA bidirectional、tab switch Lock↔Burn が DOM display 切替、(b) **Lock E2E**: alice (anvil acct #2, 0x3C44…) が新規 m0rifqt3… 宛に 0.2 ETH lock → relayer が **2s 以内** に BRIDGE_MINT で 200000000000000000 µMORM を m0r native form に着地、`/account/m0rifqt3…` が `balance=200000000000000000` (旧 0x form は 0、修正反映確認)、(c) **Burn E2E**: alice 鍵から BRIDGE_BURN(amount=0.1 ETH 相当, evm_recipient=bob 0x90F7…) → relayer が **1s 以内** に EVM `unlock()` 発火、bob EVM Δ=100000000000000000 wei、alice L1 残高 100000000000000000 残、(d) UI status panel 5s auto-refresh が lock/burn 直後に live 反映 (`0.25 ETH locked, lockNonce=3, unlockNonce=1`)、(e) console errors 0 件。残: 実 MetaMask in-browser test は preview 環境に `window.ethereum` 注入なし → real Chrome tab で別途必要 (Lock 側のみ; Burn は preview 検証で full coverage 済) |
| **P2P mesh on `.m4s` (Phase 22-Video)** | §4.1, §5.4 (Phase 22 を HLS pipeline へ) | Phase 22-Video | `morm-player/static/morm-p2p.js` を整理: announce/serve のキー単位を `cell_index:int` から `seg_id:string ("1080p/seg_NNNNN.<vhash>.m4s")` に変更、SDP/DC protocol を `kind: cell-request` → `kind: segment-request` に rename、cache 名 `morm-cells-v1` → `morm-hls-v1`、URL pattern `/api/cell/...` → `/api/video/<cid>/<seg_id>`、`?morm-peer=<id>` URL override (multi-iframe テスト用)、`?p2p-debug=1` で signal/PC state ログ。`player-hls.js`: hls.js `fLoader` に `P2PFragLoader extends Hls.DefaultConfig.loader` を実装 — `parseSegUrl(url)` で .m4s/.mp4 のみ抽出 → `p2pTryFetchSegment(cid, segId, 1500ms)` を first-try、miss なら `super.load` でorigin、wrapped onSuccess が **全 successful load** で `seedP2PCache + rememberSegment` (FRAG_LOADED に依存しないので ABR切替で破棄された segment も serve 可)、`?force-hlsjs=1` で iOS Safari でも hls.js 経路強制、`p2p-hits/bytes/peers/ICE` HUD pill。修正: stuck `RTCPeerConnection` 自動 drop on timeout/failed/disconnected (リトライで fresh handshake 強制)、inbox poll を sequential `await handleSignal(m)` 化 (parallel 実行で ICE candidate が `setRemoteDescription` 前にロストするバグ修正)、POLL_INTERVAL_MS 800→200ms (handshake roundtrip <2s) | ✅ 検証済 (preview 8801, content `61361f4d7df3eb48`): announce が **HLS segment id 文字列 5件** (`1080p/init_0.mp4` + `1080p/seg_00000…00003.<vhash>.m4s`) を `/api/signal/peers/<cid>` 経由で配信、curl-faked peer B 投入 → peer A の `peer_id/cells/last_seen` を `/api/signal/peers` で list 取得 OK、HUD `peers=2` 即時反映、cache key 一致 (相対 vs 絶対 URL 両方 hit)。2-iframe peer A↔B 試験で **WebRTC ICE handshake が `connected` 状態到達** (`serving ice state checking → connecting → connected → DC opened` ログで観測) — 完全な byte-flow は Chrome iframe timer throttling (preview 環境固有) で answer 受信が timeout 後にずれ込み、real 2-tab manual test に依存。ICE candidate parallel-dispatch race を sequential 化で解消、stuck-PC 自動 drop で retry 経路復旧、これにより protocol layer は green light |

合計: **69 Phase 完全実装** + Phase 28-doc / 28-fix + Phase 30a-e (Docker compose federated installer)。Phase 24a-d (DAG完成) + **24b throughput** (SAVEPOINT shortcut + merge_cache) + **24b incremental rebuild** (linear case bit-equivalent) + Phase 25a/b/c (QUIC一連) + Phase 26a/b/c/e/f/q/r/s/u/v/w/x/y + Phase 27f/g/h/i (Web hardening + Multi-sig + Tx confirm + Mempool DoS + Solidity audit + P2P content verify + Signaling DoS + SW version check + Genesis lockdown + DAG throughput + DAG incremental rebuild + Wallet policy) + **i18n EN/JA** + **First-visit onboarding guide** + **Phase 25Va/Vb/Vc + Phase 22-Video + Portrait pivot + Swipe feed + Camera upload UI (HLS Encoder + Origin + Player + Upload Pipeline + Auto-Register + CDN integration + P2P `.m4s` mesh + content poisoning 防御 + signaling DoS 防御 + SW stale-code mitigation + 縦型 9:16 mobile-first + scroll-snap native swipe feed + camera-first creator UX = "縦型カメラ録画→アップロード→エンコード→チェーン登録→モバイル縦型スワイプ再生→視聴報酬獲得 + P2P 加速 + 改ざん耐性 + flood 耐性 + コード鮮度保証 + TikTok/Reels 完全 UX 互換" の creator-to-viewer 全 loop 完成)** 全揃。**🎉 SECURITY-DESIGN §5 must-have + 順次対応 §🟡 26c+26q+26r/s+26y + Phase 25-Video 全段階 + Phase 22 を HLS pipeline へ吸収 達成**。次候補: 順次対応 §🟡 残 (26e genesis lockdown / 26f Solidity audit / 26t TURN bandwidth quota / 27g/h/i wallet UI 強化) / 24b throughput 最適化 / 既存 WebM cell content の HLS migration script。

**重要な副次fix (2026-04-26)**:
- `state.py:get_account` が `_ensure_account` を呼んでいたため、`/account/<addr>` の読み取り HTTP query で persistent state に空 row が INSERT されていた → Phase 24b の materialized-state-canonical-equality 要件を踏んだことで顕在化、read-only 化済 (Phase 11d 以前から存在した pre-existing bug)。
- `state.py:_canonical_tx_order` のソートキーに `(sender, nonce)` 追加 → 同一送信者の連続 tx (treasury bootstrap、viewer reward burst 等) が tx_hash 順だと nonce mismatch で skip されるバグを修正。DAG-DESIGN.md §4 の元仕様 `(height, tx.hash())` だけでは不十分だった (open question 1 への明示的解答)。
- `node.py:_produce_dag` で self-apply 失敗時 (rate-limit reject 等) に drained tx が失われる問題修正 → `_reinsert_mempool(applied)` 追加。

---

## 2. 設計確定 / 実装未着手

| 領域 | Whitepaper 章 | 設計ドキュメント | 工数見積 |
|---|---|---|---|
| **DAG 24b 性能最適化 (merge_cache, canonical replay差分計算)** | §4.3 (DAG完成形 — 性能) | DAG-DESIGN.md §8 open question 2 | ~6-10h (correctness は Phase 24b で達成済、本項は throughput regression 解消用) |
| **QUIC gossip transport (aioquic + datagrams RFC 9221)** | §4.2 | `morm-l1/ops/QUIC-DESIGN.md` (Phase 25a/b/c) | 29h |
| **BFT vote tx (24c の上に honest-→ Byzantine 拡張)** | §4.3 (将来) | (未着手, DAG 24c完了後に書く) | TBD |
| **セキュリティ強化全般** (Treasury multi-sig / Tx confirm dialog / フィッシング対策 / DoS rate limit / Bridge audit ほか) | §15 (リスクと対策) | `morm-l1/ops/SECURITY-DESIGN.md` (Phase 26a-27i) | 36h (must-have) + 50h+ (順次) |

これら **未実装の項目を Whitepaper で「実装済」とは絶対に書かない**。
"設計確定" or "次フェーズ" として扱う。

---

## 3. 数値 — Whitepaper 引用可能な観測値

### 3.1 ベンチマーク (実機・localhost 3-node)

| 指標 | 値 | 出典 |
|---|---|---|
| Phase 17 single-chain throughput cap | ~1 block/sec | `node.py:BLOCK_INTERVAL=1.0` |
| Phase 23 state convergence (30 transfers, 3 producers) | head=33, finalized_height=30 (FINALITY_DEPTH=3) | `3NODE-TESTNET.md` Phase 23 §verification |
| Phase 23a slot分布の公平化 | A=13 / B=11 / C=9 (Phase 23 同条件で A=23/B=9/C=0 だった) | `3NODE-TESTNET.md` Phase 23a §landed |
| Phase 24a DAG widening | max_width=3 at heights 5/6/7 (BLOCK_INTERVAL=0.05s, 3 senders × 150 tx) | `3NODE-TESTNET.md` Phase 24a §landed |
| Phase 24a state divergence (設計通り) | 2 distinct state_roots out of 3 nodes | 同上 |
| **Phase 24b state convergence (DAG下で frontier-relative state)** | **state_root + frontier_root が3ノード完全一致** at max_w=3 / head_w=3 (BLOCK_INTERVAL=0.1s, 3 senders × 150 tx) | `3NODE-TESTNET.md` Phase 24b §landed |
| Phase 24b throughput regression (既知トレードオフ) | 高負荷下で sealing rate が canonical replay overhead に比例して低下 — `merge_cache` 最適化で解消予定 (§2 残スコープ) | 同上 |
| **Phase 24c common-ancestor finality (DAG下)** | finalized=head−1 (3 producers / threshold=⌈⅔×3⌉=2 / head_w=3 で全 tip 共通祖先) — Phase 17 K=3 より2 block タイト | `3NODE-TESTNET.md` Phase 24c §landed |
| **Phase 24d per-producer rate limit (R=1 with no PoUW)** | 単一ノード R=1 で **10004ms** きっかりのブロック間隔。3-node DAG (R=1×3) で全 15 tx 完走 + state収束維持 + max_w=3 (DAG並列性影響なし) | `3NODE-TESTNET.md` Phase 24d §landed |
| Phase 22b TURN allocation | coturn `ALLOCATE processed, success`, gateway-issued HMAC creds で 100% 認証成功 | `morm-l1/ops/TURN.md` §verification |
| Solidity Forge tests | MORMEscrow 11/11 + Bridge 7/7 + ERC20 4/4 + MS 5/5 + Optimistic 5/5 = **32/32** | `morm-chain/test/` |

### 3.2 暗号 / プロトコル定数

| 定数 | 値 | コード |
|---|---|---|
| アドレス形式 (native) | `m0r` + base32(BLAKE2b-32(pubkey)[-20:])、35 chars lowercase | `crypto.py:address()` |
| アドレス形式 (legacy/EVM) | `0x` + 40 hex (bytes20) | `crypto.py:bytes20_to_address()` |
| 鍵タイプ (L1) | ed25519 | `crypto.py` |
| 鍵タイプ (Solidity bridge) | secp256k1 (Ethereum 互換) | `morm-chain/` |
| FEE_BPS | 100 / 10000 = 1% | `state.py` 全所、Solidity |
| FINALITY_DEPTH | 3 blocks | `morm-l1/morm_l1/__init__.py` |
| BLOCK_INTERVAL (default) | 1.0s | `node.py` (env `MORM_BLOCK_INTERVAL` で override 可) |
| Treasury 初期供給 | 10^18 µMORM = 10^18 MORM (wei単位ブリッジ対応) | `state.py:State.__init__` |
| Cell 長さ | 3秒 (50/10サイクルのため) | `morm-core/morm_core/encoder.py` |
| TURN 認証方式 | coturn use-auth-secret (HMAC-SHA1, TTL 600s) | `passkey_morm.py:ice_servers_for()` |
| WebRTC ICE servers | STUN既定 (Google) + 任意TURN (per-peer ephemeral) | `morm-p2p.js` |
| PWA SW cache 戦略 | shell=cache-first, /api/cell/*=stale-while-revalidate, API=network-first | `static/sw.js` |

### 3.3 V-Hash + Generation ID 仕様

| 項目 | 値 |
|---|---|
| pHash | DCT 32×32 → 上位8×8 = 64bit | `morm-core/morm_core/vhash.py` |
| 音声FP | mel-spectrogram の局所ピーク fingerprint | 同 |
| Generation ID | `sha256(prompt \| seed \| ts_bucket)` | `aiservice.py:gen_id()` |
| AI署名 | ed25519(seed, gen_id ‖ cid) | 同 |
| 重複判定 closeness | hamming distance ≤ 8 / 64 (12.5%) | `screening.py` |

---

## 4. 動作中の本番サービス (2026-04-25 時点)

| ポート | サービス | 用途 |
|---|---|---|
| `127.0.0.1:8800` | passkey_server.py (Phase 7) | Anvil/secp256k1 用 (legacy) |
| `127.0.0.1:8801` | passkey_morm.py (Phase 10e/22b) | MORM L1 用 gateway, TURN config配信 |
| `127.0.0.1:8900` | morm-l1 node (data: `/tmp/morm-l1-admin`) | gateway/admin の back-end chain。dag_mode=False (single chain) |
| `192.168.2.122:3478` | coturn (homebrew) | TURN/STUN server, HMAC use-auth-secret |
| `192.168.2.122:11435` | llama.cpp Qwen3.6-35B (launchd) | 別プロジェクト (PoUW worker候補だが現在 unrelated) |

ポート 8787-8789 は Phase 6 edge nodes (現在停止)、8910-8912 は Phase 23/24a 検証用 (現在停止)。

---

## 5. ディレクトリ + ファイルマップ

```
~/Desktop/MORM/
├── MORM.md                              # 元の対話形式 spec (§1-5 が Whitepaper §4-9 に対応)
├── MORM UI_UX 視覚設計書.md             # UI/UX (Phase 24-UI で実装)
├── docs/
│   ├── README.md                        # docs root
│   ├── RESEARCH_ORIGINALITY.md          # 先行技術比較 (Whitepaper §3 の素材)
│   ├── IMPLEMENTATION-STATUS.md         # ←★ このファイル ★
│   └── ja/                              # 日本語版 (canonical)
│       ├── WHITEPAPER.md                # 編集対象
│       ├── TOKENOMICS.md                # §9 の詳細版
│       ├── MILESTONES.md                # §14 の詳細版
│       ├── AGENTS.md                    # MORM Agents (DAOガバナンス) 設計
│       ├── MANIFESTO.md                 # 哲学
│       ├── TERMS.md                     # 利用規約
│       ├── LP_CREATORS.md / LP_NODES.md / LP_SHOP.md   # 各セグメント向けコピー
│       ├── SNS_KIT.md                   # 配信用ソーシャル素材
│       └── WEBSITE_COPY.md              # 公式サイト用
│   └── en/                              # 英語版 (parity, 同じファイル名)
├── morm-core/                           # Phase 1, 2, 5, 8, 14, 15c, 16
│   ├── morm_core/
│   │   ├── encoder.py                   # §5.1 Cell encoder
│   │   ├── vhash.py                     # §7.1 V-Hash
│   │   ├── screening.py                 # §7.2 重複処理 + AI motion
│   │   ├── evidence.py                  # §8 PoPE encoder + cut_score
│   │   ├── manifest.py                  # content_id + root_hash
│   │   └── cli.py                       # 統合CLI (encode/screen/evidence)
│   └── .venv/                           # numpy + Pillow + ffmpeg-python
├── morm-chain/                          # Phase 4, 12, 13 (Solidity)
│   ├── src/
│   │   ├── MORMEscrow.sol               # §8.3 (legacy single-chain)
│   │   ├── MORMBridge.sol               # §9.5 (native MORM bridge)
│   │   ├── MORMBridgeERC20.sol          # §9.5 (USDC bridge)
│   │   ├── MORMBridgeMS.sol             # §13.4 (multi-sig relayer)
│   │   ├── MORMBridgeOptimistic.sol     # §13 (challenge window)
│   │   └── MockUSDC.sol                 # test
│   └── test/                            # 32 Forge tests, 100% PASS
├── morm-l1/                             # Phase 10-23a, 24a
│   ├── morm_l1/
│   │   ├── __init__.py                  # GENESIS_HASH, FINALITY_DEPTH=3
│   │   ├── crypto.py                    # ed25519 + m0r address
│   │   ├── tx.py                        # Transaction kinds (TRANSFER=1..REGISTER_PRODUCER=31)
│   │   ├── block.py                     # DAG-ready Block (parent_hashes: list)
│   │   ├── state.py                     # state machine (apply_block, slot_owner, list_producers, dag_mode)
│   │   ├── node.py                      # producer loop + gossip + mempool dedup
│   │   ├── rpc.py                       # /info /tx /account /blocks/at + getfqdn-fix
│   │   ├── shamir.py                    # 3-of-5 GF(2^8) split
│   │   └── cli.py                       # node/keygen/submit subcommands
│   ├── ops/
│   │   ├── 3NODE-TESTNET.md             # Phase 23/23a/24a 検証手順 + 結果
│   │   ├── DAG-DESIGN.md                # Phase 24b/c/d 設計
│   │   ├── QUIC-DESIGN.md               # Phase 25a/b/c 設計
│   │   ├── SECURITY-DESIGN.md           # Phase 26a-27i 脅威モデル + 対策
│   │   ├── TURN.md                      # Phase 22b 設計 + 検証
│   │   ├── TESTNET.md                   # Phase 20 公開手順
│   │   ├── MOBILE.md                    # Phase 21 PWA手順
│   │   ├── invite-node.sh               # Phase 19 自動onboarding
│   │   ├── install-launchd.sh           # macOS LaunchAgent
│   │   └── turn/                        # coturn config + install
│   └── .venv/                           # cryptography only
├── morm-player/                         # Phase 3, 6, 7, 10e, 15a, 16, 21, 22, 22b, 24-UI
│   ├── server.py                        # Phase 6 edge node
│   ├── passkey_server.py                # Phase 7 (Anvil)
│   ├── passkey_morm.py                  # Phase 10e + TURN + signal endpoints
│   └── static/
│       ├── index.html                   # Phase 6 edge UI
│       ├── auth-morm.html               # Phase 7 passkey UI
│       ├── shop.html / shop.js          # Phase 15a + 16 + 24-UI Action Slider
│       ├── admin.html / admin.js        # Phase 19b + 24-UI Swarm Map
│       ├── player.js                    # Phase 3 + 22 P2P fetch
│       ├── morm-p2p.js                  # Phase 22/22b WebRTC mesh
│       ├── morm-identity.js             # Phase 11b in-browser ed25519
│       ├── style.css                    # Phase 24-UI Cyber-Organic theme
│       └── sw.js                        # Phase 21 Service Worker
├── morm-aiservice/                      # Phase 14
│   └── aiservice.py
├── relayer.py                           # Phase 12c EVM↔L1 bridge relayer
├── scenario_*.py / scenario_e2e.sh      # 統合テスト群
└── bin/morm                             # Phase 24 統一CLI (`~/.local/bin/morm` でPATH通)
```

---

## 6. Whitepaper 各章 → 引用すべき実装/数値

### §4. システム・アーキテクチャ
- **§4.1 ネットワーク階層**: Phase 6 (edge nodes), Phase 22 (browser P2P mesh), Phase 22b (TURN)
- **§4.2 通信層**: HTTP gossip (Phase 10c, 現行)、QUIC (Phase 25 設計のみ — `QUIC-DESIGN.md` 参照)
- **§4.3 MORM Chain**: Phase 10a-e + 17 (slot rotation) + 18 (m0r) + 23 (3-node) + 23a (mempool dedup) + 24a (concurrent DAG sealing) + Phase 24b/c/d は設計のみ (`DAG-DESIGN.md` 参照)
  - 引用可能数値: max_width=3 観測、head=33/finalized=30、state_root全node一致 (Phase 23)、A=13/B=11/C=9 (Phase 23a改善後)
  - 引用すべき設計判断: ed25519 / BLAKE2b address / `block.timestamp` で決定論性 / 1% fee 不変

### §5. ストリーミング・プロトコル
- §5.1: Phase 1 (3秒 WebM cells)
- §5.2: Phase 3 (50/10サイクル — playerはセル切替時に次セル予約)
- §5.4: Phase 22 (browser↔browser cell中継 = 設計書§4のP2P Gateway具現化)

### §6. ID・認証システム
- §6.1: Phase 7 (WebAuthn passkey + 2-of-2 XOR split)
- §6.2: Phase 9 (server単独で署名不可検証済), Phase 11b (in-browser ed25519, Pythonと完全互換)

### §7. コンテンツ純度
- §7.1 V-Hash: Phase 2 (pHash + 音声FP)
- §7.2 重複処理: 4シナリオ PASS (反転/切り抜き/Generation ID/motion検知)
- §7.3 Generation ID: Phase 14 (6シナリオ PASS、ed25519署名 + treasury whitelist)

### §8. MORM Shop / 信頼プロトコル
- §8.1 PoPE: Phase 5 (block hash 透かし) + Phase 16 (実カメラ統合)
- §8.2 改ざん防止: Phase 15c cut_score (clean ACCEPT / spliced max_diff=0.218 REJECT)
- §8.3 スマート・エスクロー: Phase 4 (Solidity, 11/11 PASS), Phase 10d (MORM Chain native, 同11/11 再現)
- §8.4 Node-Lock & Slash: Phase 10/15 (`accounts.locked = 1` で全tx拒否)

### §9. トークン経済
- §9.1 MORM Token: Phase 18 (µMORM廃止 → MORM単一単位、SQLite 64bit signed内、wei 1:1)
- §9.2 1%手数料: 全 escrow / bridge / Solidity 共通 `FEE_BPS = 100/10000`
- §9.3 PoUW worker rewards: Phase 10b (worker_stats、weight=1+completed)
- §9.5 マルチ通貨ゲートウェイ: Phase 12 (native MORM bridge, e2e ✅) + Phase 13a (USDC, 4/4) + Phase 13b (multi-sig, 5/5) + Phase 13c (challenge window, 5/5)

### §11. エコシステム拡張
- §11.1 公式プロダクト: 現状 Player + Shop + Admin + AI Service が動作中。Producer招待 (Phase 19) で誰でもノード参加可能

### §13. ガバナンス
- §13.0 法人なし: 現状 treasury だけが特別扱い。Phase 13b multi-sig relayer は将来の DAO multi-sig への布石
- §13.4 緊急対応: Phase 13b multi-sig (M-of-N ECDSA、ascending署名者順チェック)

### §15. リスクと対策
- **必ず参照: `morm-l1/ops/SECURITY-DESIGN.md`** — 脅威モデル + 8レイヤー別攻撃ベクター + 既存防御 + 残ギャップ + Phase 26a-27i 対策案 + インシデント対応プロトコル
- 引用必須項目:
  - **Treasury 単一鍵が現状最大のリスク** → Phase 26a multi-sig 移行で解消
  - **Bridge replay 防止は `evm_lock_id` UNIQUE で実装済**
  - **Phishing 防御の核は WebAuthn origin pinning + Tx confirm dialog (Phase 27f)**
  - **「無限デプロイ」「自動SWAP」リスクの個別整理は SECURITY-DESIGN.md §2/§3**
  - **本番公開前 must-have セキュリティ項目は SECURITY-DESIGN.md §5 = ~36h**

---

## 7. Whitepaper で **絶対に書かないでほしい** 主張

### 7.1 まだ実装されていないもの

- ❌ "DAG concurrent sealing で state収束" → ✅ "Phase 24a で並列sealing検証済、state収束は Phase 24b で実装予定"
- ❌ "QUIC ベースの低レイテンシ gossip" → ✅ "現在は HTTP/1.1 gossip、QUIC化は Phase 25 で設計確定済"
- ❌ "BFT finality" → ✅ "Phase 17b は K-depth finality (honest producer 前提)。BFT は Phase 24c+ で拡張予定"
- ❌ "100ノード以上で実証" → ✅ "3-node testnet で state収束 + DAG並列性確認 (max_width=3)"
- ❌ "本番ネット稼働中" → ✅ "PoC実装 + ローカル/2-machine LAN 検証"

### 7.2 過大評価のリスクある言い回し

- ❌ "数千TPS" → 現状 BLOCK_INTERVAL=1s、Phase 24a でもまだ 3 producer × ~10 tx/block ≈ 30 tx/s
- ❌ "実用レベルの分散ストレージ" → Phase 6 edge mesh は 3-node localhost 検証のみ。地理分散テストは未
- ❌ "AIによる完全な真贋判定" → cut_score は **動体差分のスパイク検出のみ**。意味解析・生成検出は未実装
- ❌ "P2Pコマースで詐欺ゼロ" → PoPE は **物理証拠の改ざん検出**。配送ルート全体や偽造商品検出はカバー外

### 7.3 法的・規制ニュアンス

- ❌ "証券性なし" と断言 → 各国規制次第。Whitepaper では "MORM Token は決済 + ノード重み付けユーティリティトークン" 程度の記述に留める
- ❌ "完全匿名" → Walletless はパスキー紐付け、Generation ID は AI署名でトレース可能。"擬似匿名" 程度

---

## 8. 既知の制約・修正中のもの

| 項目 | 状態 | 影響 |
|---|---|---|
| Mac Mini APFS で SQLite "unable to open" (高負荷時) | 既知 | 物理3-machine + BLOCK_INTERVAL=0.1 で再現。`busy_timeout` PRAGMA 追加で解決見込 |
| Service Worker style.css cache pin | 既知 | 開発時は cache clear 必要、本番では版番号化要 |
| Phase 24a state divergence | 設計通り | 24b で frontier-relative state 実装で解消 |
| WebRTC iframe 制限 | 既知 | preview iframe では UDP 192.168.x 不可、実機2ブラウザで relay/relay 確認要 |

---

## 9. Whitepaper 執筆セッションで作業可能な改修 / 追加候補

(本ドキュメントを参照する Whitepaper セッションが、実装に手を入れずに進められるもの)

1. **§3 RESEARCH_ORIGINALITY.md** との内容整合 (重複削除 / 一本化)
2. **§14 ロードマップ** と `MILESTONES.md` の同期 — Phase 24/25/BFT を追記
3. **§4.3 アーキ図** を ASCII / Mermaid で追加 (現状テキスト中心)
4. **付録 — Phase別実装ファクトシート** をこのドキュメントから抜粋して入れる
5. **付録 — APIリファレンス**: `/info` `/tx` `/account/{addr}` `/blocks/at/{h}` `/bootstrap` `/api/signal/*` の各 endpoint をJSON schemaで列挙

API一覧 (実装済の RPC + Gateway endpoints):

| Endpoint | Method | サービス | 戻り |
|---|---|---|---|
| `/info` | GET | morm-l1 (8900) | producer/treasury/state_root/tips/head/finalized/producers/dag_mode/dag_max_width/dag_head_width/next_slot_owner |
| `/account/{addr}` | GET | morm-l1 | balance/nonce/stake/locked |
| `/blocks/at/{height}` | GET | morm-l1 | array of blocks (DAG: 1+) |
| `/tx` | POST | morm-l1 | tx submit + gossip |
| `/gossip/block` `/gossip/tx` | POST | morm-l1 | peer-to-peer 受信用 |
| `/bootstrap` | GET | morm-l1 | peer URLs + chain spec for new joiner |
| `/api/auth/list` | GET | gateway (8801) | passkey enrollment一覧 |
| `/api/dev/register` `/api/dev/share` | POST | gateway (dev mode) | 鍵分割 helper |
| `/api/relay/morm-tx` | POST | gateway | passkey署名txをL1へ relay |
| `/api/treasury/credit` `/api/treasury/finalize` | POST | gateway (with `--treasury-seed`) | demo helpers |
| `/api/evidence/upload` | POST | gateway | カメラ動画 → Phase 16 evidence encode |
| `/api/signal/announce` `/api/signal/peers/{cid}` `/api/signal/inbox/{pid}` `/api/signal/send` | POST/GET | gateway | Phase 22 WebRTC mailbox |
| `/api/signal/ice` | GET | gateway | Phase 22b ICE config (STUN + TURN ephemeral creds) |
| `/api/morm/info` | GET | gateway | L1 info forward |

---

## 10. 同期ルール

- **Whitepaper を更新したら**: §1 の「実装済」表が乖離しないか確認。新しい主張が追加されたらこのドキュメントの §3 数値か §6 マッピングに対応行を追加。
- **コードを更新したら**: 該当 Phase 行をこのドキュメントの §1 に追記、Whitepaper の対応章にも反映必要なら git diff で確認。
- **設計書 (`DAG-DESIGN.md` 等) を更新したら**: §2 の見積を更新。
- このファイルは MORM repo の `docs/IMPLEMENTATION-STATUS.md` に置かれ、Whitepaper セッションが起動時に毎回読み込む前提で書かれている。
