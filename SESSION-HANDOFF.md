# MORM セッション・ハンドオフ（2026-08-29）

**新セッションは最初にこれを読む。** 推奨 cwd = `~/Desktop/MORM/`。全体マップ=`ARCHITECTURE.md`／統合計画=`CONSOLIDATION-PLAN.md`／エアドロ=`agent-lane/DEPLOY.md`（冒頭★2026-08-29確定）。

## ★2026-08-29 現況（このセッションで到達・以降を最優先で読む）
- **push 済・origin/main と同期**（当初の「未push」は解消。以後の全変更も push 済）。
- **Agent Lane 全フェーズ本番活性化 完了**: fund(PLAY/DASH=各100000 MORM)→Play を PLAY_PAYOUT に分離→Phase C バルブ(BRIDGE_VALVE=on)→DASH 配線→F(AD)→B(lane earn)→D(engagement=proportional B_EPOCH_MORM=5000)→VIEW_EARN=on。Phase E(node emission)は退役(410でハード無効化)。
- **並列レビュー(2波)でセキュリティ監査→CRIT2/HIGH3/MED多数を修正・本番反映**。記録=`REVIEW-FINDINGS-2026-08-29.md`。
  - CRIT: **本番 ADMIN_TOKEN が公開リポにコミット済＝生 token 漏洩→ローテ済**（旧 token は play で 403）。proportional 発行の予算超過→修正。
  - HIGH: view-farm→drain／システム発行上限(既定10000 MORM/24h・env `MORM_DAILY_ISSUANCE_CAP`)／payout-refill 無限ループ。
  - MED: valve fail-closed／emit-nodes 410／lane 予約解放／AGE_SECRET 独立化／未承認メタ隠蔽／CLI env-seed。
- **★重大な運用トラップ発見**: `launchctl kickstart -k` は **plist の env を再読込しない**。plist env 変更は **`bootout`+`bootstrap` 必須**（罠セクション参照）。今回の Play env 全変更は当初 kickstart で未反映→bootout で反映確定。
- **hpmini mod-worker は sudo 不要でローテ**: `mod_worker.py` が `~/.morm-worker-token` を env より優先読込→ファイル書込み＋自プロセス kill(Restart=always)で反映(手順=`SECURITY-SECRET-ROTATION.md`§0-2)。
- ✅**market.morm.one LIVE(2026-08-29)**: CF morm.one に proxied CNAME market→f60ef43f-…cfargotunnel.com 作成→https://market.morm.one/ 200 確認。設計系 findings=payout CAS 実装済・他2件は据置(ユーザー判断・`REVIEW-FINDINGS`に移行計画)。
- **残(未対応)**: C-2 minExit=1e18 再デプロイ(`morm-chain/redeploy-minexit.sh` ワンコマンド・broadcast=deployer鍵)→その後 C-1 export_relayer 起動(新bridgeへ・`agent-lane/ops/relayer-deploy.md`)。※誤作成の `market.morm.one.ctai.online`(ctai.oneゾーン)は無害だが掃除推奨。

## 一行サマリ（初期・履歴）
MORM 4サーフェス（www/api/node/play.morm.one）を監査→致命セキュリティ封鎖・デプロイ済／node.morm.one を earned報酬に統一／リポ整理 Phase 1-3 完了。

## 稼働URL・ログイン（詳細=ARCHITECTURE.md）
- www.morm.one=`site/account.html`（walletless m0r）。api.morm.one=`morm-dashboard/`（ウォレットAPI＋Agent Lane API。旧0x UIは廃止済、`/`→node.morm.oneへ307）。node.morm.one=**`node-cluster/src/node-dashboard/`**（MCアカウント+PW）。play.morm.one=`morm-play/play_server.py`（Mac Mini）。L1=`morm-l1/` Mac Mini :8900（**不可侵**）。
- **admin PW: api.morm.one=`Yachida0024`（設定済）**。node.morm.one=別の既設PW（1234不可）。play=`ADMIN_TOKEN`。

## ★重要な罠
- **★launchd の env 変更は `kickstart -k` では反映されない**（EnvironmentVariables はロード時のみ読込）。plist の env を変えたら **`launchctl bootout gui/501/<label>` → `launchctl bootstrap gui/501 <plist>`** で再読込必須。code(play_server.py 等)ファイル変更は都度読込 or kickstart で反映されるが、**env(ADMIN_TOKEN/TREASURY_SEED_FILE/EMISSION_MODE/VIEW_EARN 等)は bootout+bootstrap**。※2026-08-29: 今セッションの play env 変更(payout分離/proportional/VIEW_EARN/token ローテ)は当初 kickstart で未反映→bootout+bootstrap で反映確定。
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
- ✅**[解決 2026-08-29]** `morm-aiservice/service-key.json`: 本番 Mac Mini L1(`ts-mini`:8900・head_height=23実チェーン)の `/ai-services` = `{"services":[]}` → 漏洩pubkey `b88942..f291` は**本番未登録＝実権限なし＝L1ローテ/失効 不要**。PoC鍵再生成は任意(ファイル既に不在・.gitignore済)。**Task B クローズ**。

### C. 残セキュリティ（コード済/未・要ホスト反映）
- ✅**[コード完了 commit bfc9309]** play_server.py 4 settle経路(settle_referrals/_settle_fixed/_settle_proportional/settle_challenge)を予約先行に統一(=`_points_loop`経由の自動配当も網羅)。回帰テスト`morm-play/test_settle_idempotency.py`で二重支払いゼロ/失敗ロールバック/2レッグ端ケース検証(28 assert PASS・実チェーン不要)。※`payout()`は既済。
  - ✅**[本番デプロイ完了 2026-08-29]** Mac Mini(`ts-mini`)へ反映済。**発見**: 本番は Aug15版でリポHEADより350行古く、Task C以外に payout()予約先行修正/proportional emission/view_by_other も未反映だった→ユーザー承認のうえ**リポHEADへ前方同期**(③④はenv既定off/fixed=既定挙動不変)。手順: `/Users/user/morm-play/play_server.py`(WorkingDir同・`/usr/bin/python3`・plist `com.morm.play`・uid 501・DB=`play_catalog.db`)を backup(`play_server.py.bak-20260829-130213`)→scp(sha一致)→remote py_compile→`launchctl kickstart -k gui/501/com.morm.play`→_init_db冪等migration。検証: localhost+外部 play.morm.one で `/api/me`=400・`/api/mine`=400・feed=200・admin無token=403、play.err は Aug15以降未書込=新規エラーゼロ。ロールバック=backupを戻して再kickstart。
- **export_relayer.py**（修正済: last_block永続化+dust ALERT）→ **リレーヤ運用ホストへ反映**。★調査(2026-08-29): 未本番化(デプロイ痕跡なし)。✅**[C-1 準備完了]** runbook=`agent-lane/ops/relayer-deploy.md`(ホスト推奨=Mac Mini・web3 7.16.0/eth_account 導入確認済・コードを `/Users/user/morm-relayer/export_relayer.py` に配置+remote py_compile OK)。**残(ユーザー)**: env の鍵配置(`SIGNER_PKS`/`SUBMITTER_PK`/`TREASURY_SEED_HEX`/`TREASURY_SIGNER_SEEDS`)＋launchd 起動＝ブリッジ発行権限のため。C-2 後に新 BRIDGE_ADDR で起動が無駄なし。CHAIN_ID=84532(Base Sepolia)。
- **contract MIN_EXIT ★フルスタック再デプロイ要（testnet・非緊急）**: 稼働中 MORMExportBridge `0xf7a4c27a…db10a818`(Base Sepolia)の `minExit=0` を確認。`minExit` は **immutable**＝変更不可。さらに既存 WMORM `0x5cd8053c…` の `setBridge` は **one-shot**(`bridge!=0`でrevert)＝旧bridgeに恒久バインド・再ポイント不可 → **新WMORM＋新bridgeのフルスタック再デプロイが必須**(既存プール切離し)。
  - ✅**コード変更不要**: `DeployExportBridge.s.sol` は `c.minExit = vm.envOr("MIN_EXIT", 0)` ＝**env `MIN_EXIT` で設定可**。修正=`MIN_EXIT=1000000000000000000`(1e18) を設定して再デプロイするだけ(deployer鍵＝ユーザー実行・`forge script ... --broadcast`)。
  - **移行**: 新 BRIDGE_ADDR/WMORM を relayer env・`.testnet-deploy.env`・`morm-market/app.html`(app.htmlのcontract定数) に反映、Base Sepolia の wMORM/USDC プール再作成。
  - ✅**[C-2 準備完了]** runbook=`morm-chain/REDEPLOY-MINEXIT.md`(turnkey・現行bridgeにパラメータ整合: WINDOW_LEN3600/MAX_MINT1e24/MAX_SUPPLY1e26/THRESHOLD2/GUARDIAN0x9eb4…+`MIN_EXIT=1e18`・forge build確認済)。**残(ユーザー)**: `forge script … --broadcast`(deployer鍵)＋移行(BRIDGE/WMORM/USDC 全参照差替・pool再作成)。
  - **非緊急**: testnet(実資金なし)＋relayer の dust ALERT で緩和済。context: threshold=2・paused=false・maxMintPerWindow=1e24。
- ✅**[コード完了 commit 51e16de]** play 読み取り経路: (1)IDOR封鎖=/api/earnings・/api/mine を pubkey要求化(生の公開アドレスm0r不可・`pub_to_m0r`で32byte厳格検証)、/api/me も統一。 (2)ADMIN_TOKEN in URL→`X-Admin-Token`ヘッダ化(admin GET 3経路＋呼出元 mod_worker/recaption/ADMIN_MOD_HTML)。 (3)mod preview 404復活=admin(ヘッダ)のみ pending/R18 を審査配信・公開は404据置。 (4)age.verify=署名必須・18-120・HttpOnly cookie で問題なし(自己申告は KYC未導入の設計上既知制約)。実サーバ+curlで全確認・settle回帰PASS。 ※feed/content は公開データ(m0rアドレスのみ・pub非露出)で IDOR非該当。
  - **残(gated=要承認)**: 上記も play_server.py の一部 → **C冒頭の Mac Mini 転送＋kickstart** に同梱でデプロイ。

### D. Phase 2 残（★監査完了＋方針決定 2026-08-29）
- **admin 陳腐化整理 → 【決定=全保持・作業なし】**: 監査で安全な削除対象なしを確認。全11ページ稼働(dbAll直参照 or 生きた/api or 静的)・retire済API(`/api/my/*`等)への壊れ参照ゼロ(Phase2 retireは既にクリーン)・孤立なし。`scores`(node-emission)は Agent Lane と共有のため削除不可。ユーザー判断=全保持。ARCHITECTUREの「陳腐化」表記も訂正済。
- **morm-market → 【Mac Mini側デプロイ完了・DNS のみ残 2026-08-29】**: 自己参照を相対リンク化(commit 4222502)→scp `/Users/user/zoku-sites/morm-market/`(sha一致)→nginx vhost `/opt/homebrew/etc/nginx/servers/morm-market.conf`(listen8080・server_name market.morm.one・root同dir、morm-apex.conf に倣う)→`nginx -t`OK→reload。cloudflared `/Users/user/.cloudflared/config.yml` に `market.morm.one→http://localhost:8080` ingress 追加(catch-all直前)→validate OK→kickstart(一時530→即回復)。nginx は `curl -H "Host: market.morm.one" localhost:8080/` で 200 配信確認済。
  - **残(gated=要ユーザーの morm.one CFアカウント)**: **market.morm.one の DNS レコード作成**。morm.one ゾーンに **proxied CNAME `market.morm.one` → `f60ef43f-8ba5-45ee-946f-1c1f673df231.cfargotunnel.com`**(www/play と同方式)。※`cloudflared tunnel route dns` は tunnel既定ゾーン ctai.online に付くため不可(誤って `market.morm.one.ctai.online` を作成済→ユーザーが ctai.online ゾーンで削除推奨)。DNS 伝播後 https://market.morm.one/ が live。

### E. Agent Lane 活性化（`agent-lane/DEPLOY.md` 冒頭★の順）★ready-state検証済 2026-08-29
**✅ 準備完了(確認済)**: Phase A コード live(api.morm.one `/api/lane/skill|feed`=200・Vercel)／play settle修正 live(本日デプロイ・Phase D前提クリア)／verify 9/9／`ADMIN_PASSWORD`=Yachida0024／**treasury `m0rzjtz…ctbc` balance≈1e18・nonce20**／payout口座 balance=0(未fund)。
**進捗(2026-08-29 実行)**:
- ✅**E-1** PLAY_PAYOUT seed を Mac Mini `~/.morm-agentlane/play_payout.seed`(0600) に配置・導出アドレス一致で検証。
- ✅**E-2 fund 完了(ユーザー実行)**: treasury→PLAY 100000・DASH 100000 着金。treasury 残 ≈1e18-2e5・nonce22。
- ✅**E-3 Play 分離完了**: `com.morm.play.plist` に `TREASURY_SEED_FILE=/Users/user/.morm-agentlane/play_payout.seed` 追加→再起動(PID更新・health OK・エラーなし)。Play settle は今後 PLAY_PAYOUT の独立 nonce で支払い＝跨ぎ衝突解消。plist backup=`com.morm.play.plist.bak-20260829-134924`。

**残(api.morm.one=Vercel の段階ロールアウト・各段ユーザー承認/検証)**:
- **E-4 DASH 配線(秘密更新＝ユーザー実行)**: Vercel morm-dashboard の `MORM_TREASURY_SEED`(現在22日前の旧値)を **dash_payout.seed** に、`MORM_TREASURY_ADDRESS` を `m0roshqbpskljwuj3drophhb7tth33qprzn` に更新→再デプロイ。※F/B の前に必須。
- ✅**Phase C(換金バルブ) LIVE 2026-08-29**: `BRIDGE_VALVE=on` を Vercel production に設定→`vercel --prod`(deploy `pdy8vk0kg`・api.morm.one alias)→回帰なし(price/lane 200)。保護=system≤0.5%/日・acct≤$50/日・cooldown24h(他ノブは既定)。ロールバック=`BRIDGE_VALVE` unset+redeploy。
- ✅**E-4 DASH 配線完了 2026-08-29**: ユーザーが `MORM_TREASURY_SEED`→dash_payout・`MORM_TREASURY_ADDRESS`→`m0rosh…` を更新(seed導出=DASH一致を検証)→`vercel --prod`(deploy `elkqashi5`)→回帰なし・l1.morm.one 200(dashboard の L1 到達確認)。dashboard は DASH_PAYOUT(100000) から faucet/lane/AD を支払う。
- ✅**Phase F(AD) ready**: 専用フラグ無し=`ADMIN_PASSWORD`(設定済)で admin-gated。no-auth→401(fail-closed)確認。発行外の再分配。
- ✅**Phase B(lane earn) active**: `MORM_LANE_EARN`既定1・`MORM_LANE_EARN_DAILY_CAP`既定10。未署名→400"invalid m0r addr"(署名必須・開放なし)。DASH から支払い。
- ✅**Phase D(engagement proportional) LIVE 2026-08-29**: Play plist に `EMISSION_MODE=proportional`+`B_EPOCH_MORM=5000`(72h)+`EPOCH_ACCT_CAP_FRAC=0.005` 追加→再起動(PID更新・health OK・エラーなし)。engagement settle は総発行B頭打ちの proportional に(PLAY_PAYOUTから・base=1)。plist backup=`com.morm.play.plist.bak-D`。ロールバック=`EMISSION_MODE`をfixedに戻す/削除→再起動。`VIEW_EARN` は署名付きwatchクライアント改修後(未改修は安全に無報酬)。
- ✅**VIEW_EARN LIVE 2026-08-29**: 本番 index.html は Aug12版(署名beaconなし)だった→HEAD同期(署名watch beacon込・都度読込で即live・backup=index.html.bak-*)＋Play plist `VIEW_EARN=on`(再起動・health OK・backup=.bak-VIEW)。署名付き視聴→検証→クリエイターへ視聴ポイント(PT_VIEW=1・proportional配分・PLAY_PAYOUTから)。ロールバック=`VIEW_EARN`削除→再起動。
- ✅**Agent Lane 活性化 完了**: fund→Play分離→C(valve)→DASH→F(AD)→B(lane)→D(engagement)→VIEW_EARN 全て稼働。**Phase E(node emission)は廃止(不活性のまま)**。残(任意/運用): 明示的な lane/日次上限の調整・payout口座の残高監視/補充。
- 詳細=`agent-lane/DEPLOY.md` 冒頭★。base=1(整数MORM)で初回・§G(1e6)は後日。

## 必要アクセス（新セッションで request）
- `~/Desktop/node-cluster/src/node-dashboard`（node.morm.one 編集/デプロイ）
- SSH: Mac Mini（play/L1・fund・plist）／リレーヤ運用ホスト（export_relayer）。CLAUDE.md/メモリにSSH情報。

## メモリ参照
`reference_morm_security_audit_2026-08`／`project-morm-dashboard-login-rewards`／`reference_agent_lane_session_handoff`（別プロジェクトmemory・冒頭に★2026-08-29上書き済）。
