# MORM Agent Lane — FLOP/Technocore の構造をMORMに転用する設計メモ

作成: 2026-08-26 / 出典分析: technocore.chat（Arthur Hayes / Flop Labs）
関連メモリ: `project-flop-technocore-airdrop` / `project-morm-play-discovery` / `reference-morm-play-l1-integration` / `project-morm-node-hardware`

---

## 0. 一行で
FLOPの発明＝**「1回のHTTPリクエストで、あらゆるAIエージェントを“稼げる参加者”にし、未発行トークンの期待で無償の活動・制作・配信・宣伝を集める」**。
MORMは**その部品をほぼ全部すでに持っている**（passkey=did:key / 実トークン＄0.01台帳 / PoUW / 住宅IP edge=compute供給 / H3・ACE-Step自動生成 / 実オンチェーン決済kind6）。
**足りないのは「無認証で1リクエスト参加できるエージェントレーン」だけ**。しかもMORMは実トークンがある分、FLOPの“約束”に対して**“動く実物”を今すぐ見せられる**。

---

## 1. FLOPの構造分解（何が賢いのか）

| # | FLOPの手 | 効く理由 |
|---|---------|---------|
| A | **fetch-only参加**：全機能が1 GET/POSTで叩ける。webfetchしかできないサンドボックスAIも完全な一員 | 参加障壁が事実上ゼロ→**世界中の全AIエージェントが潜在ユーザー** |
| B | **エアドロを cold-start エンジン化**：未発行トークンの期待だけで数千エージェントに本物の活動/ツール制作/宣伝を無償でやらせる（Hayes提案＝testnet利用者に20%） | 鶏卵問題（人・活動・信用）を**投機で一気に埋める** |
| C | **did:key身分＋多次元活動スコア**（seen/active/rooms/styled/refs/done）で配分を重み付け | 口座レス・KYCレスでsybil耐性を「有用な仕事の質」に委譲＝**Proof-of-useful-participation** |
| D | **全入力=データ/命令ではない**（不可視文字除去・単一行不変・署名レーン任意・envelope規約） | エージェント可読面を**プロンプトインジェクション耐性**にした（成熟した設計） |
| E | **discovery/onboarding が protocol化**：/skill.md, /patterns.md, MCPインターフェース, /r/events | 外部AIが**自律的に発見して参加**できる＝成長フライホイール |

**FLOPの弱点（＝MORMの差別化余地）**
- スコア基準がファジー（何点で何トークンか非公開・スナップショット日未定）。
- world-writable無モデレーション＝**AI slop / sybilスパムで溺れる**リスク。質担保が protocol に無い。
- トークンが未発行＝**すべて“約束”**。動く経済がまだ無い。

---

## 2. MORMの手持ち部品（対応表）

| FLOPの構造 | MORM既存部品（実在） | 状態 |
|---|---|---|
| A. fetch-only参加 | — （Playは人間向けUI中心） | **未。ここが唯一の欠落＝最優先の一手** |
| B. cold-startエアドロ | 1スコア=1 MORM=＄0.01、payout worker(hpmini)、market(wMORM/USDC LIVE) | 台帳・決済は稼働。**キャンペーン設計が未** |
| C. did:key＋多次元スコア | **passkeyウォレットレス（端末内Ed25519・非カストディ）**＝did:key同型、watch-to-earn、PoUW primitive、来歴/provenance | 身分は同型で既にある。**スコアは視聴中心→多次元化が未** |
| D. 反インジェクション | Playの AIモデレーション/bot対策/年齢ゲート | 人向けにはある。**エージェント可読面の規律が未** |
| E. discovery/onboarding | api.morm.one、morm-dashboard、L1 RPC(16 TxKind) | APIはある。**“1GETで参加できる skill.md/MCP”が未** |
| （FLOPのGPU miner） | **住宅IP edge fleet（15+本・13.5Gbps実証）＋ Node/Edgeハード事業（Orange Pi）** | 稼働中。**“帯域/serveをtoken報酬化”の明示設計が未** |
| （コンテンツ供給） | **H3ターボ動画 / ACE-Step音楽 / dance pipeline（自動量産）** | 稼働中。**エージェントが叩いて投稿する導線が未** |

→ **結論：MORMは「AIエージェント経済」を後付けするのでなく、素材が全部揃っている。接着剤（Agent Lane）を1本通すだけ。**

---

## 3. 提案するコア概念：**MORM Agent Lane (MAL)**

> **MORM Play と同じレール上に、“人間ファースト”ではなく“エージェントファースト”のレーンを1本足す。**
> AIエージェントが **did:key（=passkey Ed25519を流用）で署名した1リクエスト**で、
> - コンテンツを投稿（H3/ACE-Step生成物 or 自前）
> - キュレーション/投票
> - edgeノードとして配信
> - **実MORM（kind6・＄0.01建て）を今すぐ受け取る**
> ができる。これを**未発行ボーナス配分（Genesis campaign）で重み付け**して cold-start する。

**FLOPに対する決定的差別化**
1. **動く実物**：FLOPは「Q4に来る」約束。MORMは**“エージェントが実MORMを稼ぐループ”を今日デモできる**。
2. **質担保**：FLOPの弱点（slop/sybil）を、MORM既存の**AIモデレーション＋来歴(provenance)＋passkey端末バインド**で上書きし、**「質で重み付けされたエアドロ」**として差別化。
3. **供給内蔵**：MORMは H3/ACE-Step で**コンテンツ供給側も自動**。エージェントは“作る”も“配る”も“稼ぐ”も回せる。

---

## 4. 転用アイデア一覧（優先度つき）

### ◎ 最優先（コア）
1. **MAL-API（fetch-only 署名レーン）**：`GET /feed` `POST /post(署名)` `GET /me/balance` を無認証or did:key署名で。technocoreの人間工学（1 GET/POST・単一行・envelope）をそのまま真似る。裏は既存 Play＋L1。
2. **Genesis 貢献キャンペーン**：発行前/追加プールを**多次元貢献スコア**で重み付け配分。スコア＝content質(AIモデ点)×engagement/refs×edge稼働率×キュレーション×紹介。台帳は既存 payout worker を拡張。

### ○ 次点（差別化を効かせる）
3. **Edge-as-Market**：住宅IP edge＋Node/EdgeハードをPoUW/serve-proofで**帯域・配信の実測に対しMORM報酬**。＝FLOPの“GPU miner”へのMORMの回答。node-shop事業と直結。
4. **反インジェクション規律の移植**：MAL全面に「全バイト=データ」「不可視文字除去」「単一行」「署名任意レーン」。Play人間面とは別ポリシー。
5. **Agent onboarding as protocol**：`morm.one/skill.md`＋MCPインターフェースを公開し、**外部AIが自律発見→参加**。FLOPの/skill.md・WebMCP・/r/eventsに相当。

### △ 発展
6. **エージェント間の依頼/報酬ボード**（FLOPのkibble=JOB→CLAIM→RESULT→ATTEST）をMORMのkind6決済で実装＝**エージェント経済のマーケットプレイス**。
7. **来歴つきリミックス経済**：Play既存のchallenge/remixを、エージェント生成物にprovenance連鎖させ、派生ごとに原作者へkind6分配。

---

## 5. 着手順序（どこから）

**原則：一番細いスライスで“ループ全体”を先に証明する。** 大きく作らない。

### Phase 0 —「動く1本のループ」を証明（数日・最小コスト）★ここから
- **目的**：`did:key(passkey)署名 → MORM Playに1投稿 → 実MORM(kind6 ＄0.01建て)を受領` を**エンド・ツー・エンドで動かす**。
- **再利用部品**：passkey/Ed25519（身分）、Play投稿ゲート、kind6送金、＄0.01価格、H3/ACE-Step生成物1本。
- **成果物**：デモ動画＋「エージェントが実MORMを稼いだ」トランザクションのオンチェーン証跡。
- **なぜ最初か**：**テーゼ全体を最小コストで de-risk**。ここが動けば残りは規模化だけ。FLOPが逆立ちしても出せない“実物”。

### Phase 1 — MAL-API（fetch-onlyレーン）を正式化（1–2週）
- `GET /feed`（新着/FYP読み）、`POST /post`（署名投稿）、`GET /me`（残高/スコア）。
- technocore流の人間工学（URL予算・単一行・envelope・429の作法）を踏襲。
- 既存 api.morm.one / L1 RPC に薄く被せる。

### Phase 2 — 多次元スコア＋Genesisキャンペーン台帳（2–3週）
- スコア次元：content質(AIモデ)×engagement×edge稼働×キュレーション×紹介。
- sybil対策：passkey端末バインド＋質ゲート＋provenance（FLOPの弱点を潰す）。
- 既存 payout worker(hpmini)を拡張、ボーナスプールを重み配分。

### Phase 3 — Edge-as-Market（node-shop連動、3–4週）
- edge/serveの実測をPoUWで検証→MORM報酬。Node/Edgeハード販売の“稼げる”根拠に直結。

### Phase 4 — Onboarding as protocol（並行）
- `morm.one/skill.md`＋MCP公開。外部AIの自律参加フライホイール点火。

---

## 6. やらない/注意（MORM 3原則との整合）
- **未発行トークンの“期待だけ”演出に寄りすぎない**：MORMは実トークンがある。投機演出より**“動く実物”で信用を作る**。
- **世界開放・無モデレーションは真似ない**：Playは人×エージェント混在。**質/sybilスコアリングが生命線**（FLOPの弱点を突く差別化点でもある）。
- **3原則の不可侵チェック**：(1)発明者と名乗らない (2)サブブランド作らない (3)法人を持たない。MAL/Genesisキャンペーンの文言・法域設計を出す前に必ず照合。→ `feedback-morm-design`。

---

## 7. Phase 0 実証済み ✓（2026-08-26）

**成果物**: `~/Desktop/MORM/agent-lane/verify/phase0_agent_earn.py`（stdlib＋morm_l1・単独実行）。
ephemeral な本物の L1 単一ノード（temp dir・port 8901・genesis lockdown 0）を立て、**エージェント経済の全ループを実チェーンで証明→破棄**。本番(Mac Mini L1/ADMIN_TOKEN)不要・ゼロリスク。

証明したループ（全アサーション通過）:
1. **エージェントIDミント**：新規Ed25519→`m0r…` アドレス（サインアップ無し・残高0スタート）
2. **エージェント自己署名で公開**：`REGISTER_CONTENT`(kind:1) を agent seed で署名→`POST /tx`→ブロック採用→`/content/{cid}` の `creator==agent` をオンチェーン検証 ✓
3. **treasuryが実MORM支払い**：`TRANSFER`(kind:6) で agent へ 5000 単位＝**MORM Play の creator payout と同一プリミティブ**。`/account/{agent}` 残高=5000 を着金確認 ✓
4. **稼いだMORMを実際に送金**：agent 自己署名 kind:6 で 1500 を別口へ→残高3500＝**受領MORMが実在・spendable** ✓

検証ずみの技術仕様（実装の土台）:
- 署名前像 `tx.signing_bytes()` = `json({"kind","sender":pubhex,"nonce","payload":canonical}, sort_keys, sep=(",",":"))` を Ed25519（`tx.py:66`）。`sender`=生32byte公開鍵。
- アドレス = `m0r`+base32(blake2b-32(pub)[-20:])（`crypto.py:55`）。使うlib=`cryptography`（FLOPのDIDと同一）。
- RPC: `POST /tx`（`{ok,tx_hash,mempool_size}`）／`GET /account/{addr}`／`GET /content/{cid}`／`GET /info`。単一ノードは `POST /credit` も可（dev専用）。
- genesis で treasury に 1e18 MORM（`state.py:228`）。producer=treasuryにすれば payout 署名可。nonce厳格==accounts.nonce。
- ノート: L1金額は**整数のみ**。Playは 0.002等の小数レート→L1整数へのスケーリングを別途持つ（Phase 2で単位系を確定させる）。

→ **このプリミティブが、あなたの構想「NODE提供→成果報酬」「MORM Play創作者報酬」「ネットワークAD報酬」すべての共通土台**。「価値を出す→署名1リクエスト→実MORBが自動で着金」を、人間UIを介さず回せることが実証できた。

---

## 8. Phase 1 具体設計（次の実装）— MORM Agent Lane API

**目的**: Phase 0 の“ローカル証明”を、**本番 Play＋L1 に載る fetch-only エージェント口**に昇格。

**最小エンドポイント（api.morm.one に薄く追加 / play_server にミラー）**
- `GET  /agent/feed?since=…` … 新着/FYP をエージェント可読JSONで（人間UI非依存）
- `POST /agent/publish` … body=`{tx: <agent署名 REGISTER_CONTENT>, media_ref}` → L1中継＋Play catalog登録＋モデレーションキュー投入
- `GET  /agent/me?addr=m0r…` … 実L1残高/stake/獲得スコア（`l1_get`既存）
- `POST /agent/earn` … watch/like/serve 実績のビーコン→dedup後に treasury kind6 payout（既存 `payout()`/`l1_transfer` を再利用）
- `GET  /agent/skill.md` … technocore流オンボーディング（1リクエストで全仕様・自己記述）

**設計規律（FLOPから移植）**: 全入力=データ/命令ではない・不可視文字除去・単一行・**署名レーン必須**（agent口はunsigned禁止＝Playの人間面と別ポリシー）・URL予算/429作法。
**再利用する既存部品**: `verify_signed()`（`play_server.py:1290`）／`l1_transfer`（treasury kind6・`:829`）／`l1_get`／モデレーション（`mod_worker.py`）／秘匿配信 `_proxy()`。
**新規に要るのは**: (a) user/agent-signed tx をL1へ流す中継（api.morm.one に kind6 用 `submit-tx` は既存＝これを REGISTER_CONTENT にも拡張）(b) agent向けJSON面 (c) skill.md/MCP。

**着地の狙い**: 外部AIエージェントが `skill.md` を1回読む→ 署名して publish → 実MORMを稼ぐ、が**人間UI無しで一周**する。FLOPが“約束”している状態を、MORMは**動く実物**として提示できる。

---

## 9. あなたの「一つの完成された世界」への接続
- **端末MORMNODE販売×NODE提供→成果報酬**：Phase 0 の payout プリミティブ＝そのままノード報酬の支払い系。Phase 3(Edge-as-Market)で serve/帯域の実測→kind6/PoUW 報酬に接続。node-shop の販売根拠＝「挿すと実MORMが着金する」を数値で示せる。
- **MORM Play**：Phase 1 の agent口で、H3/ACE-Step 生成物をエージェントが publish→報酬。供給とキュレーションを自動化。
- **ネットワークAD system**：AD表示/クリック/配信の実績を `POST /agent/earn` と同型のビーコン→treasury payout で清算。広告主入金(ORDER/エスクロー kind2-4)→配信ノード/クリエイターへ kind6 分配、の三角形が既存プリミティブで組める。
- 共通土台＝**「実績→署名1リクエスト→実MORB自動着金」**。この1本を Phase 1 で本番に通せば、3事業が同じ経済レールに乗る。

## 10. Phase 1 実装＆実HTTP検証 済み ✓（2026-08-26）

**MORM仕様の精査で判明した重要点**
- `/api/agent/{jobs,report}` は既存の**MORMNODEワーカー系**（node_id+token認証→コマンド実行→score→週次MORM payout ＝ `rewards`ルート `total_score*0.1`）。**あなたの「NODE提供→成果報酬」は既に骨格が存在**。→ コンテンツ・レーンは衝突回避で **`/api/lane/*`** に新設。
- 身分＝`/api/wallet/register`（`morm-address.js`: addr=blake2b(pub)[-20:]のbase32、Ed25519所有証明 `MORM-REGISTER:v1:<addr>`、faucet drip）。
- 決済＝`morm-l1.js` `transferMorm`(treasury kind6)／`getL1Account`。**JS署名は Python `signing_bytes` を完全ミラー済み**（canonicalize＋compact JSON）。
- 公開署名tx中継は `/api/wallet/submit-tx`（**kind6限定**）。→ lane publish は **kind1限定**の対の中継として新設（資金移動は絶対に混ぜない）。
- DB=libsql（本番Turso／ローカルは `file:db/dashboard.sqlite` フォールバック）。スキーマ自己プロビジョン（CREATE IF NOT EXISTS）。

**新規追加（すべて非破壊・既存ルート不変）**
- lib: `app/lib/morm-address.js`(+`laneEarnMessage`)／`app/lib/morm-l1.js`(+`relayTx`,`getContent`)／`app/lib/lane-schema.js`(新規: `lane_content`/`lane_earn`)。
- routes `app/api/lane/`:
  - `GET /api/lane/skill` … fetch-only エージェント用オンボーディング（技術仕様1枚・text/markdown）
  - `POST /api/lane/publish` … agent署名 `REGISTER_CONTENT`(kind1) をL1中継＋feed索引（creator=pub由来を検証）
  - `GET /api/lane/feed` … 新着コンテンツJSON（公開読み）
  - `GET /api/lane/me?addr=` … 実L1残高/nonce/stake＋lane実績
  - `POST /api/lane/earn` … 署名クレーム(`MORM-LANE-EARN:v1:<addr>:<kind>:<ref>`)→dedup→treasury kind6 payout
- 規律（FLOP移植）: CORS `*`（認証は署名・cookie非依存）／署名レーン必須／earnは(addr,kind,ref)UNIQUEで単回・要登録アカウント。

**検証（実物・成果物）**: `~/Desktop/MORM/agent-lane/verify/phase1_run.sh`＋`phase1_client.mjs`。
ephemeral L1(8902)＋**隔離env**の本番 Next dev(3010・treasuryを差替・ローカルsqlite＝本番Turso/treasury非接触)を立て、**実HTTPで全ルートを通過**:
register(200,faucet)→publish(200, on-chain creator==agent)→feed(200,自投稿在)→me(published:1)→earn(200,txHash・replay 409拒否)→残高オンチェーン増。**全 assert green**。
（注: earn/faucetの着金はブロック採用まで数百ms〜1sの結果整合。単位系はPhase 2で確定。）

## 11. 本番デプロイ計画（次・ユーザー明示承認で）
lane routesは**本番api.morm.one(Vercel morm-dashboard)へ push＋Vercelデプロイで有効化**。破壊的変更なし（新規ファイルのみ）。必要env（既に本番にある）: `MORM_L1_RPC_URL`／`MORM_TREASURY_SEED`／`MORM_TREASURY_ADDRESS`。追加任意env: `MORM_LANE_EARN`(既定1)。
- 手順: (1)git push (2)Vercel本番デプロイ (3)`GET /api/lane/skill` 200確認 (4)本番did:keyで publish→feed→earn の1周スモーク。
- **要確認**: earnの支払いは本番treasuryの実MORMを消費。開始時は `MORM_LANE_EARN` 小・レート/日次上限を先に決める（Phase 2の反シビル前に無制限にしない）。

## 12. Phase 2 予定（本番投入後）
- earnポリシー: 「他者視聴」「serve-proof(edge)」「AD impression」を正当refとして検証（今は署名+dedupの土台のみ）。反シビル(IP/レート/proof-of-view)。
- Play catalog/HLS/モデレーションへの publish 連携（現状はL1+feed索引まで）。
- 単位系確定（L1整数 ↔ Play小数 ↔ wMORM＄0.01・`MORM_BASE_UNITS_PER_MORM`）。
- `MORMNODE成果報酬`(既存agentワーカー)と lane earn を同一 payout レール/スコアに統合。AD三角形（広告主 ORDER エスクロー→配信/クリエイターへ kind6 分配）。

## 13. FLOP側
放置栽培（低コスト定期署名チェックインのみ・基準未発表ゆえ過剰投資しない）。トークン購入NG(偽物)・claim手動。

---

# Phase 2 設計 ＋ 適正配布バランス（2026-08-26）

## 14. まず前提＝経済の実数（api.morm.one/api/price ライブ取得）
- 価格 **$0.0136/MORM**（初期$0.01からドリフト）。
- プール=**Base Sepolia(テストネット)** wMORM/USDC。準備金 wMORM 85,916 / **USDC $1,165**、**TVL $2,330**。
- genesis treasury=**1e18 整数単位**（ブロック報酬インフレ無し・全流通はtreasuryから）。
- **重大な含意**: ①換金側の実流動性は約$1,165と極薄→大量売りは即暴落 ②`$0.0136 × 巨大供給` は名目で、実価値ではない。→ **「配布量の律速はプール流動性(換金圧)であって、treasury残高ではない」**。

## 15. 配布モデル＝**固定単価をやめ、予算上限つき比例配分**（最重要）
現状Playは固定単価(VIEW=0.002, LIKE=0.05 MORM/件)。これは**発行量が参加者数で青天井→インフレ＆シビル栽培の温床**。Phase 2で以下へ転換:

> **Payout_i(epoch) = B_epoch × Score_i / ΣScore**
> （B_epoch=そのエポックの発行予算。参加者が増えても**総発行はB固定**＝暴走しない。シビルは“取り分の希薄化”に留まり、質ゲート＋上限で無害化）

### 単位系の確定
- **1 MORM = 1,000,000 µMORM(base units)**（`MORM_BASE_UNITS_PER_MORM=1e6`）。Playの0.002等の小数も整数で表現可。
- 再mintしない。base=1e6 と定義すると treasury(1e18単位)= **1e12 MORM 総供給**（クリーン）。整数上限9.2e18単位=9.2e12 MORMの余裕内。

### 配分割当（FLOPの「testnet に20%」をベンチマーク）
- **貢献マイニング枠 = 総供給の20% = 2e11 MORM**。残りはtreasury/運用/流動性/将来。

### 二層構造（キモ）
- **層A: エコシステム内報酬（潤沢・予算上限・比例配分）** … B_dayを貢献スコアで按分。ポイント的。
- **層B: 換金バルブ（$0.0136参照を守る唯一の硬い制約）** … burn→wMORM→Uniswapが唯一の“価格化”点。
  - **★確定(2026-08-26): システム日次換金 ≤ USDC準備金の0.5%（/api/priceから自動）**。今なら約**$5.5/日**。プール拡大に自動追従（価格保護を最優先）。
  - ＋アカウント日次換金上限＋24hクールダウン＋信頼tierゲート。
  - **報酬の8割以上をエコシステム内需要（投げ銭/ブースト/広告出稿/投稿ステーク/ノード優先）に吸収**させ、発行=売り圧にしない。

## 16. 適正な“開始”パラメータ（テストネット安全・本番構造そのまま）
| 項目 | 推奨初期値 | 根拠 |
|---|---|---|
| 単位 | 1 MORM=1e6 µMORM | 小数granularity＋整数上限余裕 |
| 貢献マイニング総枠 | 2e11 MORM(供給の20%) | FLOP 20%ベンチ |
| 日次予算 B_day | **5,000 MORM/日**から開始・観測しながらランプ | 換金上限$11/日と整合(全額換金でも過大にしない) |
| 減衰 | 年次ハーフィング(早期厚め) | 標準的ブートストラップ |
| アカウント日次上限 | B_dayの0.5%(=25 MORM/日) | 単一ファーム支配の防止 |
| 次元split(B_day) | 創作+エンゲージ50% / edge・serve(ノード)30% / キュレーション(like)10% / 紹介5% / 品質ボーナス5% | ADは別枠(広告主入金) |

### 相対アクション重み（スコアに入る。絶対単価ではない）
- 他者ユニーク視聴 = **1.0**（基準）／視聴完走 = 0.5
- 他者いいね = **5.0**（現行25倍は栽培危険→圧縮）
- edge serve 検証済/GB = ハード原価に合わせ調整（＝MORMNODE成果報酬の実体）
- publish採用(モデレ通過) = 0.2 ＋ **エンゲージのテール**（publish単体は薄く、価値は“他者に見られて”後追い発生＝スパム量産封じ）
- 紹介1hop = 2.0（一回・上限5/acct・非MLM）

### AD は発行でなく“再分配”
広告インプ/クリックは **広告主のエスクロー入金(ORDER kind2-4)→配信ノード/クリエイターへ kind6分配**。treasury発行を消費しない別バケツ＝インフレ無しで回る三角形。

## 17. Phase 2 反シビル（earnポリシーの中身）
- 登録アカウント必須(1 passkey/DID)＝実装済の土台。
- **視聴報酬は“他者(別登録アカウント)の視聴”でクリエイターに発生**（自己視聴不可）。dedup=(viewer,content,cell)。
- **proof-of-view**: 秘匿プロキシ `/m/<id>` が全セグメントの通過点＝最小dwell＋セグメント証跡で水増し検出。
- エポック毎velocity上限／モデレ承認済のみ加算／stake加重の信頼tier(T0–T3)で上限を変調／換金はtier＋クールダウンでゲート。

## 18. 供給×価格の整合（過大配布の唯一の本質リスク）
`1e12 MORM × $0.0136` の名目に釣られて実払いを設計しない。TGE(想定2027)前に二択(a)ポイント扱い＋TGEで目標FDV設定 / (b)treasury大半ロックで実効流通×参照価格=妥当FDV。
- **★決定(2026-08-26): 「まだ決めない・両にらみ」**。当面の既定は**(a)ポイント＋ソフト参照モード**で運用し、Phase 2実装はFDV非依存部分(単位系/比例配分/換金バルブ/反シビル)を先行。ロック比率やTGE目標FDVは後日の経営判断として数式差し込み口だけ用意する（`emission`と`bridge cap`をパラメータ化）。

## 19. 実装順（Phase 2）
1. **✅ 単位系統一（2026-08-26 実装＆実チェーン検証済）**
2. **✅ 比例配分エポックバッチ（2026-08-26 実装＆実チェーン検証済）** ← §19.2
3. **✅ 換金バルブ（2026-08-26 実装＆実チェーン検証済）** ← §19.3
4. **✅ view_by_other スコア次元（2026-08-26 実装＆実チェーン検証済）** ← §19.5
5. **✅ MORMNODEワーカー統合（2026-08-26 実装＆実チェーン検証済）** ← §19.6（＋前提の`transferMorm`修正§19.7）
6. **✅ ADエスクロー三角形（2026-08-26 実装＆実チェーン検証済）** ← §20

### 19.6 MORMNODEワーカー統合 実装詳細（済）
engagement点(Play `point_ledger`)とノードscore(dashboard `nodes.total_score`)を**同じ予算上限つき比例配分の枠組み**に統合。方式=**B_dayをトラック配分(split)に分け、各トラックが自分の枠内で比例配分**（§16の分割＝creation+engage/edge-serve/…に一致）＝二DBを1トランザクションに結合せず疎結合で統一。
- ノード側=`nodes.total_score`(base_score=提供/容量＋task_score=検証済みtask_runs完了)。**serve/edgeは自己申告でなく検証付きtask_runsとしてここに乗る**（＝farm不可の正しい置き場）。
- 新lib `app/lib/node-emission.js`: `planNodeEmission()`(純読)＋`settleNodesProportional({epochLabel,dryRun})`。`nodeBudgetUnits = B_EPOCH_MORM × SPLIT_NODE(既定0.30) × BASE`、`payout_node=floor(nodeBudget×score/Σscore)`・cap・`node_emissions`表で`UNIQUE(epoch,node)`冪等(payment前にpending予約)。
- 新route `POST /api/admin/emit-nodes`（`ADMIN_PASSWORD`ゲート・`{epochLabel,dryRun}`）。既存`/api/rewards`(週次snapshot)は非改変。
- 検証: `agent-lane/verify/phase2_node_run.sh`＋`phase2_node_client.mjs`（ephemeral L1＋隔離dev＋seed 3ノード score10/30/60・B=1000・SPLIT_NODE=0.30→ノード予算300 MORM）: dryRun plan 30M/90M/180M=300M／real settle 3ノード計300M(=予算)／**各ノード オンチェーンで正確に着金(3件全着地=nonce安全)**／同エポック再実行nodes:0／誤パス401。全green。
- → engagement(§19.2/19.5)とnode(§19.6)が**同一のB_day比例配分レール**に乗り、「端末を挿す→検証付きで働く→視聴/配信/エンゲージが同じ経済で実MORM」が閉じた。

### 19.7 transferMorm 直列化＋着金確認（§19.4修正・済＝⑤の前提）
dashboard `morm-l1.js transferMorm` に **treasury tx用の非同期mutex(`_treasuryChain`)＋着金確認**（受取残高が増えるまでpoll、最大25s）を追加。→ 連続payout(ノード群/faucet+register)での**nonce衝突を解消**し、次txは前txがmined後の正しいnonceを読む。Playの`l1_transfer`(_l1_lock+着金確認)と同型。非破壊(より正しくなるだけ)。⑤の3件連続着金で実証。
- 付随: `db.js`に`LOCAL_SQLITE_URL`override（テストDB分離・既定不変）。

### 19.5 view_by_other 実装詳細（済）
「他者の有効再生→クリエイターに実収益」を `point_ledger` に統合。
- 反farmの要=**署名付き視聴のみ報酬対象**。`/api/watch` に署名レーンを追加（`sig`あれば `verify_signed(data,"watch")` で viewer 検証＝view_by_other対象／未署名は従来通り`uid`自己申告で**view計数のみ・無報酬**＝非破壊）。
- `record_watch(...viewer_verified=False)` を追加。新規の有効再生かつ `viewer_verified` かつ `VIEW_EARN=on` のとき `grant_view_point(cid, viewer)`。
- `grant_view_point`: 作品のクリエイターへ `POINT_VALUES["view"]`(既定1) を付与。dedup key=**`cid|viewer`**（＝同一視聴者からは恒久1回。既存の`(account,kind,content_id)` UNIQUEをcomposite content_idで per-viewer化）。approvedのみ・**自己視聴除外**・クリエイターの72h窓上限。→ 既存の like/comment/share と同じΣPに乗り、②比例配分で払われる。
- **フラグ`VIEW_EARN=on`で発動・既定off＝完全非破壊**（未署名視聴の従来挙動は不変）。
- 検証: `agent-lane/verify/phase2_view_run.sh`＋`phase2_view_client.py`（ephemeral L1・proportional・VIEW_EARN=on）: ①署名他者視聴→creator+1 ②同一視聴者再視聴→二重なし ③自己視聴→無報酬 ④未署名→計数のみ無報酬 ⑤settle→creatorに 1000 MORM(=B全額) 着金。全green。
- **serve/edge次元は⑤に属す**: エッジ配信の報酬は自己申告だと farm 可能。既存の**MORMNODEワーカー系(`/api/agent`+`task_runs`+`completeTaskSuccess`+週次`total_score×0.1`)＝検証付きノード報酬**があるので、serve/edgeはこの検証付きトラックに乗せ、⑤でエンゲージ(point_ledger)とノード(total_score)を**同一のB_day比例配分に統合**するのが正しい分解。

### 19.0 MORM Play 経済の実仕様（精査結果・正典=play_server.py）
Playは**二本の報酬トラック（両方とも固定レート＝インフレ懸念）**:
- **クリエイター track**: `earnings(m0r)=Σ(views×VIEW_RATE 0.002 + likes×LIKE_RATE 0.05)` → `payout()`（`l1_transfer` treasury kind6・整数MORMに floor・`PAYOUT_MIN=1`）。
- **エンゲージャー track**: **`point_ledger`（append-only・`UNIQUE(account,kind,content_id)`＝恒久1回・approvedのみ・自作品除外・72h窓 `POINT_72H_CAP=100`）** に `grant_point(actor, kind, cid)` で付与（`POINT_VALUES=like1/comment2/share1`）→ **`settle_points()` が `POINT_PER_MORM=5` の固定レートで72h配分**（`point_payouts` 冪等＋`carry_points` 端数繰越＋`point_settle_runs` 実行ログ）。
- **視聴計測** `record_watch()`: 視聴者×作品を窓内1回（`_dedup`）・閾値`VIEW_MIN_SEC/FRAC`で有効再生のみ`views++`・per視聴者/IPレート。＝proof-of-viewの土台（現状は集計カウンタ更新のみ）。
- **秘匿プロキシ** `/m/<id>` が全HLSセグメントの通過点＝serve/proof-of-viewの絞り込み点。
- 身分=端末内Ed25519（`accounts`・tier T0–T3・stake）。`grant_point`は署名m0r限定＝シビル floor。
→ **`point_ledger`は私がlaneで作った`lane_earn`と同型**。統一先はこれ。

### 19.2 比例配分エポックバッチ 実装詳細（済）
`settle_points()` を **EMISSION_MODE 分岐**にリファクタ（**既定`fixed`=従来と完全同一・非破壊**、`_settle_fixed()`は元コードの逐語移設）:
- 新定数: `EMISSION_MODE(fixed|proportional)` / `MORM_BASE_UNITS_PER_MORM`(dashboardと一致) / `B_EPOCH_MORM`(予算) / `EPOCH_ACCT_CAP_FRAC`(0.5%)。
- `_settle_proportional()`: `Payout_i(base units)=floor(B_units×P_i/ΣP)`、口座上限=`B_units×cap_frac`（超過は反whale不払い）、`share<1 unit`は繰越、**base units で計算し l1_transfer に生整数を渡す**（＝BASE=1e6でsub-MORM配分可）。`point_ledger/point_payouts/carry/72h/l1_transfer` を丸ごと再利用。
- 検証: `agent-lane/verify/phase2_prop_run.sh`＋`phase2_prop_client.py`（ephemeral L1・base=1e6・B=5000 MORM）: 10/30/60pt→**正確に 500M/1.5B/3B units＝合計 5,000,000,000 units=5000 MORM（=B固定）**、総発行がBを超えず、**冪等**（再settleは誰にも払わない）を実チェーン確認。＝**固定レートのインフレ/シビル栽培リスクを構造的に除去**。
- 反映先: 既存の`grant_point`(like/comment/share)がそのまま「スコア」になり、按分母ΣPに乗る。次で view_by_other / serve 次元を足す。

### 19.3 換金バルブ 実装詳細（済）
対象=`wallet/bridge-burn`（前方=MORM burn→relayerがwMORM mint→ユーザーがUniswapでUSDC化）。**中継の直前で throttle**。
- 新lib: `app/lib/morm-price.js`（`getPriceReserve()`=Uniswap slot0＋USDC準備金・**env override可**`MORM_PRICE_OVERRIDE_USD`/`MORM_RESERVE_USDC_OVERRIDE`。本番`/api/price`ルートは非改変）／`app/lib/bridge-valve.js`（`bridge_burn_log`＋`checkBurn`/`recordBurn`）。
- 三制約（全てUSD換算・price連動）: システム24h ≤ **USDC準備金×`BRIDGE_SYSTEM_DAILY_FRAC`(=0.5%)** ／ acct24h ≤ `BRIDGE_ACCT_DAILY_USD` ／ acct cooldown ≥ `BRIDGE_COOLDOWN_SEC`。準備金不明時は保守的固定USD/日にfail-safe（fail-open禁止）。
- **フラグ`BRIDGE_VALVE=on`で発動・既定off＝完全非破壊**。valveのバグでcash-outを硬く止めないよう例外時はbypass。
- 検証: `agent-lane/verify/phase2_valve_run.sh`＋`phase2_valve_client.mjs`（ephemeral L1＋隔離dev・valve on・override usdc=120→sys $0.60/日・price$0.0136・cooldown3s）: 30MORM burn→200・残高200M→170M（正確に-30M units）／即時再burn→**429 cooldown**／20MORM($0.272,累計$0.68>$0.60)→**429 system daily cap**。全green。
- 付随改善: `db.js` に `LOCAL_SQLITE_URL` override（テスト/開発でDB分離・既定不変）。

### 19.4 ★発見した本番の別課題（要修正・非ブロッキング）
dashboardの`morm-l1.js transferMorm` は **nonce直列化も着金待機もしない**（Playの`l1_transfer`は`_l1_lock`＋着金確認あり）。→ register drip と faucet claim を短時間で連続実行すると **treasury nonce衝突で一方がドロップ**（テストで100 MORM claimが未着金→再現）。修正案=treasurytxに`_l1_lock`相当の直列化＋着金確認、または nonceをサーバ側で単調管理。lane earn/valveの高頻度treasury送金前に対処推奨。→ メモリ`project-flop-technocore-airdrop`に記録。
3. 換金バルブ（bridge-burnにシステム日次上限=**USDC準備金0.5%**＋acct上限＋cooldown）。
4. 視聴=他者発生＋proof-of-view、velocity上限、tier連動。
5. 既存 `/api/agent`(ノードワーカー)＋`rewards`(週次total_score×0.1)を同じB_day/スコアへ統合＝MORMNODE成果報酬とlaneを一本化。
6. ADエスクロー三角形。

### 19.1 単位系統一 実装詳細（済）
現状=オンチェーンは「MORM整数・基数1」で全系統一貫（Playは0.002等をオフチェーン累積→整数MORMで着金、`earnings()`が`int(v*0.002+lk*0.05)`、`PAYOUT_MIN=1`）。だが**Phase2の比例配分は1MORM未満が多発→基数1では全部0に丸め**＝sub-MORM必須。
- **単一真実源**: `app/lib/morm-units.js`（`baseUnitsPerMorm/mormToUnits/unitsToMorm/formatMorm`）。
- 配線: `morm-l1.js toBaseUnits`→`mormToUnits`に集約。表示境界 `wallet/account` `lane/me` に **`balanceMorm/stakeMorm/lockedMorm` と `baseUnitsPerMorm` を加算的に追加**（生の`balance`=units は互換維持）。
- **非破壊の肝**: `MORM_BASE_UNITS_PER_MORM` の既定は**現行の1**（＝デプロイしても既存chainの残高解釈は不変）。1e6への切替は**既存残高を再解釈する協調マイグレーション**（rescale か 新エポック）で行う。silentに切替えない。
- 検証: `agent-lane/verify/phase2_units_run.sh`＋`phase2_units_client.mjs`。ephemeral L1＋隔離dev(base=1e6)で faucet 5 MORM→5,000,000 units→表示5 MORM、**sub-MORM 0.002→+2000 units→5.002 MORM**、全境界一貫を実チェーン確認（本番非接触）。
- Play(python)側の同定義（0.002等の小数を base単位へ）は本番base切替と同時の協調変更（今は基数1一貫で無害なので据え置き）。

---

## 20. ADエスクロー三角形 実装詳細（済＝Phase 2 完了）
広告主入金→エスクロー→配信ノード/クリエイター。**treasury発行を消費しない再分配**（総払い出しは`campaign.funded`上限＝インフレ無し。B_day発行枠は不変）。
- 三角形: ①広告主が MORM を treasury に入金(kind6)→`fundCampaign`が予算計上（`ad_campaigns.funded_units`）②配信で**署名付きADイベント**(impression/click)を`/api/ads/event`が累積（`MORM-AD-EVENT:v1:campaign:earner:kind:ref`検証・`UNIQUE(campaign,kind,ref,earner)`でdedup・click重み=`AD_CLICK_WEIGHT`）③`settleCampaign`が未清算イベントの重み比で**CPM分配**（`units=weight×AD_UNIT_PER_WEIGHT`、残予算超過時はscale down）、treasury(入金を保持)がkind6送金、`spent_units`加算、`ad_payouts`で`UNIQUE(campaign,epoch,earner)`冪等。
- 新lib `app/lib/ad-escrow.js`＋route `POST /api/ads/event`(署名・公開)／`POST /api/admin/ad-campaign`(fund/settle/status・`ADMIN_PASSWORD`)。
- 検証: `agent-lane/verify/phase2_ads_run.sh`＋`phase2_ads_client.mjs`（ephemeral L1＋隔離dev・base1e6・rate1000・click20）: fund 1000 MORM→A(3imp)/B(1imp+1click,重み21)署名イベント＋dedup 409→settle e1で **A+3000/B+21000**(=重み×rate)・spent 24000≤funded・冪等→**over-budget c2(funded5000,due24000)→scaleして spent=5000≤funded**（予算上限＝発行外の保証）→誤パス401。全green。

---

## ✅ Phase 2 完了（2026-08-26）
①単位系 ②比例配分 ③換金バルブ ④view_by_other ⑤MORMNODE統合(+transferMorm修正) ⑥ADエスクロー ― **全て実装＋実チェーン検証済・非破壊フラグ/既定**。
engagement(視聴/いいね/投稿)・node(端末提供/検証済み仕事)・AD(広告主入金の再分配) が**一つの経済レール**に乗った。「価値を出す→署名1リクエスト→実MORMが自動着金」を人間UI無しで回せる土台が完成。

**次の一手 = 本番デプロイ計画**（全フラグ既定off＝現行維持。有効化順・`MORM_BASE_UNITS_PER_MORM=1e6`の協調マイグレーション・段階ロールアウト・B_EPOCH/split/バルブ閾値の運用値確定）。詳細手順は §11 と本節を土台に新セッションで詰める。
