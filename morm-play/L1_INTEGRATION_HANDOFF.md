# MORM Play × L1 統合ハンドオフ（2026-08-10）

このドキュメントは **MORM Play に L1 ネイティブ機能を組み込む新セッション** が最初に読む前提資料。
「MORM L1 のチェーン構造を理解した上で Play の仕組みに入れていく」ための地図。

- 対象コード: `~/Desktop/MORM/morm-play/`（本番 https://play.morm.one）
- L1 コード: `~/Desktop/MORM/morm-l1/morm_l1/`
- 関連メモリ: `project_morm_play_discovery` / `reference_morm_usd_market`（wMORM/USD市場）/ `project_morm_walletless_accounts`（morm.one パスキーウォレット）/ `project_morm_poc`

---

## 0. 一言まとめ
MORM Play は **既に実 L1 で決済している**（treasury→クリエイターの kind:6 送金＋着金確認）。報酬の**発生**はSQLiteカウンタ、**支払い**は本物のチェーン。ここに、L1 が持つ**ネイティブ・ソーシャル/マーケットprimitive**（VIEW_REWARD / TRANSFER / ORDER / JOB / REGISTER_CONTENT+AI provenance）と、**wMORM/USD 実価格**・**パスキーウォレット**・**wMORMブリッジ**を接続して機能を深める。

---

## 1. L1 チェーン構造（要点・正典 = `morm-l1/morm_l1/`）

### アドレス/署名
- アドレス = `m0r` + base32(BLAKE2b-32(ed25519 pubkey)[-20:]).lower()（35字）。`crypto.py:55`。**片方向**（addr→pubkey不可）。
- tx.sender = **生の32バイトEd25519公開鍵**（アドレスではない）。
- 署名前像（`tx.py:66`）= `json.dumps({"kind":int,"sender":pubhex,"nonce":int,"payload":_canonicalize(payload)}, sort_keys=True, separators=(",",":"))` を Ed25519署名。`_canonicalize`=辞書キー再帰ソート/bytes→hex。tx.hash=`sha256(signing_bytes+signature)`（**署名後に確定**、mempool/dedup/burnId キー）。
- **金額は整数のみ（小数なし）**。SQLite INTEGER（最大~9.2e18）。

### TxKind 全16種（`tx.py:25`）
| Kind | 値 | 用途 | 権限 |
|---|---|---|---|
| REGISTER_CONTENT | 1 | コンテンツ記録公開（creator=sender, generation_id一意, AI署名で来歴） | 誰でも |
| CREATE_ORDER | 2 | エスクロー購入（value, fee1%→treasury, 残→escrow） | 誰でも |
| SUBMIT_PROOF | 3 | 梱包/開封 proof（packing=seller, opening=buyer） | 当事者 |
| FINALIZE | 4 | 注文確定/返金+slash | **treasury限定** |
| STAKE | 5 | balance→stake | 誰でも |
| **TRANSFER** | 6 | 残高移動（=送金・チップの基礎） | 誰でも |
| **VIEW_REWARD** | 7 | 視聴報酬（treasuryが1単位/ユニーク視聴・dedup） | 誰でも(treasury原資) |
| POST_JOB | 10 | 賞金付きジョブをcontent_idに紐付けロック | 誰でも |
| CLAIM_JOB | 11 | ワーカーが請負（winner-take-all） | 誰でも |
| SUBMIT_WORK_PROOF | 12 | output_root提出→報酬解放+worker評価加算 | claimer |
| BRIDGE_MINT | 20 | EVMロック観測→L1でmint | treasury限定 |
| BRIDGE_BURN | 21 | 残高burn→EVM放出シグナル（**forward の基礎**） | 誰でも |
| REGISTER_AI_SERVICE | 30 | Generation-ID発行者をwhitelist（AI来歴） | treasury限定 |
| REGISTER_PRODUCER | 31 | ブロック生成者追加 | treasury限定 |
| REGISTER_TREASURY_SIGNERS | 32 | treasury M-of-N多重署名ブートストラップ | 初回のみ |
| MULTISIG_TX | 33 | treasury限定txを≥M署名でラップ | 署名者 |

payload形状の詳細は `tx.py:107-294` のファクトリ参照（各`*(sender,nonce,*,...)`）。

### アカウント/状態（`state.py`）
- `get_account(addr)`（`state.py:1697`）= `{address,nonce,balance,stake,locked,tokens{sym:bal}}`。未使用アドレスは全ゼロ。
- native MORM=`accounts.balance`、ERC-20ミラー（USDC等）=`account_tokens`。
- dispatch（`_apply_tx` `state.py:1029`）: `tx.verify()`必須／locked口座拒否／**nonce==accounts.nonce厳格**／treasury限定kindは多重署名ゲート／適用後nonce++。
- テーブル: contents / ai_services / orders / accounts / bridge_mints / bridge_burns / account_tokens / views / jobs / worker_stats / producers / blocks / treasury_signers / treasury_config（`state.py:33`）。エスクロー=合成アドレス`ESCROW_ACCOUNT`。fee=1%（`FEE_BPS=100`）。VIEW_REWARD=1単位。

### コンセンサス/生成（`node.py`/`block.py`/`state.py`）
- DAG対応だが**既定は線形単一チェーン**。ブロック=height/parents[]/producer(pub)/timestamp/state_root/tx_root＋producer署名。
- 生成ループ `produce_one`（既定1.0s）。producerはslot_owner(height)=PoUW重み(1+worker完了数)で選出。**producer未登録なら全ノード生成可**（単一ノード起動）。
- **genesis lockdown**: producer0件かつheight<100の間はtreasury署名ブロックのみ受理。
- **初期供給=treasuryに1e18 MORM（genesisのみ）**。ブロック報酬インフレは**無い**。MORMはtreasuryから流通。
- finality: 線形=head-3。今は実質**単一ノード**（新チェーン）で動作。

### RPC（`rpc.py`・既定 127.0.0.1:8900・CORS*）
- 読み取り: `/info` `/account/{addr}` `/content/{cid}` `/order/{oid}` `/job/{jid}` `/jobs?status=` `/worker/{addr}` `/ai-services` `/views/{content_id}` `/bridge/burns?only_pending=1` `/blocks/latest?n=` `/block/{hash}` `/tip`。※content/order/job/viewsは`0x`hex ID正規表現のみ。
- 書き込み: `POST /tx`（署名tx投入・`{ok,tx_hash,mempool_size}`）／`/bridge/burn-confirmed`（relayer）／`/credit`（単一ノード専用）。
- 公開経路: **api.morm.one**（Vercel morm-dashboard）が唯一のブラウザ到達面。L1は非公開（`MORM_L1_RPC_URL`でdashboardのみ到達、`l1.morm.one`=CFトンネル→Mac Mini:8900）。CORS許可=morm.one系のみ。

### ソーシャル/マーケットprimitive（Playに効く）
- **コンテンツ来歴**: REGISTER_CONTENT（creator所有・generation_id一意・AI service署名で「H3生成」を検証可能に）。
- **チップ/送金**: TRANSFER（専用tip/liketxは無い）。
- **視聴→報酬**: VIEW_REWARD＋`views`テーブル＋`/views/{cid}`（ネイティブ視聴カウンタ／watch-to-earn）。
- **有料コンテンツ**: ORDER三部作（エスクロー＋commit-reveal＋treasury裁定・返金/slash）。
- **クリエイター/ワーカー賞金**: JOB三部作（transcode/tag/moderate等をcontent_idに賞金付け・winner-take-all・worker評価が生成重みに反映）。
- **来歴発行者**: REGISTER_AI_SERVICE＋`/ai-services`。
- **ネイティブに無く off-chain で埋める必要**: like/follow/comment、コンテンツ一覧/検索/フィード、username/profile（per-idルックアップのみ）。

---

## 2. MORM Play 現状（正典 = `morm-play/play_server.py`＋`index.html`）

### 構成
- stdlib のみの単一ファイル HTTP サーバ `play_server.py`（`ThreadingHTTPServer`）。frontend=`index.html`（SPA・毎リクエストdiskからhot-reload）。SQLite `play_catalog.db`。
- 本番: Mac Mini launchd `com.morm.play`（PLAY_PORT=8791）→ nginx:8080 → CFトンネル → play.morm.one。モデレーションは hpmini systemd `morm-modworker`。
- テーブル: content / likes / accounts / moderation_log / comments / payouts / covers / follows / referrals / challenges / challenge_awards。

### ★MORM連携＝**既に実オンチェーン**（DBカウンタではない）
- レート（`play_server.py:43`）: `VIEW_RATE=0.002`・`LIKE_RATE=0.05` MORM。`MORM_L1_RPC=127.0.0.1:8900`。`TREASURY_SEED_FILE=~/.morm-l1/producer.seed`。
- `l1_transfer(to,amount)`（`play_server.py:829`）= treasury seed で **kind:6送金**を署名→`/tx`→**`/account/{to}`残高増を最大25s polling**で着金確認。`_l1_lock`でnonce直列化。
- 発生: `earnings(m0r)`（`:540`）= 再生×VIEW_RATE + いいね×LIKE_RATE − 既払（`payouts`）。**発生=DBカウンタ／支払い=実tx**。
- 支払い経路（全て`l1_transfer`）: クリエイター報酬 `payout()`（`:855`, `/api/admin/payout`）／紹介 `settle_referrals()`（`:977`・1段のみ・非MLM）／チャレンジ `settle_challenge()`（`:1191`）。全て`tx`ハッシュを台帳に記録・冪等。
- 不正対策: 視聴/いいねは dedup+閾値（`record_watch()` `:412`・`/api/watch`ビーコンのみ加算）。

### 本人性/署名
- **ブラウザ内生成のEd25519鍵（IndexedDB `morm-play-wallet`）**。`index.html:328`。アドレス方式は **morm.one パスキーウォレットと互換**（`mormcrypto.py:94`）。
- 全変更操作は Ed25519署名を`verify_signed()`（`play_server.py:1290`）で検証。署名の唯一の口 = `index.html:351 sign()`。

### コンテンツpipeline
- 生成: MiniMax **H3**（dgx1・`samples/h3_batch.py`）→ ステーク済スタジオ口座で署名アップロード。
- 変換: `/api/upload/*` → hpmini gateway（ffmpeg→HLS）→ サーバ側で実尺/解像度を再導出しtier再判定。
- モデレーション: `mod_worker.py`（hpmini）が `/api/mod/pull`→`moderation.moderate()`（qwen2.5:32b＋qwen2.5vl:7bフレーム解析）→`/api/mod/verdict`。人手キュー`/admin/moderation`。
- 秘匿配信: `/m/<id>/...`→`_proxy()`が住宅edge（edge-mc*.ctai.online）からHLS取得しノード識別ヘッダ除去・playlist書換。R18は年齢cookie必須。

---

## 3. 統合の接続口（seam）＝ここに機能を差す

| # | 機能 | 現状 | L1差し込み | 主なアンカー |
|---|---|---|---|---|
| A | **パスキーウォレット本人性** | ブラウザ内Ed25519 | morm.one パスキーウォレットに差替（アドレス互換ゆえAPI不変） | `index.html:351 sign()` / `:328 wallet()` |
| B | **ユーザー→クリエイターのチップ（投げ銭）** | 無し（treasury→creatorのみ） | クライアント署名の kind:6 TRANSFER をユーザー鍵で。`/api/like`隣に新エンドポイント（user-signed txをL1へ中継） | `play_server.py:2272 /api/like` / `l1_transfer` は treasury専用なので**別途user-signed経路**が要る |
| C | **watch-to-earn をネイティブ化** | 発生=DBカウンタ／支払い=treasury kind:6 | VIEW_REWARD(kind7)＋`/views/{cid}`でオンチェーン視聴台帳に寄せる（原資=treasury） | `record_watch()` `:412` / `earnings()` `:540` |
| D | **実残高/ステークをL1から表示** | staked_morm=手動DB列・balance非表示 | `l1_get(/account/{m0r})`（既に有る）で実balance/stakeを`/api/me`に | `:822 l1_get` / `:635 account_public` / `:2050 /api/me` |
| E | **wMORM実USD価格** | `$0.01`ハードコード | **価格オラクル実装済＝`GET https://api.morm.one/api/price`**（`{usdPerMorm,reserves,tvlUsd,...}`・CORS`*`・15s CDNキャッシュ・失敗時0.01フォールバック）。frontendでこれをfetchし `index.html:618` の`*0.01`を`*usdPerMorm`に差替。server側 `play_server.py:653 rates` にも反映可 | `index.html:618` / `play_server.py:43,653` |
| F | **有料コンテンツ/サブスク** | 無し | ORDER三部作（エスクロー購入） | L1 `CREATE_ORDER/SUBMIT_PROOF/FINALIZE` |
| G | **クリエイター/ワーカー賞金** | gateway変換+modは有るがoff-chain | POST_JOB/CLAIM_JOB/SUBMIT_WORK_PROOF で transcode/moderate をオンチェーンPoUW化 | L1 jobs + `worker_stats` |
| H | **AI来歴（H3生成の証明）** | 無し | H3署名鍵を REGISTER_AI_SERVICE 登録→REGISTER_CONTENTに generation_id+AI署名 | L1 `/ai-services` / `_tx_register_content` |
| I | **MORM→現金化**（creatorがwMORM化） | 無し | forward(BRIDGE_BURN)→wMORM→Uniswapで USDC（`reference_morm_usd_market`の経路・api.morm.one/api/wallet/bridge-burn 実装済） | dashboard `bridge-burn` route |

### 経路の要
- 全オンチェーンは `MORM_L1_RPC`（`play_server.py:47`）＋`l1_get`/`l1_transfer`（`:822-852`）の1点に集約。ここを拡張すれば新txkind追加も一箇所。
- ブラウザから直接L1は不可（非公開）。ユーザー署名txを流すなら **api.morm.one 経由**（`submit-tx`=kind6, `bridge-burn`=kind21 が実装済。新kindは同型ルート追加が必要）。CORS=morm.one系のみ。

---

## 4. 触ってはいけない/注意
- **relayer（Mac Mini常駐・EXPORT_TOKEN=MORM・2-of-3）と Base Sepolia 3コントラクト＋Uniswapプールは稼働中**（`reference_morm_usd_market`）。forward/exitはそれ前提。
- treasury seed=`~/.morm-l1/producer.seed`（producer=treasury）。L1は127.0.0.1:8900 localhost限定（tailnet不可）。
- **セキュリティ注意（★2026-08-29: 公開露出発覚→要即ローテ）**: 旧 `ADMIN_TOKEN`（`adm_1b3…`）が本リポ(PUBLIC)にコミット済＝**漏洩済**。全 `/api/admin/*`（payout/stake/settle/moderation）を守るトークンなので**本番plistでローテ必須**（token は plist の env のみに置き、コミットしない）。手順=`SECURITY-SECRET-ROTATION.md`。
- 決済は実MORM。発生カウンタや閾値をいじる時は不正/二重支払いに注意（既存の dedup/idempotency 台帳を壊さない）。
- LLM推論はMac Mini禁止・DGX使用（`feedback_llm_host_policy`）。

## 5. 最初のおすすめ着手（新セッションでユーザーに提案）
1. **E: wMORM実価格表示**（低リスク・即体験向上。価格API=`https://api.morm.one/api/price` は**実装済・稼働中**なので、frontendでfetchして`index.html:618`の`*0.01`を差替えるだけ）
2. **D: 実L1残高/ステーク表示**（`l1_get`既存・`/api/me`拡張のみ）
3. **A: パスキーウォレット差替**（本人性統合・アドレス互換で影響小）
4. **B: 投げ銭（user-signed TRANSFER）**（新規経済導線・api.morm.oneにuser-signed中継ルート追加）
5. 以降 H(来歴)/C(watch-to-earnネイティブ)/G(PoUWジョブ)/F(有料)/I(現金化) を段階的に。

各機能の詳細設計は新セッションで、上表のアンカーとL1 primitiveを突き合わせて詰める。
