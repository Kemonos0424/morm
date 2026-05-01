# MORM セキュリティ設計 — Threat Model + Mitigations

> 設計書 §13 (ガバナンス) と §8 (信頼プロトコル) で扱われたセキュリティ要件を、
> **具体的な攻撃ベクター → 既存防御 → 残ギャップ → 提案** の順に整理。
> Whitepaper §15 (リスクと対策) の素材になる。
>
> ステータス: **Phase 26a 着地済 (2026-04-26) — 残りは設計のみ**。実装は 26b-26h で段階的に。
> Phase 26a の詳細は §5「実装優先度」+ §1.1「Treasury key compromise」+ §6.1「Treasury 鍵流出時」を参照。
> Last sync: 2026-04-25 (Phase 1-24a 完了時点)

---

## 0. 脅威モデル (Adversaries × 動機)

| Adversary | 動機 | 期待される能力 |
|---|---|---|
| **Script-kiddie** | 名声、悪戯 | 公開ツール (curl/Burp/Metamask) 操作、低リソース |
| **Profit-driven attacker** | 直接的な経済利得 | exploits 開発・実行、オンチェーン取引、bot 運用 |
| **Phisher** | 鍵盗難・なりすまし | ドメイン詐称、SSL証明書取得、ソーシャルエンジニアリング |
| **Compromised producer** | ネットワーク撹乱、検閲、自己利得 | 1ノード分の鍵・帯域、合法producerの権限 |
| **Coordinated producer cabal** | ネットワーク乗っ取り、treasury強奪 | ⅓〜½ producer の協調 |
| **Treasury key holder rogue** | 通貨無限増刷、bridge悪用 | treasury 単一鍵 (現状)、最大権限 |
| **Insider (運営寄与者)** | 仕様乱用、内部情報悪用 | コミット権、デプロイ権 |
| **State-level actor** | ネットワーク遮断、ID紐付け | DPI、BGP操作、CA強制発行 |

**現状最大のリスク**: **treasury 単一鍵**。BRIDGE_MINT / REGISTER_PRODUCER / REGISTER_AI_SERVICE が
すべて treasury 署名で通る → 鍵流出で実質ネットワーク全権奪取が可能。
**対策の本命**: Phase 13b multi-sig 構造を treasury 自体に適用 (M-of-N)。

---

## 1. レイヤー別 — 既存防御 + ギャップ

### 1.1 L1 Chain (morm-l1)

| 攻撃 | 既存防御 | ギャップ | 対策案 (Phase) |
|---|---|---|---|
| Tx replay | `nonce` 単調増加チェック (`state.py:_apply_tx`) | なし | — |
| 鍵不正使用 (forged signature) | ed25519 verify (`tx.py:Transaction.verify`) | なし | — |
| Double-spend | nonce + balance チェック | DAG-mode (24a) で sibling tx 競合は **lower-hash-wins** で merge 必要 (DAG-DESIGN.md §5) | 24b (canonical merge) |
| Sybil producer | treasury 署名の REGISTER_PRODUCER 必須 | treasury が compromise されると無限producer量産 → ネット支配 | **26a Treasury multi-sig** |
| Producer block spam (DoS) | なし — `produce_one()` は無制限 | `--dag-mode` で顕著、悪意producerが BLOCK_INTERVAL=ms オーダーで spam可 | **26b Per-producer rate limit** (= 24d) |
| Mempool flood | **Phase 26c 着地済** (`node.py:submit_tx` で global cap `--mempool-max-txs` 既定 5000 + per-sender quota `--mempool-max-per-sender` 既定 32 を enforce、`/info` で公開、`/tx` resp に `error` + `limit` を返却) | fee 機構自体は未導入 — fee floor は per-sender quota で代替。本来の経済的 disincentive は将来 fee tx 導入後 | (将来 fee tx) |
| Eclipse attack | gossip mesh、現状3ノードでは脆弱 | 攻撃者が producer の peer list を独占すると state divergence 注入可 | **26d Peer rotation + bootstrap安全性向上** |
| Long-range re-org | finality_depth=3 (Phase 17b) で過去ブロック不可逆 | 24c で common-ancestor finality に置換予定 | 24c |
| state_root 改ざん | apply_block 内で再計算+strict match (`state.py:184`) | dag-mode で skip-and-continue (24a) → 24b で frontier-relative state に置換 | 24b |
| genesis bootstrap rush | **Phase 26e 着地済** (`state.py:State.genesis_lockdown_active(height)` で `producers.empty AND height < lockdown_height` を判定、`apply_block` 先頭で treasury 以外の producer block を `26e genesis lockdown` で reject、`node.py:produce_one` も非 treasury 自己生成を skip。escape hatch: `height >= lockdown_height` または最初の REGISTER_PRODUCER で auto 解除、`/info: genesis_lockdown_height/active` で観測可能、`--genesis-lockdown-height 0` で disable) | (将来) treasury 鍵流出時の rotation 経路は 26a-rotation で対応予定 | (将来) |
| Treasury key compromise | **Phase 26a multi-sig 着地済** (M-of-N、`tx.py:REGISTER_TREASURY_SIGNERS+MULTISIG_TX`、`state.py:_tx_register_treasury_signers/_tx_multisig_tx`、`_TREASURY_ONLY_KINDS` ガード) | time-lock 未対応、rotation は now MULTISIG_TX 経由のみ (現状 `_TREASURY_ONLY_KINDS` に REGISTER_TREASURY_SIGNERS 未登録のため別 Phase 必要) | **26a-rotation** (multi-sig 経由で signer set 更新を可能に) |

### 1.2 EVM Bridge (morm-chain Solidity)

| 攻撃 | 既存防御 | ギャップ | 対策案 |
|---|---|---|---|
| Locked event replay (mint twice) | `bridge_mints` テーブル `evm_lock_id` UNIQUE (`state.py:473`) | なし | — |
| Burn-side replay (unlock twice) | Solidity `burnConsumed` mapping (Bridge.sol) | なし | — |
| Reentrancy | **Phase 26f 着地済** (Slither 全 Solidity contract scan で High=0/Medium=0 baseline 達成 — fix した実バグ: `MORMEscrow.createOrder` の CEI 違反 = treasury.call BEFORE orders[orderId] 書込み → CEI 順に並び替え。`MORMBridgeMS.unlock` の uninitialized-local + arbitrary-send-eth は false-positive (M-of-N 署名で gate 済) と判定し explicit zero-init + slither-disable comment + 監査ノート docstring 追記。Echidna fuzz 50,118 calls で `unlocked` 単調性 / `lockNonce` 単調性 / bridge balance solvency / threshold immutability の 4 不変条件 PASS、`forge test` 全 32 件 regression なし) | (将来) `MORMBridgeERC20`/`MORMBridgeOptimistic` の Echidna properties 拡張 | (将来) |
| Front-running relayer | single relayer (Phase 12c) | 単一信頼点 | **26g Multi-sig relayer (Phase 13b 既実装) を defaultに** |
| Bridge contract upgrade attack | 現状 immutable | 仕様変更時に hard fork 不可避 | (許容) |
| Challenge window bypass | Phase 13c Optimistic で 7-day window | 攻撃者が treasury (proposer) と結託すると window意味なし | **26g + 26h** Decentralized challenger network |
| Ethereum re-org > finality | (なし) | L1 の finality depth (12 blocks) を待ってから L1 mint すべき | **26h: relayer.py に min_confirmations=12 追加** |

### 1.3 Walletless ID + Passkey

| 攻撃 | 既存防御 | ギャップ | 対策案 |
|---|---|---|---|
| Server share theft | XOR 2-of-2 (Phase 9) — server単独で署名不可 | client share がIndexedDBにある → ブラウザ exploit 経由で同時盗難リスク | **26i Client share を Web Crypto API SubtleCrypto で hardware-isolated に** |
| Passkey replay | WebAuthn 仕様で counter + challenge nonce 管理 | passkey gateway で counter 検証要 (要audit) | **26j WebAuthn counter strict check** |
| Replay across origins | WebAuthn は rpId 厳格判定 (origin pinning) | rpId は `localhost` や `*.morm.dev` 設定次第 | **26k Production rpId をDNS名でpin、wildcard禁止** |
| Phishing via lookalike domain (`m0rm.app` vs `morm.app`) | パスキーは origin bound (本物以外で signature 出ない) | しかしユーザは別 origin で別 passkey を 새로 作ってしまう | **26l Trust badge + Sigstore風 verifyフロー (PWA installのみ trusted)** |
| Server share rotation 攻撃 | (なし) | 古い server share が漏れた場合の再生成手順なし | **26m server_share rotation tx** |

### 1.4 MORM Shop / PoPE

| 攻撃 | 既存防御 | ギャップ | 対策案 |
|---|---|---|---|
| 偽動画 (古い動画使い回し) | block_hash watermark (`evidence.py:write_evidence_meta`) — 直近ブロックのhash不可avoidance | client 側 system clock 改ざん時? watermark は server が直近ブロック取得して焼き込むので OK | — |
| 動画splice (途中差し替え) | cut_score (Phase 15c) — フレーム差分のスパイク検出 | **検出は確率的**、巧妙な splice は escape する | **26n: 機械学習 deepfake detector追加 (将来)** |
| 同一物の二重出品 | content_id (manifest hash) の `UNIQUE` index | しかし content_id を recompute するだけで別ID化可能 — 真贋は V-Hash 重複検知に頼る | (Phase 7 既存で対応) |
| Buyer 受領後の返金詐欺 | `submitProof(opening)` 後 finalize で fund 解放 | finalize が treasury 任せなので treasury rogue 時に保留可 | **26o Time-lock auto-finalize after dispute_window** |
| Seller 詐欺 (item違い) | (技術layerでは不可避) | ❌ 技術で解決不能 | **26p 保険 / DAO仲裁 (法的layer)** |

### 1.5 P2P / WebRTC mesh

| 攻撃 | 既存防御 | ギャップ | 対策案 |
|---|---|---|---|
| Cell content poisoning | **Phase 26q 着地済** (`morm-p2p.js: _vhashFromSegId + _verifyBlobAgainstSegId` で受信した `.m4s` の `sha256[:8 bytes hex]` を filename に焼き込まれた vhash16 (`seg_NNNNN.<vhash16>.m4s`) と照合、不一致なら `stat.p2pRejects++` + cache に書かない + `rememberSegment` 呼ばない + 次の candidate を試行)。`init.mp4` は filename に hash が無いため P2P から除外し origin only (~1KB なので egress 影響 negligible) | (将来) manifest.json の `init_hashes` を取得して init.mp4 も P2P 経由で検証可能化 | (将来) |
| TURN credential abuse | **Phase 26r 着地済** (`passkey_morm.py:_signal_rate_guard` で `/api/signal/*` 全 path に per-IP token-bucket rate limit 適用、デフォルト 15 RPS 持続 / 60 burst、超過は 429 + Retry-After) — `/api/signal/ice` を含む全 signaling endpoint に同一 limit | (将来) `/ice` 専用にもっと低い per-IP cap (TURN cred 生成は HMAC-SHA1 1回なのでコスト微小、現状は per-IP 共通 limit で十分) | (将来 fine-tune) |
| Signaling DoS | **Phase 26s 着地済** (per-peer_id mailbox cap `--signal-mailbox-max` 既定 256: oldest を drop して新着の offer/answer/ICE を優先、global announced-peers cap `--signal-peers-max` 既定 10000: TTL 切れを stale 削除→足りなければ LRU で last_seen 最小を evict + 対応 inbox も削除、`/api/signal/announce` 経路で enforce) | (将来) per-content_id cap で同一 content への spam を更に絞る | (将来 fine-tune) |
| ICE info leak | (peer reflexive addr 公開、これは意図通り) | — | — |
| TURN relay 帯域吸い尽くし | (なし) | 攻撃者が大量 file 中継させて自分のWAN食い潰す | **26t TURN bandwidth quota per cred (coturn `max-bps`)** |

### 1.6 Gateway / RPC

| 攻撃 | 既存防御 | ギャップ | 対策案 |
|---|---|---|---|
| ~~CSRF on `/api/relay/morm-tx`~~ | **Phase 26u 着地** (`passkey_morm.py:_check_csrf_or_reject`): `--allowed-origins` 設定時、全 POST の `Origin` header をチェック、不一致なら 403 + JSON explanation。デフォルト (legacy/dev) は無効化 | mainnet では必ず `--allowed-origins` を設定する運用ルール | (運用ガイド `SECURITY-COMM.md` で明記) |
| ~~Open CORS (`Access-Control-Allow-Origin: *`)~~ | **Phase 26v 着地** (`passkey_morm.py:_cors / _origin_matched`): `--allowed-origins` 設定時は matched origin のみ echo + `Vary: Origin`、不一致なら ACAO header 自体送らない (browser CORS-block) | 同上 (legacy default = `*`) | 同上 |
| ~~Server share leak via `/api/dev/share`~~ | **Phase 26w 着地** (`passkey_morm.py:main`): `MORM_PRODUCTION=1` 環境変数 set で `--dev-mode` を fatal exit、production marker を startup log に表示、ランタイムも `httpd.dev_mode = False` を force | runtime override されないことを deployer 側で確認 | (運用ガイド) |
| ~~`/api/treasury/*` 悪用 (`ps` 経由 seed leak)~~ | **Phase 26x 着地** (`passkey_morm.py:main`): `--treasury-key-file` (mode 0o600 必須、64-hex content 必須、`--treasury-seed` と mutex) を新設。`ps` には path しか出ない | mode を 600 に保つ運用ルール | (運用ガイド) |

### 1.7 Browser / PWA

| 攻撃 | 既存防御 | ギャップ | 対策案 |
|---|---|---|---|
| Service Worker hijack | **Phase 26y 着地済** (`sw.js: VERSION='morm-sw-v2'`、`SHELL_MAX_AGE_MS=24h` を `cacheFirst` で `Date` header 経由 enforce、`_recheckVersionAndMaybePurge()` で `/sw-version` を fetch して META cache に保存した値と比較→不一致なら SHELL+CELLS 全 purge、`activate` 時 + page-driven `postMessage({type:'morm-sw-recheck'})` 両方でトリガー、gateway 側 `_shell_bundle_version()` で sha256(sw.js + static/**/*) を返却) | 旧 SW 仕様で `activate` は SW スクリプト変更時のみ発火するため、page-driven recheck を必須に | (運用) |
| Stored XSS via user content | コンテンツは video binary のみ — innerHTML insertion なし | 将来 comments/profile 追加時に注意 | **26z Strict CSP header (`script-src 'self'`)** |
| MITM via fake SSL cert | TLS依存 (本番) | 国家レベル攻撃者が CA に強制発行可 | **27a Cert pinning in PWA manifest (要 Web App Manifest 拡張 wait)** |
| `localhost` テスト用設定の漏出 | `--host 127.0.0.1` が default | デバッグ時 `--host 0.0.0.0` でうっかり外部公開 | **27b 起動時に `0.0.0.0` 検出で警告 + fail-safe (firewall block 確認)** |

### 1.8 ユーザレベル: フィッシング・SE

| 攻撃 | 既存防御 | ギャップ | 対策案 |
|---|---|---|---|
| Lookalike domain (`m0rm.app`) | passkey origin-bound (本物以外で署名出ない) | しかしユーザは "登録ボタン" 押して別 passkey 作ってしまう | **27c Browser PWA install プロンプトで "MORM公式以外でinstall禁止" 文言 + DNSSEC + .morm TLD 申請 (長期)** |
| 偽アプリ (App Store/Play) | (App Store/Play審査) | サードパーティ store は通る | **27d 公式 GitHub releases に SHA256 + GPG署名公開** |
| Fake support (Discord/X) で seed phrase 要求 | (なし — passkey なので seed が無い → 詐欺成立しない) | しかし server share 提供を求められる | **27e UI 内 "MORM 運営は server share を要求しません" 永続表示** |
| Auto-SWAP drainer (悪意あるサイトで passkey署名後に自動SWAP) | passkey 署名は明示的なユーザ操作要 (Phase 7) | 1tx 署名で複数 op を実行する batch-tx を仕込まれると詐取可 | **27f Tx 署名時の human-readable summary (`tx kind=TRANSFER amount=100 to=m0r...` を確認画面で表示) + multi-op tx 拒否ポリシー** |

---

## 2. 「無限デプロイ」リスクの個別整理

ユーザ言及の「無限デプロイ」は次の3つに分解される:

### 2.1 Solidity contract 無限デプロイ
- **既存**: bridge contracts は immutable に deploy 済 (Phase 12-13)、再 deploy は別アドレス
- **リスク**: 攻撃者が gas を支払えば任意の悪意 contract を deploy 可 (これは Ethereum の特性、防げない)
- **対策**: gateway / shop UI が **whitelist された contract addr** とのみインタラクト。`MORMBridge.sol` の deploy 後 addr を `bin/morm gateway` の env に固定し、それ以外を拒否

### 2.2 Producer 無限デプロイ
- **既存**: REGISTER_PRODUCER は treasury 署名必須 (`state.py:304`)
- **リスク**: treasury 鍵流出で無限producer 立ち上げ放題 → ネット過半数取得 → 任意 finality
- **対策**: **26a Treasury multi-sig** + **Phase 24d rate limit (24h あたり N producer まで)** を treasury 上にも適用

### 2.3 Content registration spam
- **既存**: `register-content` は誰でも tx 1本で可能 (Phase 17 fee=1%)
- **リスク**: 1µMORM の手数料で無限の偽 content_id をchain に書き込み、state DB肥大化
- **対策**: **26C content registration 最低deposit (返金可)** + **GC: registration から 30日間視聴ゼロなら state から削除 (Phase 28 で cleanup tx)**

---

## 3. 「自動 SWAP」リスクの個別整理

ユーザ言及の「自動 SWAP」= 攻撃者が仕込んだ trigger でユーザの意図せぬ swap が走るシナリオ:

### 3.1 シナリオ
1. ユーザがフィッシングサイトで passkey を承認 (見た目は単純な login)
2. サイトが裏で `/api/relay/morm-tx` を叩いて TRANSFER tx を送る
3. ユーザの残高が攻撃者アドレスへ移動

### 3.2 既存防御
- WebAuthn の origin pinning — 偽ドメインでは passkey が反応しない
- `/api/relay/morm-tx` は CORS で `*` 開放されているが **passkey 署名済の tx しか受け付けない** (関連性なし)

### 3.3 残ギャップ
- ユーザが本物 origin で passkey を出したあと、JS が裏で勝手に追加 tx を組み立てる可能性 (XSS or 悪意ある SW)
- Tx 内容を **明示的に確認するUIなし** で送信できてしまう

### 3.4 対策案
| Phase | 内容 |
|---|---|
| **27f Tx confirm dialog** | passkey 署名前に **必ず** "to: m0r... / amount: X / kind: TRANSFER" モーダル表示 + 明示クリック必須 |
| ~~**27g Per-domain spending cap**~~ | ✅ **landed 2026-04-30** (`morm-player/static/morm-policy.js: getPolicy/decideTx/recordSpend/getSpentLast24h` で per-app rolling 24h cap、`txSpendAmount(kind, payload)` が TRANSFER/BRIDGE_BURN/CREATE_ORDER の sender 流出額を抽出、`signTxWithConfirm` が `decideTx().requireExtra` で `showExtraCeremonyDialog` (赤色 + ack-checkbox 必須) に切替、`recordSpend` は 24h sliding window で auto-prune。Default cap: shop=1M MORM, wallet=100k MORM, それ以外=0 (no spend)) |
| ~~**27h Tx kind whitelist per origin**~~ | ✅ **landed 2026-04-30** (`morm-policy.js: DEFAULT_POLICIES` で page-key (= `location.pathname` 第一セグメント) ごとに `allowedKinds` を seed: shop={CREATE_ORDER, SUBMIT_PROOF, FINALIZE} / admin={4, 20, 31, 32, 33} / player-hls={VIEW_REWARD} / upload={REGISTER_CONTENT} / auth-morm={REGISTER_CONTENT, REGISTER_AI_SERVICE} / wallet={TRANSFER}、`decideTx` が `kind ∉ allowedKinds` で `ok:false, reason:"kind-not-allowed"` を返し `signTxWithConfirm` は `showKindBlockedDialog` (赤色 + 許可済み kind リスト表示) で reject、ユーザは /wallet からのみ broaden 可) |
| ~~**27i 1-tap revocation**~~ | ✅ **landed 2026-04-30** (`/wallet` ページに 5列 policy table (App / Allowed kinds / Spent/Cap / progress bar / Edit) + 大型 red "🚨 Revoke all (1-tap)" button、`morm-policy.js: revokeAll()` で `morm-policy-v1` + `morm-spend-v1` の両 localStorage key を removeItem、次の tx は default policy で再 prompt。confirm modal でユーザが意図確認、screenshot 取得済) |

---

## 4. フィッシング対策の重点項目

### 4.1 多層防御 (priority順)

1. **WebAuthn origin pinning (既存・最強)** — 偽 origin では passkey が出ない物理的保証
2. **PWA install + 公式 install URL の強調** — "アプリでアクセス" を運用上の defaultに
3. **Tx confirm dialog (Phase 27f)** — 署名内容を必ず human readable で表示
4. **Lookalike domain monitoring** — 月次で `morm.app`, `m0rm.app`, `morrn.app` 等の登録監視 (Spamhaus風)
5. **DNSSEC + CAA records** — 公式ドメインの cert 不正発行検知
6. **公式チャンネルでの注意喚起テンプレ** (`SECURITY-COMM.md` で運用)

### 4.2 ユーザ教育素材

`docs/ja/SECURITY_USER_GUIDE.md` を作って Whitepaper §15 (リスクと対策) からリンクさせる。
内容案:
- "MORM運営は seed/server_share/パスワードを聞きません"
- "Tx を送る前に必ず内容を確認"
- "PWA install は必ず公式 URL から"
- "Discord/X DM の運営なりすましに注意"

---

## 5. 実装優先度 (提案)

### 🔴 即着手すべき (本番公開前 must-have)

| Phase | 項目 | 工数 |
|---|---|---|
| ~~26a~~ | ~~Treasury multi-sig (M-of-N、treasuryからの全 tx に適用)~~ | ✅ **landed 2026-04-26** (~16h 実工数 ~12h、verified bootstrap + gate + 2-of-3 accept + 1-of-3/wrong-nonce reject) |
| ~~26b~~ | ~~Per-producer block rate limit (24d 兼)~~ | ✅ **landed 2026-04-26** (= Phase 24d, R blocks/10s where R = `1 + worker_stats.completed`、3-node DAG verified `recent=0` window release) |
| ~~26u/26v~~ | ~~CSRF token + production CORS strict~~ | ✅ **landed 2026-04-26** (`passkey_morm.py:--allowed-origins`、Origin allowlist + strict CORS + Vary header、curl tests pass) |
| ~~26w~~ | ~~dev-mode endpoint 本番ビルド除外~~ | ✅ **landed 2026-04-26** (`MORM_PRODUCTION=1` env で `--dev-mode` fatal、 `dev_mode=False` を force off) |
| ~~26x~~ | ~~treasury seed → keyfile (umask 0600)~~ | ✅ **landed 2026-04-26** (`--treasury-key-file` 新設、mode 0600 + 64-hex 必須、`--treasury-seed` と mutex) |
| ~~27f~~ | ~~Tx confirm dialog (passkey 署名前)~~ | ✅ **landed 2026-04-26** (`morm-identity.js: showTxConfirmDialog + signTxWithConfirm`、shop.js + auth-morm.js wired、kind 別 field rendering、VIEW_REWARD は exempt、Cancel/Confirm 両パス preview 検証済) |

合計 **~36h**。本番公開 (mainnet candidate) の最低条件。

**🎉 すべて 2026-04-26 着地済**: 26a (Multi-sig) + 26b (rate limit, = 24d) + 26u/v (CSRF/CORS) + 26w (prod guard) + 26x (keyfile) + 27f (confirm dialog)。SECURITY-DESIGN must-have 完全達成、mainnet candidate の transport/auth/UI/key-handling 層は出揃った。残るのは順次対応 (next §🟡) と 27g/h/i (per-domain spending cap, kind whitelist, 1-tap revocation)。

### 🟡 順次対応

| Phase | 項目 | 工数 |
|---|---|---|
| ~~26c~~ | ~~Mempool size cap + fee floor~~ | ✅ **landed 2026-04-30** (`node.py: MEMPOOL_MAX_TXS_DEFAULT=5000 / MEMPOOL_MAX_PER_SENDER_DEFAULT=32`、`Node.submit_tx` で BEFORE accepting global+per-sender cap enforce、`_sender_count` map を `submit_tx`/`drain_mempool`/`_reinsert_mempool`/`import_block` で同期、`cli.py: --mempool-max-txs/--mempool-max-per-sender`、`rpc.py: /info` に両 cap 露出 + `/tx` resp に `error: "mempool full" \| "per-sender quota exceeded"` + `limit`)。**E2E 検証**: cap 8/4 で起動 → sender A の 5th tx を `per-sender quota exceeded` で reject、sender B が global cap まで埋めた後 5th を `mempool full` で reject。fee 機構自体は未導入のため、本来の "fee floor" は per-sender quota で代替している (将来 fee tx で経済的 disincentive を追加可能) |
| ~~26e~~ | ~~Genesis lockdown window~~ | ✅ **landed 2026-04-30** (`state.py: GENESIS_LOCKDOWN_HEIGHT_DEFAULT=100`、`State.genesis_lockdown_active(height)` ヘルパ、`apply_block` 先頭で `crypto.address(block.header.producer) != self.treasury` なら `26e genesis lockdown` raise、`node.py:produce_one` で 非treasury self-production を skip、`cli.py: --genesis-lockdown-height` (0 で disable)、`rpc.py:/info` に `genesis_lockdown_height/active` 露出。**3 シナリオ E2E 検証**: (a) 非treasury producer + lockdown=5 → tx submit 後 4s でも head=0 (sealed されず)、(b) 同 data dir で treasury 鍵に切替 → tx 再 submit → `[producer] sealed #1` で head=1、(c) treasury が REGISTER_PRODUCER 投稿 → block sealed → `genesis_lockdown_active=False` に auto 切替、producers=['rogue']、next_slot_owner が新 producer に切替) |
| ~~26f~~ | ~~Solidity Slither + Echidna audit pass~~ | ✅ **landed 2026-04-30** (Slither 0.11.5 を pip3 install + Echidna 2.3.2 を brew install。`slither morm-chain/` 初回 run で 28 findings = High×2 + Medium×2 + Low×15 + Informational×9 → triage 後 fix した実バグ: (i) **`MORMEscrow.createOrder` reentrancy-eth** = CEI 違反 (treasury.call が orders[orderId] 書込み前) → CEI 順に並び替え + 詳細コメント、(ii) **`MORMBridgeMS.unlock` arbitrary-send-eth** は M-of-N 署名 gate 済の false-positive と判定 → docstring に audit ノート + explicit zero-init (uninitialized-local 解消) + `slither-disable-next-line arbitrary-send-eth` 単行抑制。再 slither run で **High=0/Medium=0** 達成 (Low 15 は reentrancy-events 9 + low-level-calls 6 = どちらも `recipient.call{value:}` 必須の bridge/escrow 設計、timestamp 4 + reentrancy-benign 2 + その他 3 は事前承知の design choice、Informational 9 は noise)。**Echidna property test** 新規 `morm-chain/test/echidna/EchidnaBridgeMS.sol` + `echidna.yaml` (testLimit=50000, seqLen=50, 4 workers) — 4 不変条件 (`echidna_unlocked_monotonic` / `echidna_lockNonce_monotonic` / `echidna_bridge_balance_solvent` / `echidna_threshold_correct`) を 50,118 fuzz calls で PASS、coverage 2274 instr。`forge test` 全 5 suite × 32 tests 全 PASS で regression なし) |
| ~~26q~~ | ~~Cell SHA256 verify in p2p~~ | ✅ **landed 2026-04-30** (`morm-p2p.js: _vhashFromSegId(seg_id)` + `_verifyBlobAgainstSegId(blob, seg_id)` (Web Crypto SubtleCrypto SHA-256 → first 8 bytes hex)、`p2pTryFetchSegment` 内で受信 blob を verify、不一致は `stat.p2pRejects++` + 次の candidate へ。`.mp4` init は P2P から除外 (filename に vhash 無いため origin only)、`player-hls.html` に `P2P rejects` tile + `player-hls.js: refreshP2PHud` で表示。**検証**: 749017B の本物 `.m4s` を origin から fetch → `sha256[:8B]=bbf448059f876670` = filename vhash16 一致確認、1B 反転で `c89a9e6e8a6b56c2` 不一致確認 (verify primitive が encoder side と完全一致) |
| ~~26r/26s~~ | ~~Signaling rate limit + mailbox cap~~ | ✅ **landed 2026-04-30** (`passkey_morm.py: PasskeyMormServer.sig_rate_take(ip)` token-bucket per-IP (`signal_rate_per_ip / signal_burst_per_ip`), `_signal_rate_guard(path)` を `do_GET / do_POST` 先頭で `/api/signal/*` のみ適用→429+`Retry-After`、`sig_send` の mailbox cap (oldest drop)、`sig_announce` の peers cap (TTL prune→LRU last_seen evict + inbox 同期削除)、`cli.py: --signal-rate-per-ip/--signal-burst-per-ip/--signal-mailbox-max/--signal-peers-max` + 起動 banner に `signal_caps=rps:N/burst:M/mailbox:K/peers:L`)。**E2E 検証** (`burst=5 rps=2 mailbox=3 peers=4`): (a) 7連続 announce → 1-5 OK / 6-7 `429 signaling rate limit`、3s 後 token 補充で OK 復帰、(b) cap=3 mailbox に 4 send → inbox poll で 3 messages (msg-0 dropped, msg-1/2/3 残存)、(c) cap=4 peers に 6 announce → `bb0002..bb0005` のみ残り、`bb0000/bb0001` LRU evicted |
| 26t | TURN bandwidth quota | 2h |
| ~~26y~~ | ~~SW max-age + version check~~ | ✅ **landed 2026-04-30** (`passkey_morm.py: _shell_bundle_version()` (sha256(sw.js + static/**/*)、process-cached) + `GET /sw-version`、`sw.js: VERSION='morm-sw-v2'` (force fresh install)、`_recheckVersionAndMaybePurge()` ヘルパで META 比較→ SHELL/CELLS 一括 purge、`activate` + `message {type:'morm-sw-recheck'}` 両 trigger、`cacheFirst` の `_cachedTooOld()` で 24h max-age 強制、network 失敗時は stale でも返却して offline path を維持。**E2E 検証**: META に `STALE_DEADBEEF` を inject → postMessage → SW が `mismatch:true` 返却 → `caches.keys()` が `[morm-meta-v1]` のみに、META が live version `3d009ac60b986a16` に更新確認) |
| 27c | DNSSEC + .morm TLD研究 | 16h+ |

### 🟢 長期 / 研究色

| Phase | 項目 |
|---|---|
| 26n | Deepfake detector (PoPE強化) |
| 26p | DAO仲裁 (Shop trust prot.の社会layer) |
| 27a | Cert pinning in PWA |
| 27c | .morm TLD 申請 (multi-year) |
| 27d | GPG-signed releases |

---

## 6. インシデント対応プロトコル (案)

### 6.1 Treasury 鍵流出時
1. **検知**: monitoring (`monitor.py`) が treasury 異常tx (per-day cap 超え) を 5min 以内に検知
2. **遮断**: treasury multi-sig (Phase 26a 後) で `treasury_freeze` tx を緊急発行 — 全 treasury-only tx を一時停止
3. **rotation**: 新 treasury 鍵を multi-sig 投票で選出、旧 treasury → 新 treasury への migration tx
4. **post-mortem**: Discord 公式 + GitHub Security Advisory

### 6.2 Producer cabal攻撃時
1. **検知**: head_height advance が止まる / state_root divergence が長期化
2. **対応**: コミュニティ producer が `slash_producer` tx (Phase 26 で追加要) を投じ、悪意 producer の weight=0 化
3. **回復**: honest producer のみで chain を継続、再 register-producer 投票

### 6.3 Bridge 異常mint
1. **検知**: Solidity `Locked` event と L1 `BRIDGE_MINT` の数量不一致を relayer 自体が検出
2. **対応**: `relayer.py` が異常検知時に処理停止 → manual 介入待ち
3. **強化**: Phase 13c Optimistic challenge window + Phase 26h L1 min_confirmations=12

---

## 7. 監査 / 透明性

### 7.1 公開推奨
- L1 source: 既に open (PoC段階)、本番 freeze 後 git tag + SHA256 公開
- Solidity: Slither/Echidna レポートを `morm-chain/audit/` に置く
- Bug bounty: Immunefi / HackenProof で seed funds + bounty pool 設置

### 7.2 ログ・観測性
- `monitor.py` (新規追加要) が `/info` を 30s ごとに pull、treasury balance / producer count / dag_max_width を Prometheus exposition format で公開
- 異常パタン (treasury balance 急減、producer 急増、state divergence 長期化) で Discord webhook 通知

---

## 8. Whitepaper §15 (リスクと対策) への抜粋ガイド

WHITEPAPER.md の §15 で書くべき内容 (このドキュメントの抜粋):

| WP行 | 出典 |
|---|---|
| "Treasury single key risk → Phase 26a multi-sig 移行" | §1.1 + §5 |
| "Bridge replay 防止は `evm_lock_id` UNIQUE で実装済" | §1.2 |
| "Phishing 防御の核は WebAuthn origin pinning" | §4.1 |
| "Producer cabal 対策は Phase 24c common-ancestor finality + slash tx (Phase 26)" | §1.1 + §6.2 |
| "User-facing security guide → `SECURITY_USER_GUIDE.md`" | §4.2 |

---

## 9. 同期ルール

- セキュリティ修正実装時: 該当 Phase 行に `✅ 実装済` を付与、`IMPLEMENTATION-STATUS.md §1` にも追記
- 新たな攻撃ベクター発見時: §1 の対応 layer に行追加
- インシデント発生時: §6 のプロトコルを実行し、post-mortem を `morm-l1/ops/INCIDENTS/yyyy-mm-dd.md` に記録
