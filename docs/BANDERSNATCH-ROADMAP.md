# MORM Bandersnatch — 実装ロードマップ

> 策定 2026-09-04 ／ 概念正本=`~/Downloads/08-bandersnatch.md`・公開概要= http://pilot.masterclass.tokyo/morm/ （Basic認証）
> 位置づけ: **MORMの次マイルストーン**。既存本番基盤（PLAY / L1 / lane / payout worker / market）の上に乗る新レイヤー。
> 前提: 抽選・チケット・リセール市場のコードは**リポジトリに一切存在しない＝完全な新規実装**（grep確認済）。

---

## 0. 先に決めるべきこと（ここが未確定だと全フェーズが動かせない）

概念ドキュメントは配分（賞金85%/配当10%/運営5%）は定義しているが、**プールの原資**と**適法性の建て付け**を定義していない。ここはコードでなく意思決定。

### D-1 ★賞金プールの原資 — 【決定済 2026-09-04：ブレンド型】

チケットは「週1枚/台を無料配布」＋「Mad HatterはP2P（運営1%手数料のみ）」で、概念上プールの原資が未定義だった。**新規発行（＝売り圧）を避けつつ意味のあるジャックポットを作る**ため、以下の3層ブレンドで確定。

| 層 | 原資 | 役割 |
|---|---|---|
| **主原資：burn振替(D)** | 機能burn/決済burn（エンジン①②）で焼く予定のMORMの**一部をプールへ** | ジャックポットが利用量に比例。新規発行ゼロ |
| **自己資金(E)** | Mad Hatter手数料1% ＋ 各週プールの運営5%分の一部を翌週へ繰越 | 二次流通が育つほど還流・閉ループ |
| **ブートストラップ(A・逓減)** | トレジャリーが**週次下限**まで補填（**週次ハードキャップ付き**・逓減サンセット） | 初回からプールが空にならない下支え。D+Eの成長で縮小 |

#### 循環性・片落ちの判定（設計の芯）
素の「パススルー（毎週の入り=出を全額配る）」は**循環せず片落ち**になる。理由と対処:
- **循環性**: 当選金が換金されればループ外へ抜け、ops取り分も抜ける＝会計的に一方通行。循環を成立させる2経路を設計で用意する — (1)**当選金の再投入**（当選者がshop決済/機能burn/Mad Hatterで再び使う→翌週プールへ戻る＝行動誘因ループ。強制不可なので「利用量に比例する変換エンジン」と正直に位置づける）、(2)**★リザーブ**（毎週全額配らず貯め、好調週の余剰を不調週へ回す＝時間軸の循環）。
- **片落ち（4つの非対称）**: ①トレジャリーがbootstrapで一方的放出（意図的だが恒久化は片落ち）②高再生オーナーの二重取り（転売益＋発行元配当）＝富の集中 ③burn振替による受動ホルダー→能動プレイヤーの価値移転 ④**パススルー由来の賞金ボラティリティ＝暴落スパイラル（低活動週→賞金激減→誘因低下→さらに縮小）**。
- **対処**: ①④は**リザーブ1つで両方解消**（下記の目標駆動方式でbootstrapは不足時のみ発火＝reserveが積むと自動サンセット）。②は**発行元配当キャップ＋確率重みの対数圧縮/上限**(D-5)。③は振替率≤0.2で80%焼却＝純デフレ維持＋移転先はNODE保有者＝活動報酬として正当化。

#### 決定パラメータ（リザーブ入り・目標駆動／初期値・全て env 調整可・ドライラン2-3週で実測較正）
毎週の組成を**目標ジャックポット＋リザーブ**で行う（パススルーは廃止）:
```
inflow  = burn_redirect_week + madhatter_ops_carryover
target  = BS_POOL_TARGET ；  reserve ≥ 0（前週繰越）
if inflow ≥ target:      payout=target；余剰→reserve（上限 BS_RESERVE_CAP）；bootstrap=0
elif reserve が不足を賄える: reserveから補填；bootstrap=0
else:  bootstrap = min(target − inflow − reserve, BS_BOOTSTRAP_WEEKLY_CAP)
       payout = min(target, inflow + reserve + bootstrap)   # なお不足なら floor=available
payout を 85/10/5 に分配（運営5%の一部を翌週 carryover へ）
```
→ **bootstrapはinflowもreserveも足りない時だけ発火**＝成長でreserveが積むと**トレジャリー補填が自然にゼロへ（自動サンセット）**。手動の逓減スケジュール不要。

| パラメータ | 初期値 | 意味 |
|---|---|---|
| `BS_BURN_REDIRECT_FRAC` | 0.20 | burnの20%をプール、80%焼却（純デフレ維持・≤0.3を厳守） |
| `BS_MADHATTER_FEE` | 0.01 | Mad Hatter手数料1%→プール |
| `BS_POOL_TARGET` | 100,000 MORM(≈$1,000) | 目標週次ジャックポット（絶対額は実測較正） |
| `BS_RESERVE_CAP` | 400,000 MORM（target×4≈1ヶ月分） | リザーブ上限 |
| `BS_BOOTSTRAP_WEEKLY_CAP` | 100,000 MORM（target×1） | トレジャリー補填の週次天井 |
| `BS_DIVIDEND_ISSUER_CAP` | 配当10%の20%/単一発行元 | 富の集中(#2)抑制 |
| 確率重み | `w=log1p(honest_views)`＋95%tile上限 | farm/集中抑制（D-5） |

**動作例（同一パラメータ・3シナリオ）**

| 週 | inflow | reserve(前) | bootstrap | payout | reserve(後) |
|---|---|---|---|---|---|
| 立上げ(週1) | 30,000 | 0 | **70,000** | 100,000 | 0 |
| 好調週 | 115,000 | 0 | 0 | 100,000 | +15,000 |
| 不調週 | 60,000 | 40,000 | **0**（reserve充当） | 100,000 | 0 |

立上げ補填最大→活動が育つと自動0へ。好調週余剰が不調週を埋める＝**回っている**。

**実装接続点**
- **burn実装箇所を特定**し、各burnサイトで `redirect_frac` 分を焼却でなく**プール蓄積口座 `bs_pool`（トレジャリー管理のm0r）**へTRANSFERするよう分岐（Phase1で口座、Phase4でプール確定）。エンジン①（shop MORM決済 burn50）実装済＝最初の接続点。
- ブートストラップ補填は Phase4 のプール確定時にトレジャリー→`bs_pool` を上限チェック付きで実行。
- 適法性(D-2)にも有利: 「賞金はエコシステム活動から拠出・無料エントリー維持」と説明できる。

**代替（将来検討）**: ブートストラップをA（トレジャリー放出）でなくB（NODE販売収益でMORMを消費的に市場調達→`bs_pool`）にすると初期に買い圧を生む。ただし相場操縦の外見に注意・運用重・ローンチ期限定。

### D-2 ★適法性の建て付け（法務ゲート）
- **無料エントリーの懸賞** vs **富くじ/賭博**の分岐。チケットが Mad Hatter で**購入可能**になった時点で「対価を払って当たりの権利を得る」構造になり、賭博罪/富くじ（刑法185–187）・景表法・資金決済法のリスクが上がる。
- 「当選確率が再生数に比例」＝確率そのものが売買対象＝**金融/賭博性のある権利の二次市場**と評価されうる。
- メモリ`reference_morm_sales_pricing_schedule`が既に MLM/出資法/金商法の留意を記録済。ここに**賭博/富くじ/景表法/資金決済法**を追加して**弁護士レビューを必須ゲート**にする。
- 実装は「無料エントリー経路を常に残す（no-purchase-necessary）」「賞金は運営が拠出、参加費ゼロ」を満たす設計にすると懸賞寄りに倒せる。**この方針もD-1と連動して要判断。**
- ※私は弁護士ではない。ここは要件整理であって法的助言ではない。

### D-3 チケットの実体（オンチェーン vs オフチェーンDB）
- **案i オフチェーンDB**（node-dashboard Turso）: 実装最速。`weekly_snapshots`と同じ台帳文化。Mad Hatterのエスクローは運営custody。→ **推奨（Phase1で採用）**
- 案ii オンL1トークン化: 監査性・自己主権は上がるがL1にNFT/チケット種別の新TxKind実装が必要（`morm-l1`は不可侵扱い＝重い）。将来の移行先。

### D-4 乱数の公正性（VRF/コミットリビール）
L1にVRF・乱数ビーコンは無い。抽選の当選者選定は**新規に建てる**。案:
- コミット・リビール（開催前にseedハッシュを公開→開催後にseed公開→誰でも再計算）＝**外部依存ゼロで最速・推奨**。
- drand等の公開ビーコン参照＝第三者検証性は最高だが外部依存。
- 監査ログ（入力=確定再生数スナップショット＋seed、出力=当選券）を公開し、**誰でも再現できる**ことを必須要件にする。

### D-5 再生数→確率の重み付け（farm耐性）
- 生の`content.views`をそのまま確率にすると**view-farm→当選確率**の直接攻撃になる（handoffのview-farm対策と同じ論点）。
- PLAYの**署名付きwatch**（sybil耐性）／`point_ledger`のΣP（honest-engagement）を重みに使い、生viewsは参考値に留める。重み関数 `w = f(honest_views)`（対数圧縮・上限キャップ）をD-1のプール規模と合わせて設計。

### D-6 ★アイデンティティ・バインディング（node ↔ agent(m0r) ↔ owner）— Phase 1 の前提
**現状（コード確認済）**: 「エージェント」に固有種別は無く、実体は**自分に着金する独立m0r署名者**。Agent Lane（`/api/lane/*`）で署名→`REGISTER_CONTENT`→`/api/lane/earn`（treasury kind6が**自分のm0rへ**）。台帳は`lane_content.creator=m0r`・`lane_earn.addr=m0r`、PLAYは`content.uploader=m0r`。**node_id もオーナーも紐付いていない**。node-dashboardの`nodes`(node_id/`morm_address`/wallet)はnode→受取アドレスを持つが「そのnodeのエージェントはどのm0rか」は無い。新規`wallet/link-evm`は m0r↔EVM(0x) を結ぶだけ（node/owner無関係）。

**Bandersnatchが要求する未実装バインディング**:
- **node ↔ agent(m0r)**: 「1 node=週1チケット」「確率∝そのnodeのエージェント再生数」に必須。
- **agent(m0r) ↔ owner受取アドレス**: 「配当は発行元エージェントの**オーナー**へ」に必須。現状はエージェントが自分に着金するだけ。
- **エージェント限定投稿ゲート**: 「投稿はエージェントのみ・人間は視聴/いいね/シェア」。現状PLAY投稿は任意m0rで可能＝ゲート無し。

**決定事項（要確定）**:
- 配当先を **agent m0r＝オーナー受取と同一**（オーナーが自分の鍵でエージェント運用）にするか、**別々**（node→agent→`nodes.morm_address`で受取解決）にするか。→ 既存資産的には後者（`nodes.morm_address`受取）が素直・**推奨**。
- バインディングの登録方法: node-dashboard（オーナーはMCアカウントでログイン）で node に agent(m0r) を登録する署名フロー（m0r ed25519 proof）。`link-evm`の署名proofパターンを流用可能。
- **→ Phase 1 でこの三点バインディングを最初に建てる（チケット発行の前提）。**

---

## 既存レール（再利用する本番資産）

| 用途 | 既存資産 | 場所 |
|---|---|---|
| MORM支払い（当選金・配当） | `l1_transfer()` / `cli.py submit transfer`（treasury kind-6 TRANSFER、発行でなく移転） | `morm-l1/morm_l1/cli.py`, play_server |
| 支払いキュー＋冪等決済 | `morm_payouts`(status=pending)→confirm-by-nonce ワーカー | `node-dashboard/scripts/morm-payout.py`（hpmini常駐） |
| 再生数・honestシグナル | `content.views`/`likes`・署名watch・`point_ledger` | `morm-play/play_catalog.db`, `play_server.py` |
| 比例分配エンジン | `_settle_proportional()`・epoch台帳`point_settle_runs` | `play_server.py` |
| NODE→オーナー→アドレス | `nodes.morm_address` / `wallets.address` / `weekly_snapshots` | `node-dashboard/db/schema.sql`（Turso） |
| 発行上限ガード | `issuanceAllowed()` / `MORM_DAILY_ISSUANCE_CAP` | `morm-dashboard/app/lib/issuance.js` |
| 冪等性の作法 | reservation-first＋`_payout_lock`/`_l1_lock`、`test_settle_idempotency.py` | `morm-play/` |
| 新HTTP公開 | nginx vhost→cloudflared ingress→proxied CNAME `X.morm.one` | `morm-market/DEPLOY.md` |

---

## フェーズ計画

### Phase 1 — データモデル & チケット週次発行
- **前提タスク（D-6・チケット発行より先）: node↔agent(m0r)↔owner バインディング**
  - `bs_node_agent(node_id PK REFERENCES nodes, agent_m0r, owner_payout_addr, linked_sig, linked_at)` — オーナーがnode-dashboardログイン下で自nodeにエージェントm0rを署名登録（`link-evm`のed25519 proofパターン流用）。`owner_payout_addr`は`nodes.morm_address`に解決（推奨）。
  - **エージェント限定投稿ゲート**: PLAY投稿(またはlane publish)を「`bs_node_agent`に登録済みm0rのみ」に制限。人間m0rは視聴/いいね/シェアのみ。
  - これが無いと確率(∝nodeのagent再生数)も配当(発行元owner)も解決不能。
- **新テーブル**（node-dashboard Turso, D-3案iを採用）:
  - `bs_tickets(ticket_id PK, week_epoch, issuing_node_id, issuing_agent, original_owner_addr, current_owner_addr, status[active|listed|entered|void], created_at)`
  - `bs_draws(week_epoch PK, state[open|frozen|drawn|settled], seed_commit, seed_reveal, snapshot_at, drawn_at, inflow_morm, bootstrap_morm, payout_morm, reserve_before, reserve_after, carryover_next)` — 目標駆動組成の各項を記録（`payout_morm`が85/10/5分配の対象）。`reserve_after`が翌週の`reserve_before`。
  - `bs_snapshots(week_epoch, ticket_id, issuing_agent, honest_views, weight)` — 15分前確定値
  - `bs_winners(week_epoch, ticket_id, rank, prize_morm, dividend_morm, owner_addr, issuer_owner_addr, payout_status)`
  - `bs_pool_ledger(id PK, week_epoch, source[burn_redirect|madhatter_fee|ops_carryover|bootstrap], amount_morm, ref, created_at)` — プール蓄積の入金明細（D-1ブレンド原資の監査台帳）。プール残高は `bs_pool` m0r口座（トレジャリー管理）。
- **burn振替フック（D-1主原資）**: 既存burn実装箇所で `BS_BURN_REDIRECT_FRAC` 分を焼却→`bs_pool`口座へTRANSFERに分岐し、`bs_pool_ledger`にsource=burn_redirectで記帳。エンジン①（shop MORM決済 burn50）が最初の接続点。
- **週次発行ジョブ**: 各`nodes`行に対し当該週1枚（`weekly_snapshots`の週次前例に倣う）。cadence= hpmini cron or Vercel cron。`issuing_agent`＝そのNODEのPLAY投稿主（m0r）に紐付け。
- **紐付け**: ticket↔issuing_agent↔`content.uploader`。転売しても`issuing_*`は不変（Mad Hatterの「発行元紐付き」要件）。
- 完了条件: 毎週チケットが全ノードぶん生成され、UIで自分の保有チケットが見える。

### Phase 2 — 再生数スナップショット & 確率エンジン
- 開催**15分前**に`play_catalog.db`からissuing_agentごとの再生数を読み、**honest_views**（署名watch/point_ledger加味・D-5）を計算して`bs_snapshots`にfreeze。以後その週は不変。
- 重み `weight = f(honest_views)`（対数圧縮＋上限キャップ、係数はD-1のプール規模と連動）。
- チケット確率 = そのチケットのweight / Σweight。転売券は発行元agentのweightを引き継ぐ。
- 完了条件: 任意週で「確定スナップショット→各券の確率」が再現可能に出せる。

### Phase 3 — 抽選エンジン + 公正性（D-4）
- コミット・リビール: freeze時に`seed_commit=H(seed)`公開→開催時に`seed_reveal`公開。
- 重み付き**非復元**抽出で当選券9枚を選定: 1等×1(50%) / 2等×3(各10%) / 3等×5(各1%)。同一券の重複当選なし。
- **監査ログ**を公開: 入力(`bs_snapshots`全体＋seed)→出力(`bs_winners`)。第三者が同じアルゴリズムで再計算して一致検証できる形式（JSON＋擬似コード）。
- 完了条件: seed公開後、外部が当選を独立再現できる。

### Phase 4 — 配当 & 決済（既存ワーカーに載せる）
- **プール確定（D-1リザーブ入り目標駆動）**: `inflow=burn_redirect+madhatter_ops_carryover`。`payout`は目標`BS_POOL_TARGET`をリザーブ→bootstrap順で充当（bootstrapは`inflow`も`reserve`も不足時のみ・上限`BS_BOOTSTRAP_WEEKLY_CAP`）。好調週の余剰は`reserve`へ（上限`BS_RESERVE_CAP`）。全項を`bs_draws`に、入金明細を`bs_pool_ledger`に記帳。リザーブ残高は`bs_pool`口座で保持（＝時間軸の循環・暴落スパイラル吸収）。
- 確定`payout`を配分:
  - 賞金85% → 各当選券の`current_owner_addr`（1等50%/2等10%×3/3等1%×5）
  - 発行エージェント配当10% → 各当選券の`issuing_node_id`→オーナーアドレス（`nodes.morm_address`）へ**当選金額に比例**。ただし**単一発行元の取り分は`BS_DIVIDEND_ISSUER_CAP`（配当の20%）で上限**（富の集中#2抑制）。超過分はreserveへ戻す。
  - 運営5% → 運営アカウント（一部を`carryover_next`へ）
- **決済レール**: `bs_winners`の各行を`morm_payouts`(pending)へ挿入 → **既存hpminiワーカーがconfirm-by-nonceで着地**（新規決済コードを書かない）。
- **冪等性**: 週epochごとに1回settle（`settle_points`の「epoch内再実行スキップ」と同型）。reservation-first。二重払い防止に`_l1_lock`相当のロック。
- ★**チェーン分離の罠に注意**: `reference_node_reward_chain_split`＝払出しはhpmini着地・morm.oneは主L1を読む別台帳問題。Bandersnatch配当も**主L1(l1.morm.one)へ着地**するようワーカーのRPC/口座を統一すること（NODE_PAYOUT口座方針を踏襲）。
- 完了条件: テスト週で85/10/5が正しいアドレスに着地し、再settleしても二重払いしない（idempotencyテスト追加）。

### Phase 5 — MORM Mad Hatter（チケット二次流通）
- 出品/購入: `bs_tickets.status`=listed、`price`（出品者の言い値）、購入で`current_owner_addr`更新（`issuing_*`は不変）。
- **運営手数料1%**。
- **エスクロー/決済方式**（D-1/D-3と連動・要判断）: MORMでのオンL1エスクロー（買い手→エスクロー→売り手、1%控除）が本命。custodyモデル・返金経路・出品取消しを定義。
- 抽選確定(freeze)後は出品ロック（開催直前の投機防止）。
- 完了条件: A出品→B購入→Bの券で参加→当選でBに賞金・発行元Aに配当、が通しで動く（概念FIG.2の再現）。

### Phase 6 — フロント & 公開
- 公開概要ページ（pilot）はマーケ用。機能UIを新設:
  - `bandersnatch.morm.one`（新規サービス）or market配下に: ①今週の抽選/確率 ②My Tickets ③Mad Hatter出品ボード ④過去結果＋監査ログ。
  - まず`docs/morm-bandersnatch-overview.html`（=pilotのHTML）をリポジトリに取り込み、参照リンクを実在させる（08-bandersnatch.mdの参照先が現状ローカル欠落）。
- 公開: nginx vhost→cloudflared→proxied CNAME（morm.oneゾーン・**ユーザー承認ゲート**）。
- 完了条件: 実UIで週次サイクルが人間の目で回せる。

### Phase 7 — 監査 & ローンチ
- セキュリティ並列レビュー（前回2波方式）: 二重払い・view farm→確率・抽選操作・エスクロー抜き取り・treasury drain上限。
- 法務サイン（D-2）。
- テストネットで数週dry-run（発行→freeze→draw→settle→resale）。
- ローンチ判定。

---

## 横断的リスク & 対策
- **view-farm→当選確率**: 生views直結を禁止、署名watch/ΣPで重み付け＋上限キャップ（D-5）。
- **抽選操作**: コミットリビール＋公開監査ログ、seedは運営が事前コミット（D-4）。
- **二重払い/nonce衝突**: 既存reservation-first＋confirm-by-nonceワーカーを再利用、週epoch単一settle。
- **treasury drain**: bootstrapを週次ハードキャップ(`BS_BOOTSTRAP_WEEKLY_CAP`)、`MORM_DAILY_ISSUANCE_CAP`思想を適用。リザーブ成長で自動サンセット。
- **暴落スパイラル/賞金ボラティリティ**: リザーブで平滑化（好調週余剰→不調週）。目標駆動でパススルーの負のフライホイールを回避（D-1循環性分析）。
- **富の集中**: 発行元配当に単一発行元キャップ、確率重みは対数圧縮＋上限（D-5）。
- **チェーン分離**: 配当着地を主L1に統一（Phase4）。
- **投機の暴走**: freeze後の出品ロック、Mad Hatterの1%手数料。
- **法規制**: 無料エントリー経路の常設・弁護士ゲート（D-2）。

## 依存関係（ざっくり順序）
D-1〜D-5（意思決定） → P1 → P2 → P3 → P4 →（P5はP1完了後に並行可）→ P6 → P7。
決済(P4)は既存ワーカー再利用のため実装は薄い。重いのは **P3抽選公正性・P5エスクロー・P1発行ジョブ**。最大の非技術ブロッカーは **D-1原資** と **D-2法務**。

## 未解決オープンクエスチョン（要ユーザー回答）
1. ~~**D-1 賞金プールの原資**~~ → **【決定済】ブレンド型＋リザーブ入り目標駆動**（burn振替0.20主＋Mad Hatter/運営自己資金＋トレジャリーbootstrapは不足時のみ発火・リザーブで自動サンセット）。循環性・片落ちを塞ぐリザーブ機構と初期パラメータ確定。残: `BS_POOL_TARGET`など**絶対額をドライラン2-3週で実測較正**。
2. **D-2 法務の建て付け**（無料エントリー常設で懸賞寄せ or 有料くじとして規制対応）
6. **D-6 バインディング**（配当受取をagent m0r＝ownerと同一にするか、node→`nodes.morm_address`解決の別建てにするか）＝Phase1前提
3. **D-3 チケット実体**（オフチェーンDB推奨で確定してよいか）
4. **D-5 再生数の重み**（honest_views採用・上限キャップの水準）
5. 開催曜日/時刻・第1回ローンチ目標（shopローンチ9/1〜12/25との整合）
