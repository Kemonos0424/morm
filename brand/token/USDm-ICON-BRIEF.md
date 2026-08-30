# USDm トークンアイコン制作ブリーフ（別セッション向け）

このファイルだけで作業を開始できるよう、事実・制約・成果物をすべて記載しています。
**目的**: MORM トークンと同じ「家族」に属しつつ、USD ステーブルコインだと一目で分かる USDm アイコンを作る。

---

## 0. 最初に必ず確認すること（ユーザーへ）

- ★過去に汎用的な "M" アイコン案は**却下**されている。「MORM のケース（機体）のモック」に忠実であることが必須。
- **作業前に、ユーザーへ「MORM のケース（機体）のモック画像」を出してもらう**か、既存の完成 MORM トークン画像を正とする（下記パス）。想像で作らない。
- 完成 MORM トークン（参照の正）:
  - ベクター: `brand/token/logo.svg`
  - ラスタ: `brand/token/morm-token-1024.png` / `morm-token-512.png` / `morm-token-256.png` / `morm-token-200.png`
  - 生成器（デザイン言語の定義そのもの）: `brand/token/make_token.py`, `brand/token/make_logo_svg.py`

---

## 1. USDm とは（アイコンに載せる事実）

- 名称: **MORM USD**、シンボル **USDm**、小数 **6 桁**（USDC と同じ）
- 実体: **native USDC を 1:1 で裏付けるトラストレス・ラッパー**（deposit で mint / withdraw で償還、admin 無し・完全裏付け）
- チェーン: **Base mainnet (8453)**
- コントラクト: `0xd65896532806030878DB852F3f5216Bc917FD376`
- 裏付け USDC: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- MORM L1 へは USDmLockBridge (`0x87cD170BA7a82a0049F2fF36aa926033A5f9C26e`) 経由で 1:1 ミラー
- 位置づけ: MORM エコシステムの「価値の基準（USD 建て表示・SHOP 値付け・安定資産）」

## 2. デザイン言語（MORM トークンから継承する = 変えない部分）

`make_token.py` 冒頭のパレット（実機ケース由来）をそのまま踏襲する:

| 役割 | 色 |
|---|---|
| ケース躯体 (main) | `#272B48`（NAVY） |
| リム/ハイライト | `#3A3F6C`（NAVY_HI） |
| 影側 | `#16192E`（NAVY_LO） |
| メッシュ穴 | `#0A0B18` |
| ブランド violet | `#6B2CE6` |
| ブランド magenta | `#EC1E79` |
| ライブ LED | `#FCC04F`（AMBER） |

継承する造形:
- 円形のディープインディゴ**ケース躯体**（molded case、外周ベベルリング、左上からの光源 `lx,ly=-0.62,-0.78`）
- 中央の**リセスした Voronoi / スウォームメッシュ**パネル（グリル面）
- 左上ハイライト → 右下シャドウの製品レンダ風シェーディング

## 3. USDm 固有（MORM と変える部分＝差別化）

**狙い**: 「MORM 家族の筐体だが、中身は USD（USDC 裏付け）」を視覚化する。

- 中央グリフ: MORM の "M" ではなく **"$" もしくは "US$" を、同じマゼンタ/バイオレットのグラデ**で刻む。
  - もしくは "m" を USD 記号と融合（`$` の縦棒を `m` の脚に見立てる等）。案を2–3出してユーザー選択。
- **アクセント色を USDC ブルー `#2775CA` に寄せる**（LED やリング、グリフのハイライトの一部）。これで「USDC 裏付け＝ドル」を示唆しつつ、躯体は MORM のインディゴを維持する。
  - ただしアンバー LED を消さず、"live" 感は残す（ブルー LED と併用 or どちらか。案出し）。
- 縁（またはグリフ下）に微細に **"USD" / "1:1"** の刻印を入れてもよい（可読性優先、必須ではない）。
- MORM 本体と**並べて区別がつく**こと（サムネイル 32px でも MORM と USDm が判別できる配色コントラスト）。

## 4. 成果物（MORM トークンと同じ構成で出力）

`brand/token/` 配下に、MORM と対になる命名で:

- `usdm-token-1024.png` / `usdm-token-512.png` / `usdm-token-256.png` / `usdm-token-200.png`
- `usdm-logo.svg`（ベクター・`logo.svg` と同系の作り）
- 生成器 `make_usdm_token.py`（`make_token.py` を複製・改変。再現性のため seed 固定）
- 背景透過（円の外は透明）。円形で、各種ウォレット/DEX のトークンアイコン枠に収まること。

さらに、DEX トークンリスト提出用（任意・将来）:
- `submissions/superchain-tokenlist/data/USDm/logo.svg` と `data.json`
  （既存 `submissions/superchain-tokenlist/data/wMORM/` を雛形にする）

## 5. 反映先（アイコン完成後に使う場所・参考）

- market.morm.one の SWAP/ブリッジ UI のトークンセレクタ（`morm-market/index.html`）
- ウォレット表示 / SHOP の USD 建て表示
- （将来）Base Superchain tokenlist

## 6. 完了条件

1. ユーザーが「ケースのモックに合っている」と承認した中央グリフ案を採用
2. 4 サイズ PNG + SVG + 生成器を `brand/token/` に出力
3. 32px サムネイルで MORM と USDm が判別可能
4. ユーザー最終承認

---
（作成: 2026-08-30 / 元セッションで USDm 双方向ブリッジ本番稼働・往復実証済。アイコンはブランド仕上げの最後のピース。）
