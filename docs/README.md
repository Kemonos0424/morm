# MORM Documentation

公式ドキュメント / Official documentation.

## 構成 / Structure

```
docs/
├── README.md                       — この索引 / This index
├── IMPLEMENTATION-STATUS.md        — Whitepaper執筆セッション用 単一の真実
├── RESEARCH_ORIGINALITY.md         — 先行技術調査 / Prior-art analysis
│
├── ja/   # 日本語 (primary)
│   ├── MANIFESTO.md           — 思想・存在意義
│   ├── WHITEPAPER.md          — 技術ホワイトペーパー (v0.3)
│   ├── AGENTS.md              — AI Agent運営アーキテクチャ
│   ├── TOKENOMICS.md          — トークン経済設計
│   ├── MILESTONES.md          — 詳細マイルストーン（内部計画）
│   ├── TERMS.md               — 利用規約（要法務レビュー）
│   ├── WEBSITE_COPY.md        — Webサイト用コピー集
│   ├── SNS_KIT.md             — SNS運用テンプレ
│   ├── LP_CREATORS.md         — クリエイター向けLP
│   ├── LP_NODES.md            — ノード運営者向けLP
│   └── LP_SHOP.md             — Shop参加者向けLP
│
└── en/   # English
    ├── MANIFESTO.md
    ├── WHITEPAPER.md
    ├── AGENTS.md
    ├── TOKENOMICS.md
    ├── MILESTONES.md
    ├── TERMS.md
    ├── WEBSITE_COPY.md
    ├── SNS_KIT.md
    ├── LP_CREATORS.md
    ├── LP_NODES.md
    └── LP_SHOP.md
```

## Whitepaper執筆セッションのルール

**Whitepaper（`docs/ja/WHITEPAPER.md` / `docs/en/WHITEPAPER.md`）を編集する際は、起動時に必ず [IMPLEMENTATION-STATUS.md](IMPLEMENTATION-STATUS.md) を読み込むこと。**

これは「実装の真実」を一元管理するファクトシートで、以下の役割を持つ:
- §1: 34 Phase × Whitepaper章 ↔ コード ↔ 検証ステータスのマッピング表
- §3: 引用可能な観測値（max_w=3、head=33/fin=30、Forge 32/32 PASS、TURN HMAC、A=13/B=11/C=9 等）
- §6: WP §4-§13 → 引用すべきPhaseと数値のクロスリファレンス
- §7: **書かないでほしい主張リスト**（未実装・過大評価・法的にNG）
- §9: API リファレンス
- §10: 同期ルール（WP/コード/設計書のどれを更新したらどこを直すか）

PoCコードを直接読まずに正確なWhitepaper記述ができる状態を維持するため、コード変更時は必ずIMPLEMENTATION-STATUS.mdを更新する。

## 設計原則 / Design Principles

MORMは以下の3つの根本原則で運営される:

1. **法人なし（No Legal Entity）** — Corporation/Foundation/DAO LLCは存在しない
2. **AI Agent + Smart Contract + DAO の3層構造** — 中央運営者の不在
3. **MORMのみが固有名詞** — Phase名は MORM Phase 0/1/2/3 と数値で統一

詳細は [AGENTS.md](ja/AGENTS.md) を参照。

## 読む順番 / Reading Order

### 投資家・パートナー / Investors & partners

1. [MANIFESTO](ja/MANIFESTO.md) — 思想を理解する
2. [WHITEPAPER](ja/WHITEPAPER.md) §0-3 — エグゼクティブ・サマリーと正直なPrior Art比較
3. [AGENTS](ja/AGENTS.md) — 法人なし設計の実装
4. [WHITEPAPER](ja/WHITEPAPER.md) §10-11 — ユースケースとエコシステム
5. [TOKENOMICS](ja/TOKENOMICS.md) — 経済設計
6. [WHITEPAPER](ja/WHITEPAPER.md) 残り — 技術詳細

### 開発者 / Developers

1. [WHITEPAPER](ja/WHITEPAPER.md) §4-8 — アーキテクチャ詳細
2. [AGENTS](ja/AGENTS.md) §2-3 — Smart Contract / AI Agent詳細
3. [RESEARCH_ORIGINALITY](RESEARCH_ORIGINALITY.md) — 採用技術の先行調査
4. [TOKENOMICS](ja/TOKENOMICS.md) §2-4 — リソース報酬モデル

### クリエイター / Creators

1. [LP_CREATORS](ja/LP_CREATORS.md)
2. [MANIFESTO](ja/MANIFESTO.md)

### ノード運営者 / Node Operators

1. [LP_NODES](ja/LP_NODES.md)
2. [TOKENOMICS](ja/TOKENOMICS.md) §2.1, §5

### Shop参加者 / Shop Users

1. [LP_SHOP](ja/LP_SHOP.md)
2. [TERMS](ja/TERMS.md) §7 (MORM Shop規約)

### コア貢献者 / Core Contributors

1. [AGENTS](ja/AGENTS.md) §5（法人なしの貢献構造）
2. [TOKENOMICS](ja/TOKENOMICS.md) §2.4 (Core Contributors配分)
3. [MILESTONES](ja/MILESTONES.md) §2-3（Pre-Launch〜Phase 0）

## 言語の追加 / Adding Languages

新しい言語を追加する場合は `docs/<ISO 639-1 code>/` ディレクトリを作成し、上記10ファイルを翻訳してください。

To add a new language, create `docs/<ISO 639-1 code>/` and translate the 10 files.

例 / Examples:
- `docs/zh/` — 中文
- `docs/ko/` — 한국어
- `docs/es/` — Español
- `docs/pt/` — Português
- `docs/id/` — Bahasa Indonesia
- `docs/hi/` — हिन्दी

優先順位（市場規模・検閲耐性需要から）:
1. 英語（完了）
2. 日本語（完了）
3. インドネシア語、ヒンディー語（東南アジア、南アジア）
4. スペイン語、ポルトガル語（中南米）
5. 中文（規制対応版を別途）
6. 韓国語、フランス語、ドイツ語、アラビア語

翻訳はAI Translation Agent（Phase 1以降）が自動初稿を生成し、コミュニティ・ネイティブレビュアーがバウンティ報酬で品質確認します。

## ステータス / Status

すべて **Draft v0.x**。本番公開前に以下が必要：

All documents are **Draft v0.x**. Before going live:

- [ ] コミュニティ法務リサーチ（Bounty Contract経由） / Community legal research (via Bounty Contract)
  - 各法域の暗号資産規制 / Crypto-asset regulation per jurisdiction
  - 消費者保護 / Consumer protection
  - データ保護（GDPR/CCPA/APPI等）/ Data protection
  - 青少年保護 / Youth protection
  - コンテンツモデレーション義務 / Content moderation duties
- [ ] トークノミクス数値の確定（DAO初回投票で承認） / Finalize tokenomics numbers (DAO first vote)
- [ ] ローンチ日程の確定 / Finalize launch dates
- [ ] 公式URL・連絡先の確定 / Finalize official URLs and contact

## 翻訳の整合性 / Translation Consistency

固有名詞は翻訳しない / Do not translate proper nouns:

- MORM（プロジェクトの全名称はこれを起点とする / All project names derive from this）
- MORM Cells, MORM Chain, MORM Shop, MORM Token, MORM AI Lab, MORM Studio, MORM Live, MORM Hardware, MORM SDK
- MORM Phase 0 / Phase 1 / Phase 2 / Phase 3
- MORM Initial Airdrop
- NodePower, Edge Node, Light Client
- Validator, Creator, Publisher, Pioneer, Viewer
- Node-Lock, Slash, Bond, Stake
- V-Hash, Generation ID
- Proof of Physical Evidence (PoPE)
- Proof of Useful Work (PoUW)
- Proof of Contribution (PoC)
- Proof of Effort
- Walletless ID, Passkey, FIDO2, Secure Element
- AI Agent, Smart Contract, DAO
- The Swarm for Every Frame（タグライン）

## Founding Contributor

**YACHIDA** — bootstrap役の公開記録。TGE後は他のコア貢献者と同等の一参加者へ移行（Satoshi Nakamoto / Bitcoinモデル）。運営支配権・特別投票重み・追加トークン配分なし。詳細は [AGENTS.md §5.4](ja/AGENTS.md)。

## バージョン履歴 / Version History

- **2026-04-26 v0.7** — PoC Phase 1-27f完了（46項目）、SECURITY must-have全達成（mainnet candidate最低条件OK）、DAG/QUIC/BFT/Multi-sig/Web hardening/Tx confirm 全て実装済を MILESTONES + project_morm_design に反映
- **2026-04-25 v0.6** — `IMPLEMENTATION-STATUS.md` を Whitepaper執筆セッション用 single-source-of-truth として追加。Phase 1-24a 34項目のコード↔検証マッピング、引用可能な観測値、書かないでほしい主張リスト、WP↔コード同期ルールを集約
- **2026-04-25 v0.5** — PoC Phase 1-23a完了を反映、MILESTONES に実装ステータス節追加（技術側Pre-Launch事実上完了、残るは戦略・ブランド・コミュニティ層）
- **2026-04-25 v0.4** — Founding Contributor: YACHIDA を WHITEPAPER §17 / MANIFESTO 巻末 / AGENTS §5.4 に記録
- **2026-04-25 v0.3** — 法人なし設計（AGENTS.md新規）、Phase名統一（Genesis/Hive/Swarm/Hyperswarm → MORM Phase 0/1/2/3）、Core Contributors化
- **2026-04-25 v0.2** — Prior Art正直比較、TAM追加、ユースケース展開、TOKENOMICS新規、LP × 3新規、MILESTONES新規
- **2026-04-25 v0.1** — 初稿（MANIFESTO/WHITEPAPER/TERMS/WEBSITE_COPY/SNS_KIT）
