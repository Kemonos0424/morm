# MORM セッション・ハンドオフ（2026-08-29）

**新セッションは最初にこれを読む。** 推奨 cwd = `~/Desktop/MORM/`。全体マップ=`ARCHITECTURE.md`／統合計画=`CONSOLIDATION-PLAN.md`／エアドロ=`agent-lane/DEPLOY.md`（冒頭★2026-08-29確定）。

## 一行サマリ
MORM 4サーフェス（www/api/node/play.morm.one）を監査→**致命セキュリティ封鎖・デプロイ済**／node.morm.one を**earned報酬(稼働+利用)に統一・デプロイ済**／リポ整理 Phase 1-3 完了（ARCHITECTURE・archive・論理コミット・旧0xダッシュ廃止・node-dashboard を submodule で1入口化）。**全てローカルcommit・MORM本体は未push**。残りをこのハンドオフの「残タスク」で片付ける。

## 稼働URL・ログイン（詳細=ARCHITECTURE.md）
- www.morm.one=`site/account.html`（walletless m0r）。api.morm.one=`morm-dashboard/`（ウォレットAPI＋Agent Lane API。旧0x UIは廃止済、`/`→node.morm.oneへ307）。node.morm.one=**`node-cluster/src/node-dashboard/`**（MCアカウント+PW）。play.morm.one=`morm-play/play_server.py`（Mac Mini）。L1=`morm-l1/` Mac Mini :8900（**不可侵**）。
- **admin PW: api.morm.one=`Yachida0024`（設定済）**。node.morm.one=別の既設PW（1234不可）。play=`ADMIN_TOKEN`。

## ★重要な罠
- **node.morm.one のデプロイ/実行実体は `~/Desktop/node-cluster/src/node-dashboard`**（`.env.local`/`.vercel`保持）。`MORM/node-dashboard` は submodule=参照専用（ここを編集してもデプロイされない）。編集/デプロイは node-cluster 側で。→ 新セッションで `request_directory ~/Desktop/node-cluster/src/node-dashboard`。
- Vercel デプロイ(`vercel --prod --yes`)は権限ガードで最初ブロック→ユーザー承認で通る。各 dir の `.vercel/project.json` がプロジェクトを決める（node-dashboard / morm-dashboard）。
- **secret厳守**: `.guardian-keys.env`/`.testnet-*.env`/`*.env`/plists/`service-key.json` は .gitignore 済。`git add .` 禁止・パス指定で add。
- 本番 L1 `127.0.0.1:8900` 書込みは fund-payouts 等の所定手順のみ。

## 完了済み（この一連）
- セキュリティ本番反映: **api.morm.one `/api/admin/send` 無認証treasury drain封鎖**・admin`1234`撤廃(→`Yachida0024`)／node.morm.one morm-distribute認証・heartbeat安全化・見込み30倍修正・ops earned化・payout二重防止。旧`/my`IDOR削除。
- node.morm.one: earned報酬(`app/lib/reward.js`)一本化・shop報酬レート表示一致・特商法実値化・ログイン堅牢化（30日期限/ロックアウト/列保証）。デプロイ済。
- account.html: 監査済（本番L1接続・faucet実払い確認）。
- リポ整理: `ARCHITECTURE.md`・`CONSOLIDATION-PLAN.md`・`_archive/`・`poc/`・論理コミット・両repo main マージ・node-dashboard submodule。
- Agent Lane: verify 9/9 PASS・統合モデル確定（node据置・⑤退役・3トラック追加）・payout口座(PLAY/DASH)検証（未付与・アドレス一致）。

## 残タスク（このセッションで全部片付ける）
### A. push ✅【完了 2026-08-29】
- `git push origin main` 実施済（origin/main=`436fc4b`・ahead 0 同期確認済）。settle/IDOR/token/mod-preview/dev-seed除去/監査 全反映。
- ✅**[pre-push secret scan 済 2026-08-29]** 未push差分(origin/main..HEAD)に**新規の実secretなし**＝push安全。検出64-hexは全て公開物: RFC8032テストベクタ(mormcrypto自己テスト)・ed25519曲線定数・オンチェーンpool/token識別子・**Anvil既定acct#0 privkey `0xac0974..ff80`**(local anvil専用・morm-chain/script・poc・forge-std=周知の公開テスト定数で無害)。むしろ本pushで launch.json dev seed 除去(da4e1f8)が origin に反映。※既存の履歴露出(service-key/旧dev seed)は別件=[[Task B]]で対応中。

### B. secret ローテ（★既に PUBLIC 露出＝要ローテ判断。詳細=`SECURITY-SECRET-ROTATION.md`）
- **重大**: リポは PUBLIC・`f82ea6e` は origin/main に push 済 → 両seedは既に GitHub 公開済み（恒久 compromised）。履歴rewriteは公開後は無効＝ローテ＋失効が唯一策。
- ✅**[ローカル除去済 commit da4e1f8]** `.claude/launch.json` の `--treasury-seed` → anvil(31337)/dev専用・本番権限ゼロ・参照先archived(死設定)と確認。placeholder化で除去。本番 seed は `~/.morm-l1/producer.seed`（リポ外）で分離＝実害なし・ローテ不要。
- **残(要判断/gated)** `morm-aiservice/service-key.json`（AIサービス attestation署名鍵・PoC・.gitignore済だが f82ea6e に seed 平文）: 旧pubkeyが**本番L1のパブリッシャ登録を持つか確認**→持てば L1 で失効＋新鍵生成/登録（`aiservice.py keygen`）。持たなければ実害低。

### C. 残セキュリティ（コード済/未・要ホスト反映）
- ✅**[コード完了 commit bfc9309]** play_server.py 4 settle経路(settle_referrals/_settle_fixed/_settle_proportional/settle_challenge)を予約先行に統一(=`_points_loop`経由の自動配当も網羅)。回帰テスト`morm-play/test_settle_idempotency.py`で二重支払いゼロ/失敗ロールバック/2レッグ端ケース検証(28 assert PASS・実チェーン不要)。※`payout()`は既済。
  - **残(gated=要承認)**: **Mac Mini へ転送＋`launchctl kickstart -k gui/$UID/com.morm.play`**。デプロイ前に既存`agent-lane/verify/run_all.sh`(9/9)の再実行推奨。
- **export_relayer.py**（修正済: last_block永続化+dust ALERT）→ **リレーヤ運用ホストへ反映**＋contractの`MIN_EXIT>=1e18`設定（1MORM未満exit永久損失の根本対策）。
- ✅**[コード完了 commit 51e16de]** play 読み取り経路: (1)IDOR封鎖=/api/earnings・/api/mine を pubkey要求化(生の公開アドレスm0r不可・`pub_to_m0r`で32byte厳格検証)、/api/me も統一。 (2)ADMIN_TOKEN in URL→`X-Admin-Token`ヘッダ化(admin GET 3経路＋呼出元 mod_worker/recaption/ADMIN_MOD_HTML)。 (3)mod preview 404復活=admin(ヘッダ)のみ pending/R18 を審査配信・公開は404据置。 (4)age.verify=署名必須・18-120・HttpOnly cookie で問題なし(自己申告は KYC未導入の設計上既知制約)。実サーバ+curlで全確認・settle回帰PASS。 ※feed/content は公開データ(m0rアドレスのみ・pub非露出)で IDOR非該当。
  - **残(gated=要承認)**: 上記も play_server.py の一部 → **C冒頭の Mac Mini 転送＋kickstart** に同梱でデプロイ。

### D. Phase 2 残（★監査完了＋方針決定 2026-08-29）
- **admin 陳腐化整理 → 【決定=全保持・作業なし】**: 監査で安全な削除対象なしを確認。全11ページ稼働(dbAll直参照 or 生きた/api or 静的)・retire済API(`/api/my/*`等)への壊れ参照ゼロ(Phase2 retireは既にクリーン)・孤立なし。`scores`(node-emission)は Agent Lane と共有のため削除不可。ユーザー判断=全保持。ARCHITECTUREの「陳腐化」表記も訂正済。
- **morm-market → 【決定=Mac Mini 静的 market.morm.one(www と同方式)】**: 手順を `morm-market/DEPLOY.md` に整備(turnkey・Mac Mini固有値は`<...>`で要確認)。中身=静的HTML2枚・**Base Sepolia testnet**(実mainnet資金なし)。デプロイ前に自己参照URL `morm-market.zoku.one`→`market.morm.one` 置換が必要(既存zoku痕跡)。**実行(SSH/nginx/CF Tunnel/DNS)=gated**。

### E. Agent Lane 活性化（`agent-lane/DEPLOY.md` 冒頭★の順）
- 前提: ①api.morm.one `ADMIN_PASSWORD`=Yachida0024（済）②**payout口座(PLAY/DASH)を fund**（`agent-lane/deploy/fund-payouts.md`・Mac Mini L1操作・base=1整数MORM）③base=1統一。
- 順序: A(不活性・既載) → C(換金バルブ) → **F(AD・発行外で安全)** → B(lane・cap必須) → D(engagement・要C[play settle修正]先行)。**Phase E(node emission)は廃止**。

## 必要アクセス（新セッションで request）
- `~/Desktop/node-cluster/src/node-dashboard`（node.morm.one 編集/デプロイ）
- SSH: Mac Mini（play/L1・fund・plist）／リレーヤ運用ホスト（export_relayer）。CLAUDE.md/メモリにSSH情報。

## メモリ参照
`reference_morm_security_audit_2026-08`／`project-morm-dashboard-login-rewards`／`reference_agent_lane_session_handoff`（別プロジェクトmemory・冒頭に★2026-08-29上書き済）。
