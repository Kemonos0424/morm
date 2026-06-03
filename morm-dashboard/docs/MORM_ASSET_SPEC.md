# MORM ダッシュボード — アイコン / フレーム / 画像アセット設計指示書

> 目的: MORM ノードダッシュボードの全ビジュアルアセットを、MORM の公式ブランド
> （Swarm = 群れ／霧）とダッシュボードの Web3 グラスモーフィズム UI に整合した形で
> 一括生成するための、生成者向け詳細スペック。**この MD だけで生成に着手できる**
> ことを目標に、各アセットの寸法・形式・モチーフ・カラー・生成手法・プロンプトを定義する。

---

## 0. なぜ作り直すか（背景）

- 既存 `public/icons/` は旧 **CLT** 時代の素材で、トークンアイコンが `clt-token.svg` /
  `clt-token-sm.svg`、ロゴ文言が「Node Dashboard」のまま。
- トークンは **CLT → MORM（単位 m0r、MORM L1 ネイティブ）** に完全置換済みなので、
  ビジュアルも MORM ブランドに合わせる。
- サードパーティのサービスマーク（`svc-x` / `svc-youtube` 等 8 点）は**他社商標なので変更不可**。
  本指示の対象外（既存のまま据え置き）。

---

## 1. MORM ブランド要約（公式 docs より）

| 項目 | 内容 |
|------|------|
| 名称の由来 | **M**emory + Swa**rm**（群れ）/ Momentum |
| タグライン | **The Swarm for Every Frame** — すべてのフレームに、群れの力を |
| 世界観 | 中央のダム（巨大サーバ）ではなく、**無数のノード（霧・群れ）**が必要な時に必要な分だけ動画と価値を運ぶ。形を持たないが確実にそこにある／止められない／消せない。 |
| キービジュアル指針（公式SNSキット） | 背景=**Void Black (#000)** または深いダークグレー／アクセント=**エレクトリックブルー・バイオレット・アンバー**／**粒子表現（Swarm）を必ず1要素以上**／フォント=幾何学的サンセリフ（Inter / Geist / Noto Sans JP） |

**最重要モチーフ = 「群れ（swarm）」**。点（ノード）の集合・粒子・有機的なネットワーク。
直線的な格子よりも、**密度の濃淡を持つ点群**で「霧／群れ」を表現する。

---

## 2. デザイン原則（ダッシュボードUIとの統合）

ダッシュボード `app/globals.css` は **ディープインディゴ背景のグラスモーフィズム Web3 テーマ**。
公式ブランドの「Void Black + 粒子」と統合するための合意ルール:

1. **ダーク前提**: アセットは `#0c0c1d`〜`#000` の暗背景に乗る。アイコン類は**背景透過**。
2. **フラット + グロー**: 厚いシャドウや3Dは使わない。線・面はフラット、状態表現は**ソフトな同心円グロー**（既存 `node-online.svg` 方式）。
3. **グラデーション基調**: 紫→青（`#8b5cf6 → #3b82f6`）を全体の連続性キーとして踏襲しつつ、
   **MORMトークン系のみアンバー（#fbbf24）**を主役にしてブランドの「価値／報酬」を差別化。
4. **幾何学サンセリフ**: 文字を入れる場合は Inter / Geist（数字・記号は等幅可）。`m0r` の「0」はゼロ（数字）で統一。
5. **線幅は viewBox に対して 1.2〜2.0**。小サイズ（16–24px）でも潰れない最小要素に。
6. **群れ要素を必ず1つ**: ロゴ・ヒーロー・OG・空状態など面積のあるアセットには粒子/点群を入れる。

---

## 3. カラーパレット（確定値）

ダッシュボードの CSS 変数と SNS キットを統合した**公式パレット**。新規アセットはここから選ぶ。

| トークン | HEX | 用途 |
|----------|-----|------|
| Void Black | `#000000` | OG/ヒーローの最深部 |
| BG Indigo | `#0c0c1d` | ダッシュボード標準背景 |
| BG Indigo 2 | `#111128` | セクション背景 |
| Violet（主） | `#8b5cf6` | グラデ始点・群れ粒子 |
| Blue（主） | `#3b82f6` | グラデ終点 |
| Accent Indigo | `#667eea` | UIアクセント（既存 `--accent`） |
| Accent Purple | `#764ba2` | グラデ（`--accent-gradient` 終点） |
| Cyan | `#00d2ff` / `#22d3ee` | 補助グラデ・データ流 |
| **Amber（MORM/m0r 主役）** | `#fbbf24` | トークン・報酬・価値 |
| Amber Deep | `#d97706` | アンバーグラデ終点 |
| Green | `#34d399` | オンライン・成功 |
| Red | `#f87171` | オフライン・失敗 |
| Text | `#e2e8f0` | 文字（明） |
| Text Muted | `rgba(255,255,255,0.4)` | 補助文字 |

**標準グラデーション定義（SVG 共通 `<defs>`）**

```xml
<!-- ブランド連続性: 紫→青 -->
<linearGradient id="g-brand" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0%" stop-color="#8b5cf6"/><stop offset="100%" stop-color="#3b82f6"/>
</linearGradient>
<!-- 3色フル（ヒーロー/見出し用） -->
<linearGradient id="g-tri" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0%" stop-color="#667eea"/><stop offset="45%" stop-color="#764ba2"/><stop offset="100%" stop-color="#00d2ff"/>
</linearGradient>
<!-- MORM トークン: アンバー -->
<linearGradient id="g-morm" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0%" stop-color="#fbbf24"/><stop offset="100%" stop-color="#d97706"/>
</linearGradient>
```

---

## 4. 形式・グリッド・書き出し規則

| 種別 | 形式 | 理由 |
|------|------|------|
| アイコン・ロゴ・ステータス・タスク・イラスト | **SVG**（背景透過） | スケーラブル・軽量・既存と同形式・コードで再現可能 |
| ヒーロー背景・OG画像 | **PNG**（不透明、暗背景込み） | グラデ/粒子の質感はラスタが有利。サイズ固定 |
| favicon | **.ico**（16/32/48 マルチ）+ 512 PNG | ブラウザタブ |

- **viewBox は正方を基本**（ロゴフルのみ横長）。サイズは現行資産に一致させる（後述の表）。
- SVG は `fill="none"` ルート、`<defs>` にグラデ、`stroke`/`fill` で `url(#…)` 参照。
- 余白（セーフエリア）: アイコンは viewBox の**外周 8%** を余白に。
- 命名は現行を踏襲（kebab-case、`.svg`）。**CLT 名は廃止**（下記マッピング）。

---

## 5. 共通モチーフ・ライブラリ

新規アセットは下記モチーフの組み合わせで構成する（一貫性の核）。

- **M-1 Swarm Node Cluster（群れノード）**: 3〜大量の円（ノード）を密度の濃淡で配置し、
  近接ノードを細線で結ぶ。中心ほど密、外周は疎で「霧」に溶ける。ロゴの核。
- **M-2 m0r Glyph**: 等幅/幾何サンセリフで `m0r`（小文字、0は数字ゼロ）。トークン円の中央に置く。
- **M-3 Particle Drift（粒子の流れ）**: 微小な点が一方向に流れる残像。データ/価値の移動を表す。背景・送金・claim系。
- **M-4 Glow Ring（同心円グロー）**: 状態表現。中心実円 + 外周に透明度を下げた2層リング。

---

## 6. アセット一覧（生成対象）

優先度 **A=ブランド根幹（最優先）／B=機能アイコン／C=イラスト・装飾**。
`svc-*`（8点）は対象外。

### 6-A. ブランド根幹（最優先）

| ファイル名 | 用途 | サイズ/viewBox | 形式 | モチーフ・指示 | カラー |
|------------|------|----------------|------|----------------|--------|
| `morm-token.svg`（新規, 旧 `clt-token.svg` 置換） | MORM トークン表示 | 48×48 | SVG | 外円リング2層 + 中央に **M-2 `m0r`**。背面に **M-3 粒子**を薄く。 | `g-morm`（アンバー主）。リング外側に violet を1%混ぜ可 |
| `morm-token-sm.svg`（新規, 旧 `clt-token-sm.svg`） | インライン小 | 24×24 | SVG | 上の簡略版。粒子省略、`m0r` は太字 or 円内ドット3つで代替 | `g-morm` |
| `logo.svg`（更新） | アプリロゴ（マーク） | 40×40 | SVG | **M-1 群れ**。現行の3円三角を核に、外周へ小ドット6〜10個を散らし「群れ／霧」を追加 | `g-brand` |
| `logo-full.svg`（更新） | ヘッダ横ロゴ | 200×40 | SVG | 左にマーク（上記）、右テキストを **「MORM」**（旧「Node Dashboard」廃止）。サブに小さく `Node Network` 可 | マーク=`g-brand`、文字=`g-tri` |
| `favicon.ico` + `favicon-512.png`（更新） | タブ/PWA | 16/32/48/512 | ico+png | `logo.svg` のマークを暗角丸正方（`#0c0c1d`）に乗せ、群れドットは2〜3個に簡略 | bg `#0c0c1d`、マーク `g-brand` |
| `og-image.png`（更新） | SNS OGP | **1200×630** | PNG | 背景 Void Black→Indigo グラデ + **M-3 粒子群**。中央〜左に「MORM」ロゴ + タグライン「The Swarm for Every Frame / すべてのフレームに、群れの力を」。右下に群れの密度ピーク | bg `#000→#0c0c1d`、文字白、粒子 violet/cyan、アクセント amber |
| `hero-bg.png`（更新） | トップ背景 | **1920×1080** | PNG | 抽象的な**群れ／霧のパーティクルフィールド**。中央上が明るく、外周は黒に減衰。UIテキストが乗るので**中央は低コントラスト**に保つ | `#000` ベース、violet→blue→cyan の星雲状、amber 微量 |

### 6-B. 機能アイコン

| ファイル名 | 用途 | サイズ | モチーフ | カラー |
|------------|------|--------|----------|--------|
| `node-online.svg`（据置/微調整） | ノード稼働 | 32 | **M-4** | green `#22c55e` |
| `node-offline.svg` | ノード停止 | 32 | M-4（暗く・脈動なし） | red/grey |
| `status-online.svg` / `status-offline.svg` | 小ステータス点 | 16 | 実円+1リング | green / grey |
| `wallet-icon.svg`（更新） | ウォレット | 32 | 財布シルエット + 中に `m0r` 粒 | `g-brand` + amber 粒 |
| `score-trophy.svg` | スコア | 32 | トロフィー + 群れドット | `g-tri` |
| `merkle-icon.svg` | L1 Proof | 32 | 二分木（ハッシュツリー）+ ルートが光る | `g-brand` |
| `pc-icon.svg` / `macmini-icon.svg`（据置） | ノード機種 | 32 | デバイス線画 | `g-brand` |
| `conn-tailscale/wireguard/ssh/local.svg`（据置） | 接続方式 | 24 | 既存線画 | `g-brand` |
| `chat-icon.svg` / `avatar-default.svg` / `arrow-up.svg`（据置） | UI部品 | 各 | 既存 | `g-brand` |

**タスクカテゴリ（10点・据置ベース、配色だけ統一確認）**
`task-site / task-sns / task-gmail / task-git / task-cloudflare / task-api / task-automation / task-p2p / task-storage / task-review` — 既存の線画を維持し、**全て `g-brand` で統一**されているか確認。されていなければ統一。

### 6-C. イラスト・装飾

| ファイル名 | 用途 | サイズ/viewBox | モチーフ | カラー |
|------------|------|----------------|----------|--------|
| `network-illustration.svg`（更新） | ネットワーク図 | 横長（例 320×200） | **M-1 群れを大規模化**。中央密→外周疎、線で結節 | `g-brand` + cyan データ流 |
| `network-map-bg.svg` | 地図風背景 | 全幅 | 点群を地図状に散布 + 微結線 | violet/blue 低彩度 |
| `claim-illustration.svg`（更新） | リワードClaim | 例 240×180 | **m0r コインが群れから1つ手元へ流れる**（M-3 + M-2） | amber 主 + violet 背 |
| `empty-state.svg`（更新） | 空状態 | 例 200×160 | 霧に消える疎な群れ + 一言余白 | grey + violet 微量 |

---

## 7. ラスタ生成プロンプト（PNG: og / hero / favicon-512）

> 生成エンジン（Gemini/Imagen 等）向け **英語プロンプト**。日本語文字は AI 生成だと崩れやすいので、
> **文字は後段で SVG/PNG オーバーレイ合成**する前提（プロンプトでは「leave clear space for text」と指示）。

**`hero-bg.png`（1920×1080）**
```
Abstract swarm particle field on pure black background, thousands of tiny glowing
dots forming an organic fog-like cloud, density peak slightly upper-center fading
to black at the edges, nebula of electric violet (#8b5cf6) blending into blue
(#3b82f6) and cyan (#00d2ff), a few rare amber (#fbbf24) sparks, soft bloom,
depth of field, no text, no logo, cinematic, ultra-clean, low contrast in the
center area so UI text stays readable, 16:9.
```

**`og-image.png`（1200×630）**
```
Dark social card, deep black-to-indigo (#000 → #0c0c1d) gradient background,
swarm of luminous particles drifting from left to a dense glowing cluster on the
right, electric violet and cyan with subtle amber accents, generous empty space
on the left-center for a wordmark and tagline, premium web3 aesthetic, soft glow,
no text rendered, flat, crisp, 1200x630.
```
→ 合成テキスト（別レイヤ）: 上段に **MORM**（白・Inter 700・大）、下段に
`The Swarm for Every Frame` ＋ 改行 `すべてのフレームに、群れの力を`（Text Muted）。
左下小さく `logo-full` を配置。

**`favicon-512.png`**
```
App icon, rounded-square dark indigo (#0c0c1d) tile, centered minimal swarm mark:
three nodes in a triangle connected by thin lines plus a few scattered small dots,
violet-to-blue gradient (#8b5cf6 → #3b82f6), soft outer glow, flat, no text, 512x512.
```

---

## 8. SVG 生成の雛形（コード生成の起点）

例: `morm-token.svg`（アンバー + m0r + 粒子）。これを基準に他アイコンも `<defs>` を共有。

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48" fill="none">
  <defs>
    <linearGradient id="g-morm" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#fbbf24"/><stop offset="100%" stop-color="#d97706"/>
    </linearGradient>
  </defs>
  <!-- 背面の粒子(M-3): 数個のドットを薄く -->
  <g fill="url(#g-morm)" opacity="0.25">
    <circle cx="9" cy="14" r="1"/><circle cx="40" cy="12" r="1.2"/><circle cx="38" cy="36" r="1"/>
  </g>
  <!-- トークン円(M-4 2層リング) -->
  <circle cx="24" cy="24" r="20" fill="url(#g-morm)" opacity="0.15"/>
  <circle cx="24" cy="24" r="20" stroke="url(#g-morm)" stroke-width="2" fill="none"/>
  <circle cx="24" cy="24" r="16" stroke="url(#g-morm)" stroke-width="0.5" fill="none" opacity="0.35"/>
  <!-- m0r グリフ(M-2) -->
  <text x="24" y="29" text-anchor="middle" font-family="Inter, system-ui, sans-serif"
        font-size="13" font-weight="700" fill="url(#g-morm)">m0r</text>
</svg>
```

例: `logo.svg`（群れ強化版・40×40）— 既存3円三角の外側に群れドットを追加:
```xml
<!-- 既存3ノード + 結線(url(#g-brand)) はそのまま流用 -->
<!-- 追加: 外周に散る群れドット(M-1) -->
<g fill="url(#g-brand)">
  <circle cx="6"  cy="6"  r="1.3" opacity="0.7"/>
  <circle cx="34" cy="5"  r="1.1" opacity="0.6"/>
  <circle cx="37" cy="22" r="1.4" opacity="0.7"/>
  <circle cx="5"  cy="24" r="1.1" opacity="0.55"/>
  <circle cx="30" cy="36" r="1.2" opacity="0.6"/>
  <circle cx="10" cy="35" r="1.0" opacity="0.5"/>
</g>
```

---

## 9. CLT → MORM 命名マッピング（参照更新も必要）

| 旧（廃止） | 新 | コード参照 |
|------------|-----|-----------|
| `clt-token.svg` | `morm-token.svg` | `app/my/page.js`, `app/my/rewards/page.js` 等で `<img src>` を更新 |
| `clt-token-sm.svg` | `morm-token-sm.svg` | 同上 |

> 生成後、`grep -rn "clt-token" app` でフロントの参照を新ファイル名に置換すること。
> `logo-full.svg` のテキスト「Node Dashboard」も「MORM」へ更新済みを確認。

---

## 10. ディレクトリ・命名規則

- 配置: `morm-dashboard/public/icons/`（現行どおり）
- ラスタも同ディレクトリ（`og-image.png` / `hero-bg.png` / `favicon-512.png`）
- 命名: kebab-case、機能を表す英小文字。トークンは `morm-`、状態は `node-`/`status-`、
  タスクは `task-`、接続は `conn-`、サービス（不変）は `svc-`。

---

## 11. 受け入れ基準（生成後チェックリスト）

- [ ] すべてのブランドアセットに**群れ／粒子要素**が最低1つ入っている
- [ ] トークン系（`morm-token*`）は**アンバー主役**、それ以外は紫→青グラデで連続性がある
- [ ] 16–24px でも要素が潰れない（最小円 r≥1、線幅 ≥1.2）
- [ ] 背景透過 SVG（ラスタのみ暗背景込み）／viewBox 正方（ロゴフル除く）
- [ ] `m0r` の 0 は数字ゼロ、フォントは幾何サンセリフ
- [ ] 旧 `clt-` 名が `public/icons/` とコード参照から消えている
- [ ] OG/ヒーローの中央は UI/テキストが乗る低コントラスト
- [ ] サイズが現行資産と一致（og 1200×630 / hero 1920×1080 / logo-full 200×40）

---

### 付記: 生成手法の使い分け（`generate-images` スキル想定）

- **SVG（アイコン/ロゴ/イラスト/タスク/ステータス）** → コード（手書き or スクリプト）で生成。
  本書の `<defs>` 雛形とモチーフ定義をそのまま使えば一貫性が担保される。
- **PNG（hero / og / favicon-512）** → 画像生成モデル（Gemini/Imagen）で §7 のプロンプト、
  日本語/ロゴ文字は SVG→PNG で**別レイヤ合成**（AI に文字を描かせない）。
- **favicon.ico** → `favicon-512.png` から 16/32/48 をダウンスケールしてマルチ ico 化。
