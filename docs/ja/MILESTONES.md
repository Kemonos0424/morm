# MORM マイルストーン（詳細版）

**Version**: 0.3 (Draft)
**Date**: 2026-04-25
**Status**: 内部計画 / 進捗追跡用

---

## 実装ステータス（2026-04-26時点）

**PoC Phase 1-27f すべて実装済み + 実機検証済み（46項目）。**
**SECURITY-DESIGN §5 must-have 全達成 = mainnet candidate 最低条件OK。**

詳細は `docs/IMPLEMENTATION-STATUS.md` 参照。主要マイルストーン:

- ✅ 3秒WebM Cell + V-Hash（PoC Phase 1/2）
- ✅ Walletless ID（PoC Phase 7/9/11b）
- ✅ Proof of Physical Evidence（PoC Phase 5/10e/16）
- ✅ Smart Contract（合計 32/32 Forge tests PASS）
- ✅ MORM L1 Testnet（PoC Phase 10a-c + 23 3-node testnet）
- ✅ 50/10 Player + P2P Mesh（PoC Phase 3/6）
- ✅ WebRTC P2P + TURN（PoC Phase 22/22b、coturn稼働中）
- ✅ Player↔Chain on-chain視聴報酬（PoC Phase 11d）
- ✅ 統一CLI `morm`（PoC Phase 22/23）
- ✅ EVM Bridge + ERC-20 + Multi-sig relayer（PoC Phase 12/13a/13b）
- ✅ AI Service Generation ID（PoC Phase 14）
- ✅ MORM Shop UX + Shamir + 実カメラ証拠（PoC Phase 15a/15b/16a）
- ✅ Multi-producer Slot + K-depth Finality + m0r-prefix（PoC Phase 17/17b/18）
- ✅ node招待UI + Testnet公開手順 + PWA（PoC Phase 19/20/21）
- ✅ **真のDAG並列性**（PoC Phase 24a-d、frontier-relative state、common-ancestor finality witness ≥⅔）
- ✅ **QUIC stream gossip**（PoC Phase 25a-c、aioquic 1.3、SPKI pin TOFU、HTTP `/gossip/*` 410化）
- ✅ **Treasury Multi-sig**（PoC Phase 26a、M-of-N）
- ✅ **Web hardening**（PoC Phase 26u/v/w/x、CSRF/CORS/`MORM_PRODUCTION=1`/key-file mode 0600）
- ✅ **Tx confirm dialog**（PoC Phase 27f、shop.js + auth-morm.js wired）

**残候補（順次対応・mainnet前推奨）**:
- §🟡 Mempool size cap (26c)、Genesis lockdown (26e)、Slither/Echidna audit (26f)、Cell SHA256 verify (26q)、Signaling rate limit (26r/s)、TURN bandwidth quota (26t)、SW max-age (26y)、DNSSEC + .morm TLD (27c)
- Phase 25-Video（HLS native）、Phase 24b throughput最適化、Phase 26a-rotation

つまり残るのは **戦略・ブランド・コミュニティ層**:
- ドメイン/ENS取得（morm.io、morm.eth等）
- コア貢献者集合（仮名OK）
- Whitepaper最終公開
- AI Agent本番化
- Founding Contributor（YACHIDA）の公開記録

これらは下記マイルストーンの「2. Pre-Launch Phase」で扱う。

---

## 0. 全体マップ

```
2026  ───────────────────────────────────────────────────────
  Q2  | MORM Phase 0 準備 | AI Agent設計、Smart Contract起草、コア貢献者集合
  Q3  | MORM Phase 0 α   | Testnet開始、AI Agent基盤デプロイ
  Q4  | MORM Phase 0 β   | Public Testnet、第三者監査、MORM Shop α
2027  ───────────────────────────────────────────────────────
  Q1  | TGE & Phase 1始動 | Mainnet、MORM Initial Airdrop、DAO移行
  Q2  | Phase 1 加速      | iOS/Android v1、Verified Creator拡大
  Q3  | Phase 1 拡張      | MORM Studio、AI Lab、東南アジア展開
  Q4  | Phase 1 完了      | 1M MAU、AI Agent全面稼働
2028  ───────────────────────────────────────────────────────
  Q1-Q4 | MORM Phase 2 (Public) | アプリストア、SDK、Bridge、グローバル
2029  ───────────────────────────────────────────────────────
  Q1-Q4 | MORM Phase 3 (Sovereign) | B2B、Spatial Video、完全自律
2030+ ───────────────────────────────────────────────────────
       | 成熟期 | 100M+ MAU、創業貢献者一参加者化
```

> ⚠️ MORMには**法人が存在しない**。すべての運営はAI Agent + Smart Contract + DAOで実行される。詳細は [AGENTS.md](AGENTS.md) 参照。

---

## 1. Phase 移行のDecision Gates

各Phaseに移行するには、すべての必須条件を満たす必要がある。

### Gate A: Pre-Launch → MORM Phase 0 α（2026 Q3移行条件）

- [ ] WhitePaper v1.0 公開（GitHub経由）
- [ ] AI Agent設計（[AGENTS.md](AGENTS.md)）公開
- [ ] Smart Contract初版の内部監査
- [ ] PoC 3点完了（3秒Cells / Walletless ID / PoPE基本）
- [ ] コア貢献者15名以上（仮名/匿名OK）
- [ ] 初期Treasury Multi-sig署名者5/7確定
- [ ] Bug Bounty Contract デプロイ準備完了

### Gate B: MORM Phase 0 → Phase 1（TGE準備）

- [ ] スマートコントラクト第三者監査（最低2社）合格
- [ ] Testnet 1,000ノード安定稼働
- [ ] Discord 50,000メンバー
- [ ] MORM Initial Airdrop ホワイトリスト確定
- [ ] DEX流動性Bootstrap準備完了
- [ ] AI Agent本番候補（5種以上）稼働確認
- [ ] Bug Bounty重大Issue 0件（30日連続）
- [ ] Adminキー全Renounce準備完了（Bridge / Multi-sig除く）

### Gate C: MORM Phase 1 → Phase 2（Public Launch準備）

- [ ] MAU 100万人達成
- [ ] 稼働ノード 10万台
- [ ] 取引詐欺率 <0.05%
- [ ] DAOガバナンス自己運営化（90日連続、最低24件の可決議案）
- [ ] AI Agent全カタログ稼働（10種以上）
- [ ] 主要法域でのオプトアウト体制完成
- [ ] PWA / アプリストア配布の両立体制
- [ ] 5言語以上のローカライズ完了（Translation Agent経由）

### Gate D: MORM Phase 2 → Phase 3

- [ ] MAU 1,000万人達成
- [ ] 稼働ノード 100万台
- [ ] DAO主要決議の完了実績 100件以上
- [ ] Bridge累計取扱高 $10億以上
- [ ] 創業貢献者の特殊権限ゼロ化（Treasury Multi-sigも交代済）

---

## 2. Pre-Launch Phase（2026年4月〜2026年9月）

**目的**: AI Agent設計・Smart Contract起草・コア貢献者集合・PoC完了。
**特徴**: **法人設立なし**、雇用契約なし、すべてSmart Contract Bountyで進行。

### 2026年4月（今月）

| 項目 | 内容 | 担当領域 |
|---|---|---|
| ☐ ドメイン取得 | morm.network、morm.io、$MORM SNSハンドル、ENS `morm.eth` | Brand |
| ☐ 公式X / Discord立上げ | 仮名コア貢献者主導 | Community |
| ☐ Whitepaper v0.2レビュー（本ドキュメント） | コミュニティ・初期アドバイザーレビュー | Strategy |
| ☐ コア貢献者15名集合（仮名OK） | リファラル + Cryptoツイッター | Recruit |
| ☐ AGENTS.md公開（AI Agent設計） | GitHub経由 | Tech |

**KPI目標（月末）**: コア貢献者5名、Discord 500人、X 1,000フォロワー

### 2026年5月

| 項目 | 内容 |
|---|---|
| ☐ AI Agent設計詳細化（5種コア） | Moderation / Treasury / Support / Analytics / Education |
| ☐ ブランドキット完成 | ロゴ、カラー、フォント、UIライブラリ |
| ☐ Whitepaper v1.0 公開 | 公式サイト + GitHub + IPFS |
| ☐ 初期サイト公開（Manifesto、Whitepaper、Roadmap） | morm.network |
| ☐ PoC #1: 3秒Cells ストリーミング | ローカル環境、5デバイス間 |
| ☐ メーリングリスト・Phase 0 Waitlist開始 | Privy/Loops経由 |

**KPI目標**: Discord 2,000、Whitepaper DL 5,000、Waitlist 10,000

### 2026年6月

| 項目 | 内容 |
|---|---|
| ☐ PoC #2: Walletless ID（Passkey + Social Recovery） | iOS/macOS/Windows |
| ☐ PoC #3: Proof of Physical Evidence プロトタイプ | 単一動画ハッシュ・チェーン記録 |
| ☐ AI Agent プロトタイプ動作確認 | Moderation Agent α |
| ☐ Smart Contract第一版（Token / Distributor / Bounty / DAO Voting） | 内部レビュー |
| ☐ 初期Validator候補10〜15名選定 | コミュニティ・コアコントリビュータ |
| ☐ コア貢献者15名体制完成 | プロトコル、AI、フロント、DevOps |

**KPI目標**: コア貢献者15名、Discord 5,000、Waitlist 30,000

### 2026年7月

| 項目 | 内容 |
|---|---|
| ☐ MORM Chain Testnet α コードフリーズ | DAGコンセンサス + PoUW プロトタイプ |
| ☐ Smart Contract初版完成 | エスクロー、Slash、配布、DAO投票 |
| ☐ Treasury Multi-sig 5/7 署名者確定 | 地理分散、コミュニティ評価で選任 |
| ☐ AI Agent αバージョン公開 | GitHub、AGPL-3.0 |
| ☐ 初期Validator向け技術ドキュメント整備 | GitHub公開 |
| ☐ 第1回AMA（X Spaces / Discord） | コミュニティとの直接対話 |

**KPI目標**: コア貢献者20名、Discord 10,000、X 25,000

### 2026年8月

| 項目 | 内容 |
|---|---|
| ☐ Testnet α 内部稼働開始 | 5-10 内部Validator |
| ☐ AI Agent 5種が連携動作（Testnet上） | Moderation/Treasury/Support/Analytics/Education |
| ☐ MORM Cells エンコード→配信→検証 PoC完了 | RTX 6000 BWで完全パイプライン |
| ☐ Bug Bounty Program 立上げ | Smart Contract Bounty + Immunefi |
| ☐ 第三者監査契約（OpenZeppelin、Trail of Bits等） | 最低2社並行、Audit Coordinator Agent経由 |

**KPI目標**: Discord 25,000、Waitlist 100,000、テスト稼働Validator 10台

### 2026年9月（Gate A判定）

| 項目 | 内容 |
|---|---|
| ☐ Public Testnet招待制開放 | 100 Validator目標 |
| ☐ Walletless ID β リリース | iOS/Android専用アプリ |
| ☐ MORM Phase 0 α 公式アナウンス | プレスリリース、X発表 |
| ☐ Gate A 全要件チェック | 進捗レビュー |

**KPI目標**: コア貢献者25名、Discord 50,000、Validator 100台

---

## 3. MORM Phase 0 α/β（2026年10月〜2027年3月）

**目的**: Testnet安定運用、Audit完了、TGE準備。
**特徴**: AI Agentが本番運用に向けたシミュレーション、Smart Contract最終固化。

### 2026年10月

| 項目 | 内容 |
|---|---|
| ☐ Public Testnet 開放（500 Validator目標） | 招待ハードルを段階的に下げる |
| ☐ MORM Shop α クローズドテスト | 50取引／PoPE検証 |
| ☐ スマコン監査 第1回結果 | 修正フィードバック対応 |
| ☐ MORM Initial Airdrop ホワイトリスト基準公開 | 透明性のため詳細公開 |
| ☐ AI Moderation Agent ベンチマーク | 誤判定率測定 |
| ☐ DEX流動性Bootstrap計画策定 | Uniswap、Raydium候補 |

**KPI目標**: Validator 500、Testnet TX 10万件、Discord 75,000

### 2026年11月

| 項目 | 内容 |
|---|---|
| ☐ MORM Cells 50%/10%サイクル本実装 | 体感レイテンシ <300ms達成 |
| ☐ Generation ID（C2PA準拠）プロトタイプ完成 | Adobe CAI互換テスト |
| ☐ V-Hash + 音声FP統合 | 大規模重複検知ベンチ |
| ☐ Bug Bounty 初期報酬配布 | Smart Contract経由 |
| ☐ Audit 第2回結果 | OpenZeppelinから |
| ☐ AI Agent負荷テスト | 100K同時アクセス想定 |

**KPI目標**: Validator 1,000、Testnet 動画10万本、Discord 100,000

### 2026年12月

| 項目 | 内容 |
|---|---|
| ☐ 監査最終Pass、コードフリーズ | 重大Issue 0件 |
| ☐ TGE準備：DEX流動性Bootstrap最終計画 | $5M相当の初期流動性 |
| ☐ MORM Initial Airdrop スナップショット | TGE 30日前 |
| ☐ Adminキー Renounce準備（Bridge/Multi-sig除く） | コミュニティ最終確認 |
| ☐ AI Agent本番候補確定（5種） | DAO初回投票による承認 |

**KPI目標**: Validator 1,500、Discord 150,000、Waitlist 500,000

### 2027年1月: **TGE（Token Generation Event）**

| 項目 | 内容 |
|---|---|
| ☐ **MORM Mainnet ローンチ** | DAGコンセンサス本稼働 |
| ☐ **MORM Token TGE** | 流動性プール開放（DEX中心） |
| ☐ **MORM Initial Airdrop配布** | 500M MORM 配布 |
| ☐ **PoUW報酬開始** | Reward Distributor稼働 |
| ☐ **AI Agent本番運用開始** | 5種フル稼働 |
| ☐ DEX上場（Uniswap、Raydium等） | Day 0、Smart Contract経由のBootstrap |
| ☐ **Adminキー全Renounce** | Bridge/Multi-sig除く |
| ☐ **DAO投票機能Live** | 軽微パラメータの初投票実施 |

**KPI目標**: Mainnet Validator 2,000、初日取引高 $5M、Token Holder 50,000

### 2027年2月

| 項目 | 内容 |
|---|---|
| ☐ **MORM Phase 1 始動**（Closed β、10,000名招待） | Initial Airdrop受領者中心 |
| ☐ **MORM Shop 商用始動** | 限定カテゴリ・限定地域 |
| ☐ Validator Tier運用開始 | Creator / Publisher / Pioneer |
| ☐ AI Marketing Agent デプロイ | 多言語投稿開始 |
| ☐ AI Translation Agent デプロイ | 5言語ローカライズ自動同期 |
| ☐ DAO Tier 2 投票実装 | 中規模パラメータ投票開始 |

**KPI目標**: アクティブユーザー 50,000、初Shop取引 100件、Discord 200,000

### 2027年3月（Gate B判定終了）

| 項目 | 内容 |
|---|---|
| ☐ Closed β 拡大（50,000名） | アジア・北米 |
| ☐ MORM iOS/Android v1.0 公開（β） | TestFlight、Internal Testing、PWA同時提供 |
| ☐ Initial Verified Creator 100名到達 | 招待＋AI Audit Coordinator経由 |
| ☐ バイラル動画初事例 | 100万再生超 |
| ☐ AI Compliance Agent デプロイ | 大口取引KYCオーケストレーション開始 |

**KPI目標**: MAU 100,000、Validator 5,000、初Shop累計 1,000件

---

## 4. MORM Phase 1（2027年4月〜2027年12月）

**目的**: Closed β → Open βへ拡大。Creator経済本格稼働。AI Agent全面展開。

### 2027 Q2（4-6月）: 加速期

| 月 | マイルストーン |
|---|---|
| 4月 | iOS/Android v1.0 公式リリース、Verified Creator 500名、MAU 200K |
| 5月 | MORM Studio v1.0（クリエイター向け編集ツール）、MAU 350K |
| 6月 | TGE 1周年、Creator 1,000名、MAU 500K、Initial Airdrop振り返り |

**Q2末KPI**: MAU 500,000、Validator 10,000、累計動画 100万本、Shop月間取引 10,000件

### 2027 Q3（7-9月）: 拡張期

| 月 | マイルストーン |
|---|---|
| 7月 | MORM AI Lab β（生成AIサービス）、Indonesia/Philippines展開 |
| 8月 | India・Vietnam追加、MORM Live α（ライブ配信） |
| 9月 | Backers cliff終了、最初のVesting Unlock、MAU 1M |

**Q3末KPI**: MAU 1,000,000、Validator 25,000、ノード稼働 50,000、Shop月間 50,000件

### 2027 Q4（10-12月）: 完了期

| 月 | マイルストーン |
|---|---|
| 10月 | DAOガバナンス本稼働（Snapshot移行）、Pioneer Tier開放 |
| 11月 | MORM Live v1.0、AI Bug Triage Agent本番、MAU 1.5M |
| 12月 | MORM Phase 1完了、Phase 2準備、MAU 2M、Audit再実施 |

**Q4末KPI（Gate C判定）**: MAU 2,000,000、Validator 50,000、ノード 100,000、Shop累計 100万件

---

## 5. MORM Phase 2（2028年1月〜2028年12月）

**目的**: Public Launch、グローバル展開、エコシステム拡張。

### 2028 Q1: Public Launch

| 月 | マイルストーン |
|---|---|
| 1月 | **MORM Public Launch**（招待制解除）、Translation Agentが5言語ローカライズ完了（英・日・西・葡・尼） |
| 2月 | App Store / Google Play承認（個別貢献者経由）、PWA同時提供 |
| 3月 | MAU 5M、Validator 100,000、メディア露出ピーク |

**Q1末KPI**: MAU 5,000,000、ノード 200,000、累計動画 1億本

### 2028 Q2: Live & Hardware

| 月 | マイルストーン |
|---|---|
| 4月 | MORM Hardware（専用カメラ・ノード機器）パートナー発表 |
| 5月 | MORM Live v2.0、ライブコマース機能完全統合 |
| 6月 | MAU 10M |

**Q2末KPI**: MAU 10,000,000、ライブ視聴 月間1億時間

### 2028 Q3: SDK & Bridge

| 月 | マイルストーン |
|---|---|
| 7月 | **MORM SDK 公開**（サードパーティdApp開発キット） |
| 8月 | wMORM Bridge to Ethereum・Solana 公開 |
| 9月 | サードパーティdApp 100件超リリース |

**Q3末KPI**: MAU 20M、Bridge累計取扱 $1B

### 2028 Q4: Global Reach

| 月 | マイルストーン |
|---|---|
| 10月 | ラテンアメリカ・アフリカ重点展開（Translation Agentで10言語追加） |
| 11月 | 教育・B2Bパートナーシップ発表 |
| 12月 | MAU 50M、ノード 1M、TGE 2周年 |

**Q4末KPI（Gate D判定）**: MAU 50,000,000、ノード 1,000,000、Shop累計 1,000万件

---

## 6. MORM Phase 3（2029年〜）

**目的**: 完全自律運営、新領域開拓、創業貢献者完全フェードアウト。

### 2029年（年次マイルストーン）

| 四半期 | 主要マイルストーン |
|---|---|
| Q1 | MORM Spatial（VR/AR動画）α、B2B/Enterprise受入開始 |
| Q2 | MORM IoT機能、Bitcoin Lightning Bridge |
| Q3 | MAU 100M、Tier別ノード総数1,000万 |
| Q4 | Bridge累計取扱 $100億、Treasury Multi-sig署名者交代開始 |

### 2030年

| 四半期 | 主要マイルストーン |
|---|---|
| Q1-Q2 | DAO主導の主要プロトコル進化、創業貢献者フェードアウト宣言 |
| Q3-Q4 | MAU 200M、完全自律達成、5年目標KPI到達 |

### 2031年以降

- DAO + AI Agentによる完全自律運営
- 第二世代AI Agent群への進化（コミュニティ主導の改修競争）
- 創業貢献者は一参加者として継続貢献

---

## 7. クロスカッティング・トラック（並行進行）

### 7.1 Compliance & Regulatory Watch（AI Legal Research Agent主管）

| 期間 | 内容 |
|---|---|
| 2026 Q2 | 主要法域（日米EU・SG）の規制ベースライン把握 |
| 2026 Q3-Q4 | TGE時の証券性ベンチマーク（Howeyテスト等のセルフチェック） |
| 2027 全期間 | 段階的KYC（取引額別、Compliance Agent経由） |
| 2027 Q4 | EU MiCA動向監視（プロトコルへの影響評価） |
| 2028 全期間 | 各法域別オプトアウト機構の精緻化 |
| 2029+ | DAO法的ラッパー（DAO LLC等）の必要性をDAO投票 |

### 7.2 Smart Contract Audits

| タイミング | 内容 |
|---|---|
| 2026 Q3 | 内部レビュー、static analysis（自動Bot） |
| 2026 Q4 | 第1回外部監査（OpenZeppelin等、Audit Coordinator Agent経由） |
| 2026 Q4 | 第2回外部監査（Trail of Bits等） |
| TGE前 | Bug Bounty 30日間ロックダウン |
| TGE後 各6か月 | 継続監査（DAO予算で発注） |
| 主要アップグレード時 | 都度監査 |

### 7.3 Community Growth

| 月 | Discord目標 | X目標 | Waitlist/MAU |
|---|---|---|---|
| 2026/04 | 500 | 1K | 0 |
| 2026/06 | 5K | 10K | 30K |
| 2026/09 | 50K | 100K | 200K |
| 2026/12 | 150K | 300K | 500K |
| 2027/03 (TGE+) | 200K | 500K | 100K MAU |
| 2027/06 | 300K | 1M | 500K MAU |
| 2027/12 | 500K | 2M | 2M MAU |
| 2028/06 | 1M | 5M | 10M MAU |
| 2028/12 | 2M | 10M | 50M MAU |
| 2029/12 | 5M | 25M | 100M MAU |

### 7.4 Marketing & PR（AI Marketing Agent主管）

| Phase | 戦略 |
|---|---|
| Pre-Launch | コミュニティ・シーディング、テックメディア |
| Phase 0 | Crypto系メディア（CoinDesk、The Block）、Twitter influencer |
| Phase 1 | Tech系メディア（TechCrunch、The Verge）、AMA連発 |
| Phase 2 | Mainstream（Mainstream press、TV）、新興国でのローカル媒体 |
| Phase 3 | グローバル・カルチャー・モーメント創出 |

すべての投稿はAI Marketing Agentが自律生成。重要発表のみDAO承認。

### 7.5 Hardware Track（並行）

| 時期 | マイルストーン |
|---|---|
| 2026 Q4 | Hardware Working Group立上げ（コミュニティDAO小委員会） |
| 2027 Q3 | 専用ノード機器プロトタイプ |
| 2028 Q1 | 専用カメラ仕様策定（PoPE最適化） |
| 2028 Q3 | ハードウェアパートナー量産開始 |
| 2029 Q1 | MORM Hardware ストア・ローンチ |

### 7.6 AI Agent Evolution

| 時期 | マイルストーン |
|---|---|
| 2026 Q3 | AI Agent 5種コアデプロイ（Testnet） |
| 2026 Q4 | AI Agent本番候補確定 |
| 2027 Q1 | TGE時に5種本番稼働 |
| 2027 Q2 | Marketing/Translation/Compliance Agent追加 |
| 2027 Q4 | Bug Triage / Legal Research / Education Agent追加 |
| 2028 Q1 | Audit Coordinator Agent追加（10種フル稼働） |
| 2028 Q3+ | DAO主導のAgent競合提案制度開始 |
| 2029+ | 第二世代AI Agent群への進化 |

---

## 8. 経済マイルストーン（数値ベース）

### 8.1 Token Holder数

| 時期 | 目標 |
|---|---|
| TGE Day 0 (2027/01) | 50,000 |
| TGE +6か月 | 200,000 |
| TGE +12か月 | 500,000 |
| TGE +24か月 | 5,000,000 |
| TGE +36か月 | 20,000,000 |

### 8.2 ステーキング率

| 時期 | 目標 | 想定APY |
|---|---|---|
| MORM Phase 0 | 30% | 18-25% |
| MORM Phase 1 | 40% | 12-18% |
| MORM Phase 2 | 50% | 8-12% |
| MORM Phase 3 | 55% | 5-8% |

### 8.3 Shop GMV（Gross Merchandise Volume）

| 時期 | 月間GMV目標 |
|---|---|
| 2027 Q1 | $100K |
| 2027 Q4 | $5M |
| 2028 Q4 | $50M |
| 2029 Q4 | $500M |
| 2030 Q4 | $5B |

### 8.4 Treasury残高（DAO Multi-sig管理）

| 時期 | 想定運営Treasury |
|---|---|
| TGE | $10M（流動性込み） |
| TGE +12か月 | $50M |
| TGE +24か月 | $200M |
| TGE +36か月 | $500M |

---

## 9. リスクトリガー＆コンティンジェンシー

各マイルストーンで以下のトリガーが発動した場合、対応プランを実行する。
**法人がないため、対応はSmart Contract + AI Agent + DAO投票で完結する。**

### 9.1 規制ショック

**Trigger**: 主要法域で類似プロトコル全面禁止、または$MORMの証券認定。
**Action**:
- AI Compliance Agentが当該法域からのアクセス即時遮断
- DAO投票でTreasury振替（48時間Tier 3）
- 残法域での運営継続
- AI Legal Research Agentが代替法域分析

### 9.2 技術的失敗

**Trigger**: 大規模ハック、コンセンサス障害、PoPE回避手法の発見。
**Action**:
- **Emergency Multi-sig 5/7署名でPause**
- 影響評価・修復プラン公表（48時間以内）
- 補償スキーム実行（Treasury活用、DAO Tier 3投票）
- 再開前に第三者再監査（Audit Coordinator Agent経由）

### 9.3 ユーザー獲得未達

**Trigger**: 各PhaseのKPI（MAU等）が目標の50%以下で60日以上推移。
**Action**:
- AI Marketing Agentの予算追加投入（DAO投票）
- 製品ピボット検討（DAO Tier 3投票）
- パートナーシップ強化（Bounty Contractで募集）
- 次Phase遅延宣言（透明性のため公開）

### 9.4 Token価格急変

**Trigger**: $MORM価格が30日平均から50%以上下落、または非合理な急騰。
**Action**:
- AI Treasury Agentが流動性追加注入提案
- ノード報酬係数の一時調整（DAO Tier 1投票、48時間）
- ステーブル建てオプション拡充

### 9.5 競合激化

**Trigger**: 既存プラットフォームがMORMコア機能を模倣。
**Action**:
- PoPE特許化検討（防御的、DAO Tier 3投票）
- 差別化機能の前倒しリリース（Bounty追加）
- 独自Brand強化キャンペーン（Marketing Agent予算増）

### 9.6 AI Agent暴走

**Trigger**: AI Agentが想定外の判断（誤検閲多発、誤Slash等）。
**Action**:
- Emergency Multi-sigによる該当Agent即時停止
- 代替Agent（バックアップ系）への自動切替
- DAO Tier 3投票でAgent修正・交換

### 9.7 Treasury Multi-sig署名者の不正/離脱

**Trigger**: 署名者の信頼性に問題、または7名中3名以上の同時離脱。
**Action**:
- DAO Tier 3緊急投票で代替署名者選任
- 既存Multi-sigを新規アドレスに移行
- 残署名者で過渡期管理

---

## 10. KPIダッシュボード（AI Analytics Agent提供）

### 10.1 リアルタイム監視（公開）

`https://transparency.morm.network`（予定）で以下を24/7公開：

- 稼働ノード数（Tier別）
- アクティブViewer / Creator / Publisher / Pioneer
- 動画投稿数（24h / 7d / 30d）
- MORM Token価格・流動性
- Shop取引数・GMV
- 詐欺検知率・Slash件数
- 平均視聴開始時間
- ネットワーク全体トランザクション処理数
- AI Agent判断ログ
- Treasury資金移動

### 10.2 週次レビュー指標（DAO公開）

- Discord / X 成長率
- 新規登録ユーザー数
- 投稿動画の完了率
- Cross-Tier 移行数
- バグ報告と対応SLA
- AI Agent応答レイテンシ・誤判定率

### 10.3 月次戦略指標（DAO投票材料）

- Phase Gateの達成率
- Treasury残高と支出
- 法務・規制動向（Legal Research Agent提供）
- 競合動向
- パートナーシップ進捗
- AI Agent評価レビュー

### 10.4 四半期戦略指標

- KPIダッシュボード総合レビュー
- Roadmap見直し（DAO Tier 3投票）
- 重要決定（DAO投票）
- Treasury再配分

---

## 11. 進捗報告フォーマット

### 11.1 公開Roadmap更新（毎月、AI Marketing Agentが配信）

毎月末、以下を公式サイトとX/Discordで公開：

- 完了したマイルストーン（チェックリスト形式）
- 進行中の項目（進捗％）
- 遅延項目（理由と対応プラン）
- 来月の優先事項
- KPI実績 vs 目標

### 11.2 四半期レポート（DAOフォーラムに自動投稿）

- Phaseの達成状況
- 財務状況（Treasury含む）
- DAO主要決議
- 次四半期の重点

### 11.3 年次レポート（コミュニティ承認）

- 全Phaseのレビュー
- DAO投票実績
- パートナーシップ・統合実績
- 翌年の戦略

---

## 12. 想定外の朗報シナリオ

逆に、これらが起きた場合は前倒しを検討（DAO Tier 3投票）：

- **クリプト・ブルマーケット到来**: TGE前倒し、Marketing予算増大
- **大手プラットフォーマーの暴挙**: ユーザー大量流入の機会、AI Support Agent拡張
- **メディアバイラル**: スケール対応の前倒し、AI Compliance Agent強化
- **大手パートナーシップ**: ハードウェアOEM、グローバル展開の加速
- **EU AI Act等の追い風**: Generation IDのアドバンテージを活用

---

## 13. 「法人なし」設計の最重要前提

このマイルストーンは「法人なし」を前提に組まれている。実際の運営では：

| 伝統的なPM作業 | MORMでの対応 |
|---|---|
| 雇用契約・給与計算 | ❌ 不要（Bounty Contract） |
| 法人税申告 | ❌ 不要（プロトコルに納税義務なし） |
| 銀行口座管理 | ❌ 不要（全crypto-native） |
| オフィス賃貸 | ❌ 不要（リモート） |
| Investor Relations | ⚠️ 限定的（AMA + 透明性ダッシュボード） |
| 経営会議 | ❌ DAO投票に置換 |
| 商標登録 | ⚠️ DAOがLLC化された地域で（Wyoming等） |
| App Store登録 | ⚠️ 個別貢献者が個人として |

詳細は [AGENTS.md](AGENTS.md) §6 参照。

---

## 改訂履歴

- **2026-04-26 v0.4** — PoC Phase 1-27f完了（46項目、DAG/QUIC/BFT/Multi-sig/Web hardening/Tx confirm dialog 全達成、SECURITY §5 must-have OK = mainnet candidate最低条件達成）を反映
- **2026-04-25 v0.3** — PoC Phase 1-23a完了を反映、実装ステータス節を冒頭に追加
- **2026-04-25 v0.2** — 法人なし設計、AI Agent中心、Phase名変更（Genesis→Phase 0等）
- **2026-04-25 v0.1** — 初版作成

---

*本書は内部計画文書であり、外部公開時は適切に編集・抽出してください。マイルストーンは状況に応じて柔軟に修正します。透明性のため遅延・変更も公表します。*
