# MORM AI Agent アーキテクチャ

**Version**: 0.1 (Draft)
**Date**: 2026-04-25
**Status**: 設計ドラフト

---

## 0. 設計原則

MORMには**法人（Corporation / Foundation / DAO LLC）が存在しない**。
中央運営チームも、CEOも、本社も存在しない。

代わりに、以下の3層で運営される：

```
┌─────────────────────────────────────────┐
│    Layer 3: DAO（トークンホルダー）       │  ← パラメータ決定
├─────────────────────────────────────────┤
│    Layer 2: AI Agent群                  │  ← 日常運営の自律実行
├─────────────────────────────────────────┤
│    Layer 1: Smart Contract              │  ← 不変の資金フロー
└─────────────────────────────────────────┘
```

DAOがパラメータを決め、AI Agentがその範囲内で日常運営を実行し、Smart Contractが不変の資金移動と制裁を執行する。**人間の中央権力が介在する余地はない。**

---

## 1. なぜ法人を持たないのか

### 1.1 哲学的理由

MORMマニフェストは「中心を持たない群れ」を宣言している。法人を持つことは、その中心を物理的に作ることになる。

### 1.2 実務的理由

| 法人を持つ場合のリスク | MORMの対応 |
|---|---|
| 特定法域の規制に従属 | 全法域中立 |
| 特定政府による命令で停止可能 | 停止不能 |
| 経営判断による方向転換 | DAOのみが変更可能 |
| 創業者・経営陣のスキャンダルで崩壊 | 個人の不在で耐性 |
| 30%手数料への誘惑（株主圧力） | 1%が永久不変 |

### 1.3 実例（先行例）

- **Bitcoin**: 法人なし、Satoshi匿名のまま、プロトコルが自律
- **Ethereum L1の核**: Ethereum Foundationは存在するがプロトコル自体は止められない
- **Uniswap Protocol**: Uniswap Labsは存在するが、Protocolはheadlessに動く設計
- **Tornado Cash**: 法人なし、ただし米財務省による制裁を受けた（リスクの実例）

MORMは Bitcoin / Uniswap Protocol / 各種DAOを参照モデルとする。

---

## 2. Smart Contract 層（Layer 1）

すべての資金フローはSmart Contractが執行する。Adminキー・Pauseキーは存在しない。

### 2.1 主要Contract

| Contract | 役割 | 不変性 |
|---|---|---|
| **MORM Token** | 総供給100億固定、発行・配分ロジック | 完全不変 |
| **Reward Distributor** | PoUWに基づくノード報酬分配 | パラメータのみDAO投票で調整可 |
| **Escrow Contract** | Shop取引の99%ロックと解放 | ロジック不変、紛争解決はDAO投票 |
| **Slash Engine** | 不正検知時の自動没収 | 検知ロジックはAI Agent経由 |
| **Burn Contract** | 焼却機構 | 比率はDAO投票で調整可 |
| **Bounty Contract** | コア貢献者への報酬支払い | DAO投票で支出 |
| **DAO Voting** | ガバナンス投票 | 不変 |
| **Bridge Contract** | wMORM発行・回収 | マルチシグ + DAO監督 |

### 2.2 Adminキーの不在

すべてのContractはデプロイ後、Adminキーを焼却（Renounce Ownership）する。例外:

- Bridge Contract（マルチシグ + DAO監督下）
- Treasury Multi-sig（DAO投票で発動）

それ以外、人間が手動で介入できる箇所はない。

---

## 3. AI Agent 層（Layer 2）

日常運営はすべてAI Agentが実行する。各Agentは：

- DAO投票で**承認されたパラメータ**の範囲内でのみ動作
- すべてのアクションは**オンチェーン記録**（透明性）
- DAOが**いつでも交換・改修可能**（オープンソース）

### 3.1 Agent カタログ

#### 🛡️ Moderation Agent（コンテンツ審査）

**役割**:
- 投稿動画のV-Hash重複チェック
- Generation ID検証（C2PA準拠）
- 不適切コンテンツ（CSAM等）のAI事前検閲
- 改ざん動画（PoPE違反）の検知

**実装**: 専用GPUクラスタ（NodePower上で稼働）+ オープンソースAIモデル
**DAO制御**: 検閲基準閾値、判定モデルの選定

#### 💰 Treasury Agent（資金運用）

**役割**:
- DAO投票で承認された予算の自動執行
- 流動性プール最適化（自動マーケットメイキング）
- Bug Bounty報酬の自動支払い
- 緊急時のTreasury Multi-sig発動提案

**実装**: マルチシグ + AI判断による署名提案
**DAO制御**: 月次予算上限、緊急発動の閾値

#### 🎫 Support Agent（カスタマーサポート）

**役割**:
- ユーザー問い合わせ24/7対応（多言語）
- バグ報告のトリアージとBug Bounty Contractへのエスカレーション
- FAQ自動更新
- 仲裁要請の初期対応

**実装**: Claude / GPT-4o / Gemini系モデル + RAG（公式ドキュメント）
**DAO制御**: 応答方針、エスカレーション基準

#### 📢 Marketing Agent（コミュニケーション）

**役割**:
- X / Discord / Telegramでの公式発信
- 多言語翻訳・展開
- コミュニティイベント告知
- AMA運営補助

**実装**: 多言語LLM + ソーシャル・スケジューラ
**DAO制御**: トーン・メッセージ方針、禁止表現リスト
**注**: 個別の投稿は各Agentが自律生成するが、重要発表はDAO投票で承認

#### ⚖️ Legal Research Agent（規制監視）

**役割**:
- 各法域の暗号資産規制動向のモニタリング
- 重要規制変更の早期警告
- 利用規約の更新提案（DAO投票へ）
- 地域別オプトアウトの判断補助

**実装**: 規制データベース（Bloomberg Law等）連携 + LLM分析
**DAO制御**: 監視対象法域、警告閾値

#### 🔍 Compliance Agent（KYC/AML）

**役割**:
- 大口取引のKYCオーケストレーション
- 第三者KYCプロバイダ（Sumsub等）との連携
- 制裁対象アドレス監視（Chainalysis等連携）
- 怪しい取引パターンの検知

**実装**: API連携（Sumsub、Chainalysis、TRM Labs）
**DAO制御**: KYC閾値、対象法域

#### 🐛 Bug Triage Agent（バグ管理）

**役割**:
- バグ報告のセキュリティ・インパクト判定
- Bug Bounty金額の提案（Critical/High/Medium/Low）
- 重複報告の統合
- パッチ提案者へのインセンティブ計算

**実装**: 既存Bug Bountyプラットフォーム（Immunefi）統合 + 独自分類モデル
**DAO制御**: 報酬テーブル、判定基準

#### 🌐 Translation Agent（翻訳維持）

**役割**:
- ドキュメント・UIの多言語自動同期
- 新言語追加の自動初期翻訳
- ネイティブレビュアー（コミュニティ）への発注

**実装**: GPT-4o / Claude + 翻訳メモリ + コミュニティバウンティ連携
**DAO制御**: 対応言語リスト、品質基準

#### 📊 Analytics Agent（KPI監視）

**役割**:
- ネットワーク全体のKPIダッシュボード提供
- 異常検知（突然のユーザー減、トークン価格急変等）
- DAO向けレポート自動生成
- パブリック透明性ダッシュボード提供

**実装**: オンチェーンデータ + Web2 API連携
**DAO制御**: 監視指標、警告閾値

#### 🎓 Education Agent（オンボーディング）

**役割**:
- 新規ユーザー向けインタラクティブ・ガイド
- ノード設定支援
- Walletless ID初回設定サポート
- 多言語対応Q&A

**実装**: LLM + RAG + Voice対応
**DAO制御**: コンテンツ更新、対応シナリオ

#### 🤖 Audit Coordinator Agent（監査調整）

**役割**:
- 第三者監査会社との契約調整（Smart Contract経由）
- 監査スコープの提案
- 監査結果のDAO報告
- 修正パッチへのバウンティ発行

**実装**: 監査会社API + 契約テンプレート
**DAO制御**: 監査会社選定、予算

### 3.2 Agent間の協調

各Agentは独立して動作するが、以下のイベントで協調する：

```
[Moderation Agent] が違反検知
   ↓ オンチェーン報告
[Slash Engine Smart Contract] が自動Slash執行
   ↓
[Treasury Agent] が被害者補填予算を提案
   ↓ DAO投票（24h）
[Bounty Contract] が補填送金
   ↓
[Support Agent] が当事者へ通知
   ↓
[Analytics Agent] がインシデントを記録
```

### 3.3 Agent の交換可能性

DAOは投票でAgentを交換できる。これにより：
- AI技術の進化に追従可能
- 特定モデルへのロックイン回避
- 競合Agent提案者間のオープン競争

```
DAO投票 → 「Moderation AgentをClaude 5から Llama 6に変更」
   ↓
2週間移行期間
   ↓
新Agentがオンチェーン認証を取得
   ↓
旧Agent停止、新Agentが本番稼働
```

---

## 4. DAO 層（Layer 3）

### 4.1 投票権

| 投票単位 | 権限 |
|---|---|
| **1 MORM = 1 vote** | 基本ルール |
| **保有期間ボーナス** | 6か月以上保有で投票重み × 1.2、12か月で × 1.5 |
| **Pioneer Tier ボーナス** | 長期貢献Tierで × 1.3 |
| **単一アドレス上限** | 全議決権の1% |

### 4.2 投票対象

#### Tier 1: 軽微パラメータ（48時間投票、Quorum 3%）

- ノード報酬重み付け係数
- スパム判定閾値の微調整
- AI Agentの応答テンプレ更新

#### Tier 2: 中規模パラメータ（7日間投票、Quorum 10%）

- 焼却率の調整
- AI Agent本体の交換
- 新言語サポートの追加
- Ecosystem Fund配分

#### Tier 3: 重要決定（14日間投票、Quorum 20%）

- AI Agent の追加・削除
- 新Smart Contractのデプロイ
- Bridge追加
- 大口Treasury支出（>$1M相当）

#### Tier 4: 不変パラメータ（投票不可）

- 総発行量100億
- 1%手数料
- ユーザー所有データ原則
- Walletless ID原則
- PoPE必須原則

### 4.3 投票プロセス

```
[誰でも提案可能]
   ↓ 1,000 MORMステーク（提案デポジット）
[7日間ディスカッション]
   ↓ Discord / Forum
[投票期間（Tier別）]
   ↓ Snapshot or オンチェーン投票
[可決]
   ↓ 24-72時間 Timelock
[Smart Contract執行 / Agent反映]
   ↓
[結果記録]
```

### 4.4 緊急対応

DAOプロセスでは間に合わない緊急事態（重大ハック等）には：

- **Emergency Multi-sig**（5/7署名）でPause可能
- 署名者: 各大陸から地理的分散
- 発動後72時間以内にDAO投票で正式承認/取消
- 署名者は信頼性の高いコミュニティメンバーから選出

---

## 5. コア貢献者の在り方

### 5.1 「従業員」ではなく「貢献者」

- 雇用契約なし
- 給与なし
- 全員が**Smart Contract Bounty**で報酬を受領
- 個人として、または独立した請負業者として参加
- 各国の税務は本人責任

### 5.2 貢献カテゴリ

| カテゴリ | 報酬源 |
|---|---|
| プロトコル開発 | Bounty Contract（DAO予算） |
| AI Agent開発 | Bounty Contract |
| ドキュメント | Bounty Contract + 翻訳バウンティ |
| 法務リサーチ | Bounty Contract |
| バグ修正 | Bug Bounty Contract |
| バリデーター運用 | PoUW報酬 |
| コミュニティ運営 | Quest System報酬 |

### 5.3 匿名/仮名 OK

すべての貢献者は匿名または仮名で参加できる。Tornado Cash事件を踏まえ、特に重要パラメータの開発者は匿名性を維持することが推奨される。

### 5.4 Founding Contributor

MORMをbootstrapする最初の貢献者は **YACHIDA** が *Founding Contributor* として記録される。

役割:
- 最初のSmart Contractをデプロイ
- 初期AI Agentを公開（オープンソース）
- 初期DAOパラメータを設定
- TGE実行

TGE後は**他のコア貢献者と同等の一参加者**へ移行し、運営支配権・特別投票重み・追加トークン配分は持たない。Founding Contributorは「最初の起動を切った歴史的事実」を記録する呼称であり、CEOやFounderのような運営権限ではない（Bitcoin / Satoshi Nakamotoモデル参照）。

---

## 6. 法人なしで実行できないこと（実務制約）

正直に列挙する：

### 6.1 課題

| 業務 | 理由 | MORMの対応 |
|---|---|---|
| 銀行口座開設 | 法人不在 | 不要（全てcryptonative） |
| 従来型監査会社の契約 | 法的責任主体不明 | crypto-native監査会社（OpenZeppelin、Code4rena等）を活用 |
| App Store開発者登録 | 個人または法人が必要 | 個別貢献者が個人登録、または PWA優先 |
| 従来型法律事務所のリテイナー | 契約相手不在 | 個別案件ベースのバウンティ発注 |
| 暗号資産取引所の上場申請 | 法的責任主体要求 | DEX上場のみで開始、CEX上場は各国の取引所が独自判断 |
| 商標登録 | 出願主体不明 | DAOが出願（DAOがLLC化された地域で） |

### 6.2 グレー領域

- **VASP登録**: 一部法域で必要だが、headless protocolは登録対象外と主張可能
- **税務**: ユーザー個人の責任。プロトコル自体には税務義務なし
- **GDPR遵守**: AI Agentによる自動データ処理として対応、明示同意ベース

### 6.3 オプトアウト

特定法域がプロトコル全体を違法とした場合：
- AI Agentが当該地域からのアクセスを技術的に遮断
- DAOが地域別ポリシーを投票
- ユーザーは自己責任でVPN等を使用（推奨はしない）

---

## 7. ロードマップ：Agentデプロイ

### MORM Phase 0（〜TGE）

**Pre-TGE**:
- AI Agent中核5種をデプロイ（Moderation / Treasury / Support / Analytics / Education）
- Smart Contract初期セット（Token / Distributor / Bounty / DAO Voting）
- Audit Coordinator Agent経由で第三者監査依頼

**TGE時**:
- Adminキー全Renounce（Bridge / Multi-sig除く）
- DAOへの権限移譲完了
- AI Agentが本番運用開始

### MORM Phase 1

- Marketing Agent / Translation Agent追加
- Compliance Agent統合
- Legal Research Agent本格稼働

### MORM Phase 2

- Bug Triage Agent高度化
- 各Agentの性能評価とDAO主導の改修
- AI Agent競合提案制度開始

### MORM Phase 3

- 完全自律運営
- 創業貢献者は一参加者へ
- 第二世代AI Agent群への進化

---

## 8. 透明性と責任

### 8.1 すべてオープンソース

- AI Agentコード（GitHub、AGPL-3.0）
- Smart Contractコード（GitHub、MIT）
- Documentation（GitHub、CC-BY-4.0）
- Agent判断ログ（オンチェーンまたはIPFS）

### 8.2 責任の所在

伝統的な「経営責任」は存在しない。代わりに：

| 責任 | 主体 |
|---|---|
| Smart Contractコードのバグ | コード貢献者 + Bug Bounty報奨 |
| AI Agent判断ミス | DAOによるAgent改修 |
| 不正コンテンツの流通 | Moderation Agent + Slash Engine |
| ユーザー間トラブル | DAO仲裁 |
| 規制違反 | ユーザー自己責任 + Compliance Agent |

### 8.3 監査ダッシュボード

リアルタイム公開：
- 全Agent判断ログ
- 全Treasury資金移動
- 全Slash執行
- 全DAO投票
- 全Bug Bounty支払い

URL: `https://transparency.morm.network`（公開予定）

---

## 9. リスクと緩和

### 9.1 AI Agent暴走リスク

**緩和**:
- パラメータ範囲の厳格な制限（DAOで設定）
- Multi-Agent冗長性（重要判断は複数Agent合議）
- Emergency Multi-signによるPause機構

### 9.2 DAO Governance Attack

**緩和**:
- アンチホエール機構（1%上限）
- 保有期間ボーナス（短期投機家の影響を抑制）
- 段階的Quorum（重要決定ほど高Quorum）
- 24-72時間Timelock

### 9.3 規制リスク

**緩和**:
- 各国法域別オプトアウト
- 匿名/仮名貢献者の保護（Tornado Cash教訓）
- Compliance Agent経由の自主的KYC（大口取引のみ）

### 9.4 AI Modelロックイン

**緩和**:
- 全Agent交換可能
- オープンソースモデルへの段階的移行
- DAO投票によるモデル選定

---

## 10. 現実的な妥協

「完全に法人なし」は理想だが、以下については現実的妥協を検討：

### 10.1 Treasury Multi-sig署名者

完全headlessは緊急対応が困難。最小限の人間署名者を維持：
- 5/7マルチシグ
- 地理的分散
- DAO投票で選任・解任

### 10.2 ドメイン管理

`morm.network`等のドメインは中央集権ICANN傘下。対応：
- ENS / Unstoppable Domains等の分散型ドメインを併用
- 主要ドメインはMulti-sig管理

### 10.3 アプリストア配布

Apple / Google審査は法的責任主体を要求。対応：
- 個別貢献者が個人開発者として申請
- PWA（Progressive Web App）を主軸に
- F-Droid / 直接APK配布も並行

これらは「法人なし」原則の例外として、TERMS.mdとガバナンス文書に明記する。

---

## 11. 用語集

- **Layer 1 (Smart Contract)**: 資金フロー実行
- **Layer 2 (AI Agent)**: 日常運営自律実行
- **Layer 3 (DAO)**: パラメータ決定
- **Adminキー**: 中央管理者の介入権限（MORMでは焼却済）
- **Renounce Ownership**: Adminキーを永久に焼却
- **Bounty Contract**: 貢献者への報酬支払いContract
- **Emergency Multi-sig**: 緊急停止権限（5/7、地理分散）

---

*このドキュメントは設計ドラフト。実装段階で個別の Agent 仕様を別ドキュメントに分離する想定。*
