# MORM Play — 投稿・モデレーション・分析 設計書

対象: https://play.morm.one （実体 `~/Desktop/MORM/morm-play/play_server.py`）
決定(2026-08-07): 投稿ゲート=**ハイブリッド**（段階的信頼＋AI審査を既定、大口はMORMステークで即時解放）／
コンテンツ方針=**違法・有害のみ排除の最小規制**（AIは検閲ではなく「違法・有害＋スパム検出＋年齢自動タグ」）。

前提インフラ（既存を最大流用）:
- **秘匿プロキシ** `/m/<id>/...` = 全セグメントがここを通る → ★分析の絞り込み点。
- **m0r ウォレットレスID** = Ed25519 端末内鍵。全投稿・いいね・コメントは署名必須 → シビル耐性の根。[[project_morm_walletless_accounts]]
- **MORM L1** = ステーク／スラッシュ／報酬。[[reference_morm_dashboard_integration]]
- **DGX Ollama** = AI推論。★LLMはMac Mini禁止=DGXで実行([[feedback_llm_host_policy]])。text=qwen25-agent(32b), frame=Qwen2.5-VL(無検閲)。[[project_dgx_spark]]
- **hpmini ops hub** = モデレーションworker常駐先(DGXを叩く軽い司令)。[[project_hpmini_ops_hub]]

---

## 全体パイプライン

```
[投稿] m0r署名付きアップロード
   │ ①ゲート判定(信頼tier/レート/ステーク) ── 弾かれたら即拒否(AI呼ばない=コスト0)
   ▼
[gateway] HLSエンコード → play_server に status=pending で ingest
   │
   ▼
[moderation worker (hpmini)] pending をpull
   │ ②高速ルール(ハッシュ/正規表現/URL/既知スパム) → ③DGX AI(text+frame)
   ▼
 判定 ┬ clear      → status=approved + rating(sfw/r18) → feed露出
      ├ borderline → status=pending_review → /admin/moderation 人手キュー
      └ illegal    → status=rejected(+CSAM等は即ブロック&記録) → strike
   │
   ▼
[配信] 既存 discovery + 秘匿プロキシ（approved & 年齢ゲート通過のみ）
   │
   ▼
[分析] events(append-only) + heartbeat → 集計 → /studio(投稿者) /admin(運営)
```

---

## 1. アイデンティティ & シビル耐性（根）

- 全ての投稿・コメント・いいねは **m0r アカウントのEd25519署名**必須。匿名投稿なし。
- `accounts` に信頼状態を集約。1端末passkey=1コア、招待グラフ・投稿元IPクラスタでシビル検出。
- 署名検証は**サーバ側で実装必須**（現状playのいいねは署名保存のみ＝未検証。ここで本実装）。canonical JSON→Ed25519 verify。

## 2. 投稿ゲート（ハイブリッド）

**信頼スコア trust_score 0..100 → tier**。上限は tier で決まり、**ステークで即時引き上げ**。

| tier | score | 投稿/日 | 動画尺 | リンク | コメント/日 | 審査 |
|---|---|---|---|---|---|---|
| T0 新規 | 0–9 | 1 | ≤60s | 不可 | 3 | 全件AI＋高リスクは人手 |
| T1 見習い | 10–39 | 3 | ≤180s | allowlistドメインのみ | 10 | 全件AI |
| T2 信頼 | 40–79 | 10 | ≤600s | 可(AIリンク検査) | 30 | AI＋抜き取り人手 |
| T3 実績 | 80–100 | 実質無制限 | 制限緩 | 可 | 100 | 抜き取りAI |
| **Stake** | — | ステーク額に線形 | — | 可 | — | 優先審査 |

- **ステーク・バイパス**: MORMを `stake` すると即座に T2相当の上限＋優先審査。**違反確定でスラッシュ**（没収→報酬プール）。額に応じ上限線形増。→ 良質な大口クリエイターは摩擦ゼロ、悪質は経済的に割に合わない。
- **trust_score 増減**:
  - `+` 承認投稿・一定再生/いいね到達・account age・passkey本人性・（任意KYC）
  - `−` テイクダウン・スパム判定・いいね/コメント異常パターン・被通報確定
- **レート制限** = account×action の token bucket（`rate_buckets`）。post/comment/link/like個別。
- **shadowban**: 悪質疑いは status=shadow（本人には見えるが他人に配信されない）。誤検知の摩擦を下げる。

## 3. コンテンツ本体（テキスト/情報/リンク/コメント）

`content` 拡張列: `description`(本文) / `links`(json) / `status`(pending|approved|pending_review|shadow|rejected|removed) / `rating`(sfw|r15|r18) / `mod_score` / `mod_labels`(json) / `uploader_trust`(投稿時スナップショット)。

**リンク（スパム主要ベクタ）**:
- 本文・概要・コメントからURL抽出 → 短縮URL展開して最終先を検査。
- ドメイン **allowlist/denylist**。新規/低信頼は**リンク不可**。中信頼は allowlist のみ。高信頼は AI＋既知スパムDB照合の上で可。
- 同一ドメイン連投・貼り逃げパターン検出。表示は中間警告ページ or `rel=nofollow`。

**コメント**: `comments(id, content_id, account, text, parent_id, status, mod_score, created_at)`。
- スパム抑制多層: レート制限＋近似重複連投検出（simhash）＋リンク数上限＋新規リンク禁止＋AI毒性/スパム分類＋shadowban。

## 4. AI判定（DGX Ollama・最小規制チューニング）

**二段構え**（安価な足切り→AI）:
1. **高速ルール(worker内, 無料)**: 既知CSAMハッシュ照合・既知スパムURL/ドメイン・正規表現(連絡先大量/詐欺定型)・simhash重複。
2. **AI分類(DGX)**:
   - **テキスト** (title/description/comment): `qwen25-agent`(dgx1-3) に構造化出力させる。
     ```json
     {"illegal":0-1,"csam_risk":0-1,"real_violence":0-1,"scam_fraud":0-1,
      "spam":0-1,"doxxing":0-1,"nonconsensual":0-1,"rating":"sfw|r15|r18","reason":"..."}
     ```
     ★最小規制: 通常の性的/過激**表現**は通す。閾値は「違法・実在被害」にのみ高感度。
   - **動画フレーム/サムネ**: `Qwen2.5-VL`(無検閲) で数フレームサンプル → CSAM/実暴力/実在被害の検出＋成人度で **rating自動付与**(r18タグ＋年齢ゲート)。
   - **音声**: 将来（違法勧誘等）。
- **判定→アクション**: clear=approved / borderline or 低信頼=pending_review(人手) / illegal=rejected（CSAM等は即ブロック＋記録＋strike）。
- **Human-in-the-loop**: `/admin/moderation` 承認/却下/BAN。既存 **Hermes(dgx3 opsコパイロット)** に接続可([[project_node_dashboard]])。
- **視聴者通報**: 通報→キュー再投入。閾値超で自動 pending_review。
- **worker配置**: hpmini常駐(既存 morm-payout 型の launchd worker)が pending をpull→DGX Ollamaへ HTTP→verdict書戻し。**LLM本体はDGX**（policy厳守）。オーケストレーションは軽いのでMac Mini/hpmini可。
- **監査ログ** `moderation_log(target_type,target_id,model,score,labels,decision,reviewer,ts)` = 全判定を追記（誤検知の異議・再学習・説明責任）。

## 5. エンゲージメント分析（再生数/いいね/離脱点）

**再生数**: セッション単位で重複排除（uid×時間窓）＋ボット除外。「有効再生」= N秒 or M%到達で計上（生 open != view）。

**★リテンション/離脱点** — 二系統併用:
- **クライアント heartbeat（精密・主）**: playerが3–5秒ごと `POST /api/beat {session, content_id, position, event:play|pause|seek|ended, res}`。→ 正確な watch_time / リテンション曲線(0–100%) / 最大離脱点 / リプレイ山 / シークヒートマップ。muted-autoplayや<2s離脱は除外。
- **プロキシ・パッシブ（全数・従）**: `/m/<id>/<res>/seg_NNNNN` の seg_index をサーバ側で記録 → 全数の粗い到達率＋ボット/帯域検出。※先読み・画質切替・シークでノイジー→精密値はheartbeat。**query付与はCDNキャッシュを壊すのでしない**（cookieless opaque session ヘッダ or master発行時のsession token）。
- 指標: view / unique / avg watch time / completion rate / retention curve / drop-off seg / replay hotspot / like率 / share / CTR(impression→play)。

**いいね**: 既存トグル（account単位・重複防止済）＋ boはtrust/rateで抑制。

**アクセス分析(access analytics)**:
- **events(append-only)**: page_view / impression(グリッド表示) / tile_click / search / tag_click / play_start / beat / like / share / comment / report。
- 集計: DAU・セッション / 検索語ランキング / タグ人気 / 流入(referrer・deep-link `/watch?id=`) / コホート(新規・復帰) / edge別配信量(運用) / **クリエイター別**（自分の動画分析）。
- **プライバシー**: 視聴者IPはedge経由でproxyに出るが **生IP非保存**、粗いジオ(国/地域)＋ハッシュsessionのみ（CLAUDE.mdプライバシー方針・PIIをURLに載せない）。
- **保存の教訓を最初から**: 上限・保持期限・容量監視を設計に内蔵（[[feedback_job_queue_retention]] 220GB満杯事故／[[feedback_ttl_cache_leak]] OOM）。events は日次ロールアップ→生ログは短期TTLで破棄。

**ダッシュボード**:
- `/studio`（クリエイター）: 自投稿の retention曲線・離脱点・時系列views・いいね/シェア。
- `/admin/analytics` + `/admin/moderation`（運営）。

---

## DBスキーマ（追加）

```sql
CREATE TABLE accounts(
  m0r TEXT PRIMARY KEY, created_at INT, trust_score INT DEFAULT 0, tier INT DEFAULT 0,
  verified INT DEFAULT 0, staked_morm INT DEFAULT 0, strikes INT DEFAULT 0,
  status TEXT DEFAULT 'active'  -- active|shadow|banned
);
ALTER TABLE content ADD description TEXT DEFAULT '';
ALTER TABLE content ADD links TEXT DEFAULT '[]';
ALTER TABLE content ADD status TEXT DEFAULT 'pending';   -- 既存シードは approved に移行
ALTER TABLE content ADD rating TEXT DEFAULT 'sfw';
ALTER TABLE content ADD mod_score REAL DEFAULT 0;
ALTER TABLE content ADD mod_labels TEXT DEFAULT '{}';
ALTER TABLE content ADD uploader TEXT;                    -- 既存=uploader列(m0r)
CREATE TABLE comments(id TEXT PRIMARY KEY, content_id TEXT, account TEXT, text TEXT,
  parent_id TEXT, status TEXT DEFAULT 'visible', mod_score REAL DEFAULT 0, created_at INT);
CREATE TABLE moderation_log(id INTEGER PRIMARY KEY AUTOINCREMENT, target_type TEXT, target_id TEXT,
  model TEXT, score REAL, labels TEXT, decision TEXT, reviewer TEXT, ts INT);
CREATE TABLE rate_buckets(account TEXT, action TEXT, window_start INT, count INT,
  PRIMARY KEY(account,action,window_start));
CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INT, session TEXT, account TEXT,
  kind TEXT, content_id TEXT, meta TEXT);           -- 短期TTL→日次ロールアップ
CREATE TABLE beats(session TEXT, content_id TEXT, position REAL, event TEXT, res TEXT, ts INT);
CREATE TABLE retention_daily(content_id TEXT, day INT, bucket INT, reached INT,
  PRIMARY KEY(content_id,day,bucket));              -- 0..100% を20分割等
```

## API（追加）

```
POST /api/upload/init      {m0r, sig, title, description, tags, ar}  → ゲート判定→upload URL/id
POST /api/upload/complete  {id, sig}                                 → status=pending, worker投入
POST /api/comment          {content_id, m0r, sig, text, parent_id?}  → レート/AI→visible|shadow
POST /api/beat             {session, content_id, position, event, res}
POST /api/event            {session, kind, content_id?, meta?}
POST /api/report           {target_type, target_id, reason}
GET  /api/studio/<m0r>     (要署名) 自投稿の分析
--- admin (ADMIN_TOKEN) ---
GET  /api/admin/moderation/queue     |  POST /api/admin/moderation/decide {id,decision}
GET  /api/admin/analytics
--- worker↔play_server ---
GET  /api/mod/pull (worker)  |  POST /api/mod/verdict {id, labels, score, decision, rating}
```

---

## 実装フェーズ（段階導入）

- **P1 投稿基盤**: accounts＋署名検証＋アップロード(init/complete)＋ゲート(tier/レート)＋status=pending→approvedフロー＋既存シードをapproved移行。（AIなしでも“投稿できる/弾ける”が成立）
- **P2 モデレーション**: 高速ルール＋hpmini worker→DGX(text)判定＋moderation_log＋`/admin/moderation`。frame(VL)は次。
- **P3 コメント**: comments＋スパム多層＋AI毒性/スパム。
- **P4 分析**: beat/event収集＋retention_daily集計＋`/studio`＋`/admin/analytics`。
- **P5 経済統合**: MORMステーク→上限解放＋スラッシュ、trust_score報酬連動。
- **P6 frame AI**: Qwen2.5-VL でrating自動付与＋CSAM/実暴力検出。

## 確定パラメータ（2026-08-07・スケール前提で決定）

- **ステーク（B→C）**: 立ち上げは固定・実効ボンド **T2=5,000 MORM($50) / 無制限=50,000 MORM($500)**。ボンドは違反なければ返却。規模が出たら **"$50相当"の価格連動USDペッグ** に移行（更新ジョブ実装）。
  - **スラッシュ**: スパム/軽微 10–25% ／ 違法・重大 100%＋BAN ／ **累進（違反ごと倍・再ステークは倍額）**。没収分は報酬プールへ。
- **年齢ゲート（D 地域別ハイブリッド）**: 既定=自己申告(18+チェック＋生年月日→m0r年齢フラグ端末保持・再確認不要)。**規制強地域(英OSA/一部米州/EU)はIPジオ判定で第三者年齢認証(Yoti/AgeChecked等・属性のみ)を強制**。地域ルールは後付け可能な設計にしておく（ジオ→ポリシーのマップをconfig化）。
- **CSAM（D→A）**: 立ち上げは **Qwen2.5-VL(frame)＋人手キュー＋通報** で運用。**CF CSAM Scanning Tool（無料・NCMEC連携）を早期有効化**（全ドメインCF配下＝追加インフラほぼ不要）。発見＝即ブロック＋（米ホスティング該当時）NCMEC通報フローを`moderation_log`と連動。将来は投稿量に応じ PhotoDNA/NCMEC直提携へ。
