# Phase 25-Video — Video Pipeline Standardization (HLS/CMAF + Edge + 任意CDN)

> **命名注**: `morm-l1/ops/QUIC-DESIGN.md` は同じ Phase 25 番号で「QUIC gossip transport
> 置換」を扱う (25a/25b/25c)。両者は独立並行進行可能なため、本ドキュメントは
> **Phase 25-Video** (字尾サフィックス `-Video`) として QUIC 系列と区別する。
> 内部 phase 番号は **25Va / 25Vb / 25Vc** (V = Video) と表記する。
> 単に「Phase 25」と書く文書では QUIC 置換を指すこと。

> 「動画を画像に偽装する」のではなく、**動画を "キャッシュしやすい静的セグメント" として配信する**。
> MORM の Phase 1/3/6/22 は既に同じ思想で構築されているが、独自 WebM Cell 形式が
> モバイル native 再生・業界ツール互換・標準的 CDN の恩恵を阻害しているため、
> Phase 25 で **HLS/CMAF (.m4s)** に置き換える。

## 0. Status

This is a **design document**. No code is changed yet. Phase 25-Video is
scoped as 25Va–25Vc below; each phase is independently shippable.

> **Last sync: 2026-04-30** (Phase 25Va/Vb/Vc + 22-Video 着地後 + portrait 9:16 pivot)

### 0.3 Portrait camera-first upload UI (2026-04-30)

Feed (consumer side) と対をなす **creator side** を完成。`/upload` の UI を従来の
drag-drop file 専用から **camera-first 9:16 録画 → upload** に書換。

`upload.html`:
- 9:16 portrait preview frame (`aspect-ratio: 9/16; max-width: 420px`) を中央に固定
- 単一 primary `.action` ボタン (height 56px, cyan/red 切替) が状態遷移の唯一のエントリ
- secondary row: `Flip camera` / `Discard clip` / `▶ Feed` リンク
- file drop fallback (デスクトップ + getUserMedia 失敗時用) は小さく下に残置
- `.rec` badge は録画中だけ pulse animation

`upload.js` の状態機械:
```
idle → "Start camera"  → live      (getUserMedia 9:16 hint, facing=environment)
live → "Record"        → recording (MediaRecorder mp4/webm 自動選択, 250ms timeslice)
recording → "Stop"     → captured  (Blob を url-encode して preview ループ再生)
captured → "Upload"    → uploading (POST /api/video/upload + 800ms job poll)
uploading → done       → done       ("▶ Play <cid>" リンクが有効化)
done → "Record another" → live
```

MIME 選定は MP4/H.264 を最優先 → WebM/VP9 → WebM/VP8 fallback。
`MediaRecorder.isTypeSupported()` で実機サポート確認。

`Flip camera` は `facingMode: user ↔ environment` トグル + 既存 stream 解放→再取得。
`MAX_RECORD_MS = 60_000` で長尺の暴走を防止。

**E2E 検証**: preview で `/upload` 画面がレンダリングされ、frame ratio = 0.563 (=9/16)、`Start camera` ボタンが idle 状態、9:16 badge 表示確認。`MediaRecorder` + `getUserMedia` 両方サポート確認済み。fake mp4 の POST /api/video/upload で job 受理 + encode 起動を確認 (Phase 25Vb 既存 pipeline が portrait UI からそのまま動作)。

### 0.2 Swipe feed (2026-04-30)

Portrait pivot に続けて player UX を **TikTok/Reels 風の縦スクロールフィード** に再構成。

`player-hls.html` は `<div class="feed">` 1 個に `<article class="feed-item">` を contents 数だけ並べる構造。CSS は **scroll-snap native のみ** で gesture 処理:

```css
.feed { height: 100vh; overflow-y: scroll; scroll-snap-type: y mandatory; }
.feed-item { height: 100vh; scroll-snap-align: start; scroll-snap-stop: always; }
```

ブラウザの mouse-wheel + touch swipe が card 単位の snap を自動でやる。
JS gesture lib も `pointerdown/move/up` の自前 swipe 実装も不要。

`player-hls.js` は `IntersectionObserver({ root: feedEl, threshold: [0, 0.6, 1.0] })` で
intersectionRatio > 0.6 の item を "active" 認定 → `activate(cid, videoEl)`:
1. 既存 `activeHls.destroy()` + `activeVideo.pause()/removeAttribute('src')/load()` で完全解体
2. `setP2PContent(cid)` で P2P announce を新 cid に切替
3. 新 video element に hls.js mount + LOAD/FRAG_LOADED hook で `rememberSegment` + `tryClaim`
4. ABR ラベルは `Math.min(width, height)` で `1080p` 表記

**ライフサイクル不変条件**: 同時に live な hls.js は最大 1 個 + 動画再生も active item のみ。
スクロール O(N) でも live メディアパイプは O(1)。

各 card の右下 HUD overlay (`.item-hud`) は `cid / level / seg / claims / p2p / peers / ice`
を 1秒ごとに更新。トップバー (`.topbar`) は identity + balance + `portrait feed` pill を常駐。
右端の `.pager` は contents 数の dot を縦並びにし、active 位置をハイライト。

**E2E 検証**: 4 contents (legacy landscape + portrait + auto-cropped portrait + 旧 portrait) の feed → IntersectionObserver で active=0 から開始、`scrollIntoView` で c88e6cc025e42123 (portrait) に jump → activeIdx=3, videoSize=1080×1920, prev item の `src` 解除確認。screenshot で TikTok 風 frame + bottom HUD overlay 視覚確認。

### 0.1 Portrait pivot (2026-04-30)

ユーザ意思決定により MORM は **mobile-first / 縦型 9:16 専用** に方向転換。
TikTok / Reels / Shorts 路線で、ABR ladder と player UI を完全に portrait に
切り替えた:

| ladder name | dimensions | aspect | bitrate (video) |
|---|---|---|---|
| 1080p | 1080×1920 | 9:16 | 5000k |
| 720p  |  720×1280 | 9:16 | 2500k |
| 480p  |  480×854  | 9:16 (≒) | 1000k |
| 360p  |  360×640  | 9:16 | 600k |

ladder 名は **shorter dimension** (= 横幅) を採用。これは ABR / hls.js が
扱う `RESOLUTION` の "shorter" を直感的に示し、且つ `1080p/seg_*.m4s` 等の
URL パスが portrait 切替後も互換のまま通る。

`hls_encoder.py` の filter chain は
`scale=w:h:force_original_aspect_ratio=increase,crop=w:h` で **入力が
landscape でも自動で 9:16 center-crop** する。1920×1080 の testsrc を
入力すると、出力 1080p の init.mp4 は確かに 1080×1920 になることを
2026-04-30 の検証で確認 (`/tmp/morm-25va-portrait/`)。

`player-hls.html` は `.wrap { max-width: 420px }` + `video { aspect-ratio: 9/16; max-width: 420px; object-fit: cover }` で **デスクトップでも phone 幅** に固定。
`<h1>` に `portrait 9:16` pill を追加して mode 識別。
`player-hls.js` の LEVEL_SWITCHED ラベルも `Math.min(width, height)` で表示することで `1080p · ...kbps` の馴染みのある表示を維持。

> **3原則チェック (`feedback_morm_design.md`)**
> 1. **「最初の統合者」**: HLS は Apple 2009、MPEG-DASH は ISO/IEC、ABR は MPEG-DASH。
>    MORM は「Walletless ID × Per-cell視聴報酬 × V-Hash 改ざん検知 × HLS互換セグメント」の
>    **統合者** として位置づける。HLS そのものは MORM の発明ではないことを章末注釈で明示。
> 2. **MORM単一ブランド**: `MORM Cell` → `MORM HLS Cell` (segment) に名称統一。
>    "CMAF Lite" 等のサブブランド禁止。
> 3. **法人なし**: CDN は **opt-in 高速化層** であり、Edge Node 自前運用が標準パス。
>    Cloudflare/AWS への依存はホスティング選択肢の1つとして文書化、必須ではないと明記。

---

## 1. Why migrate from WebM Cell

### 1.1 What's working today (Phase 1/3/6/22)

| 機能 | 現状 | 評価 |
|---|---|---|
| 動画分割 | 3秒WebM Cell, content-addressed by V-Hash | ✓ コンセプト正しい (~IPFS CID) |
| 改ざん検知 | V-Hash (pHash 64bit + 音声FP) per cell | ✓ 業界標準なし、MORMオリジナリティ |
| 配信 | morm-player Edge Node (origin/mirror-a/-b) HTTP Range | ✓ 動作するが地理分散なし |
| キャッシュ | Service Worker stale-while-revalidate | ✓ ブラウザ層は十分 |
| P2P | WebRTC mesh + DataChannel (Phase 22) + TURN (Phase 22b) | ✓ むしろ業界先行 |
| 視聴報酬 | per-cell VIEW_REWARD tx (Phase 11d, 1 µMORM/unique cell) | ✓ MORMオリジナリティモート |

### 1.2 Where WebM Cell hurts

- **iOS Safari**: WebM 公式サポートなし。HLS は `<video src="*.m3u8">` で native 再生。
  スマホ実機検証で MORM の最大の障壁。
- **業界ツール**: hls.js / shaka-player / ffmpeg packaging / Mux / Cloudflare Stream
  すべて HLS/DASH 前提。MORM 独自形式だと採用障壁が異常に高い。
- **CDN**: 既存 CDN の動画最適化機能 (Range chunking, ABR fallback, edge transmuxing) が
  HLS/CMAF 以外では効かないか限定的。
- **ABR (Adaptive Bitrate)**: 現状 MORM は単一品質。1080p / 720p / 480p / 360p
  切替がないと帯域変動環境 (モバイル) で再生破綻。
- **HLS が CMAF と統合**: 1つの .m4s セグメントで HLS + DASH 両方の再生可能。
  業界標準フォーマット 2 つに同時対応できる。

### 1.3 What we explicitly keep

- **3秒分割粒度**: HLS の典型 GOP は 6 秒だが、MORM の 3 秒は VIEW_REWARD の
  粒度・P2P再配布の最小単位として核。**Cell ≒ 1〜2 個の HLS segment** にマップ。
- **V-Hash per cell**: HLS .m4s の代わりにcoreは変わらない。pHash + 音声FP は
  segment 単位で計算可。改ざん検知ロジックそのまま流用。
- **Walletless ID + 視聴報酬**: segment 単位で観測 → tx 発行のフロー不変。
- **P2P WebRTC mesh**: cell の binary 配信ではなく segment binary 配信に切替えるだけ。
- **Edge Node 自前運用**: nginx / Caddy が `.m3u8` / `.m4s` を直接配信できる。
  CDN 不要で動く設計を維持。

---

## 2. Goals / non-goals

**Goals:**

1. **iOS Safari + Android Chrome native 再生** を `<video>` タグだけで成立させる。
2. **ABR**: 1080p / 720p / 480p / 360p の 4 ladder で帯域に応じた自動切替。
3. **業界ツール採用パス**: hls.js / shaka-player / ffmpeg / mediainfo / 任意 CDN が
   そのまま動く形式に。
4. **既存 Phase 11d (VIEW_REWARD), Phase 14 (Generation ID), Phase 22 (P2P) との互換**:
   HLS segment URL = content-addressed by V-Hash、txフロー不変。
5. **CDN は opt-in**: Edge Node 自前運用が標準パス、CDN は performance 加速層。

**Non-goals (Phase 26 以降):**

- DRM (EME / FairPlay / Widevine) — 著作権保護が必要なら別Phase。
- Live streaming (low-latency HLS / CMAF Chunked Transfer) — MORM は VOD 中心。
- Cloud transcoding service 連携 (Mux / Cloudflare Stream API)。
- WebTorrent / IPFS Gateway 統合 — Phase 22 P2P で十分カバー、CDN 補助は将来。

---

## 3. Architecture

```
[User Browser / iOS Safari / Android Chrome]
   │  hls.js / native HLS
   ▼
[CDN edge cache] ◄─ optional (Cloudflare R2 / Bunny / 自前 nginx)
   │
   ▼
[Origin Shield / Mid Cache] ◄─ optional (CloudFront Origin Shield 等)
   │
   ▼
[MORM Edge Node (morm-player/server.py)]
   │  serves .m3u8 + .m4s with proper Content-Type + Cache-Control
   ▼
[Object Storage (S3互換) or Local FS]
   │
   ▲
[Encoder Worker (FFmpeg + morm-core/encoder.py)]
   │
   ▲
[Upload API (passkey gateway POST /api/video/upload)]
```

### 3.1 Layers

| Layer | 責務 | Phase |
|---|---|---|
| **Upload API** | passkey 認証, multipart upload, ジョブキュー投入 | 25Vb |
| **Encoder Worker** | FFmpeg で ABR 4 ladder + HLS packaging + V-Hash 計算 | 25Va |
| **Object Storage** | S3互換 (Cloudflare R2 / Backblaze B2 / 自前 MinIO) | 25Vb |
| **Origin (MORM Edge Node)** | nginx-style serve `.m3u8` + `.m4s`, Range OK, CORS | 25Va |
| **CDN edge** | 任意。Cache Rules で `.m4s` を長期キャッシュ | 25Vc (opt-in) |
| **Player** | hls.js + 既存 morm-player JS の cell hook → segment hook | 25Va |
| **Chain integration** | content_id → master.m3u8 URL マッピング, segment_v_hash → VIEW_REWARD | 25Va |

### 3.2 ファイル構成

```
content_<v-hash-32hex>/
  master.m3u8                                # bandwidth ladder
  1080p/
    index.m3u8                               # segment list
    init.mp4                                 # CMAF init segment
    seg_00001.<seg-v-hash-16hex>.m4s         # 3-6 sec each
    seg_00002.<seg-v-hash-16hex>.m4s
    ...
  720p/
    index.m3u8
    init.mp4
    seg_00001.<seg-v-hash-16hex>.m4s
    ...
  480p/ ...
  360p/ ...
```

ファイル名にセグメントの V-Hash を埋め込む (`seg_00001.abcd1234.m4s`) ことで:
- CDN purge を打たずにバージョン更新できる
- content-addressed の整合性チェックがファイル名だけで可能
- VIEW_REWARD tx で `cell_index + segment_v_hash` の両方を載せられる (改ざん検証)

---

## 4. Migration phases

各 Phase は独立して shippable。Phase 1-22 と並行稼働させ、新規アップロードから
HLS 化する形で漸進的に移行する。

### Phase 25Va — Encoder + Player + Origin (~10h)

**Encoder Worker** (`morm-core/morm_core/hls_encoder.py` 新規):

- 入力: 任意の動画ファイル (`.mp4`, `.mov`, `.webm`)
- 出力: `master.m3u8` + 4 解像度の `index.m3u8` + 全 `.m4s` + `init.mp4`
- 実装: FFmpeg 1コマンドで ABR + HLS packaging:

```bash
ffmpeg -i input.mp4 \
  -filter_complex "[0:v]split=4[v1][v2][v3][v4];\
                   [v1]scale=1920:1080[v1080];\
                   [v2]scale=1280:720[v720];\
                   [v3]scale=854:480[v480];\
                   [v4]scale=640:360[v360]" \
  -map "[v1080]" -map a:0 -c:v:0 libx264 -b:v:0 5M  -c:a:0 aac -b:a:0 192k \
  -map "[v720]"  -map a:0 -c:v:1 libx264 -b:v:1 2.5M -c:a:1 aac -b:a:1 128k \
  -map "[v480]"  -map a:0 -c:v:2 libx264 -b:v:2 1M   -c:a:2 aac -b:a:2 96k  \
  -map "[v360]"  -map a:0 -c:v:3 libx264 -b:v:3 600k -c:a:3 aac -b:a:3 64k  \
  -f hls \
  -hls_time 3 \
  -hls_segment_type fmp4 \
  -hls_flags independent_segments \
  -master_pl_name master.m3u8 \
  -hls_segment_filename "%v/seg_%05d.m4s" \
  -var_stream_map "v:0,a:0,name:1080p v:1,a:1,name:720p v:2,a:2,name:480p v:3,a:3,name:360p" \
  "%v/index.m3u8"
```

- **V-Hash per segment**: 各 `.m4s` を読み込んで Phase 1 の `vhash.py` で計算、
  ファイル名に `seg_00001.<v-hash>.m4s` として埋め込み + manifest に記録。

**Origin (`morm-player/server.py` 拡張)**:

- 既存の cell endpoint (`/api/cell/...`) はそのまま (互換性維持)
- 新規: `/api/video/<content_id>/master.m3u8` → master playlist
- 新規: `/api/video/<content_id>/<resolution>/<filename>` → segment / sub-playlist / init
- **Content-Type 厳守**:
  - `.m3u8` → `application/vnd.apple.mpegurl`
  - `.m4s` → `video/iso.segment`
  - `init.mp4` → `video/mp4`
- **Cache-Control**:
  - VOD `.m3u8` → `public, max-age=300`
  - `.m4s` (immutable) → `public, max-age=31536000, immutable`
  - `init.mp4` → `public, max-age=31536000, immutable`
- **CORS**: 既存と同じ `Access-Control-Allow-Origin: *`

**Player (`morm-player/static/`)**:

- 新規 `/player-hls` ルート (既存 `/player` と並行)
- hls.js を CDN から読み込み (`https://cdn.jsdelivr.net/npm/hls.js@latest`)
- `<video>` 要素 + iOS native HLS / その他 hls.js fallback:

```javascript
const video = document.getElementById('v');
const src = `/api/video/${contentId}/master.m3u8`;
if (video.canPlayType('application/vnd.apple.mpegurl')) {
  video.src = src;        // iOS Safari native
} else if (Hls.isSupported()) {
  const hls = new Hls();
  hls.loadSource(src);
  hls.attachMedia(video);
}
```

- **既存 Phase 11d VIEW_REWARD 結線**: hls.js の `FRAG_LOADED` イベントで
  segment ごとに `Transaction.view_reward(content_id, cell_index)` を
  passkey で署名・送信。`cell_index = HLS segment number`。

**Chain integration** (`state.py`, 微小変更):

- `contents.root_hash` の意味を「cell マニフェストのハッシュ」から
  「master.m3u8 のハッシュ」に拡張 (両方 hex 32 bytes なので互換)。
- `VIEW_REWARD.payload.cell_index` は既存と同じ semantics、segment 番号として再解釈。
- 既存の `views` テーブルそのまま使える (viewer + content_id + cell_index の
  triplet UNIQUE 制約が segment 単位の重複防止になる)。

**検証**:

- 1ファイル動画 (10秒の.mp4) を encoder にかけ、`master.m3u8` + 4 ladder + 4 segments × 4 = 16 files が
  生成されることを確認。
- iOS Safari (実機) と Chrome desktop (hls.js) で再生できることを確認。
- 再生中の各 segment 視聴で VIEW_REWARD tx が L1 に届き、views テーブルに記録されることを確認。

### Phase 25Vb — Object Storage + Upload pipeline (~8h)

**Object Storage**:

- 標準サポート: **S3 互換 (AWS S3, Cloudflare R2, MinIO, Backblaze B2)**
- 抽象レイヤー: `morm-player/storage.py` (新規) で boto3 ベースの簡易ラッパー。
  ローカルFS と S3互換を同じインターフェースで切替可能 (env `MORM_STORAGE_BACKEND=fs|s3`)。
- 利用例: アップロード後、encoder worker が R2 bucket に `.m3u8` + `.m4s` を put。
  Origin は R2 から直接配信 (presigned URL or proxy)。

**Upload API**:

- 新規: `POST /api/video/upload` (passkey 認証必須)
  - multipart/form-data で `file=<原本動画>` + `metadata=<json>`
  - 受信完了後、ジョブキューに encoder ジョブを enqueue
  - response: `{ content_id, status: "queued", job_id }`

**Job Queue**:

- 軽量な選択肢: Python `redis-py` + `RQ`、または `arq`。
- 重量級は不要 (MORM 個人 PoC スケール)。
- ジョブ進捗を `/api/video/<content_id>/status` で polling できるようにする。

**検証**:

- Mac Mini に Redis + RQ worker 起動、MacBook からアップロード → R2 に格納 → 再生確認。

### Phase 25Vc — CDN integration (opt-in, ~6h)

**CDN 候補 (推奨順)**:

| CDN | コスト感 | MORM とのフィット |
|---|---|---|
| Cloudflare R2 + Cloudflare CDN | egress 無料、安価 | ◎ R2 storage と CDN が統合 |
| Bunny CDN + Backblaze B2 | $0.005/GB | ◎ 安価で動画特化 |
| AWS CloudFront + S3 + Origin Shield | 中庸 | ○ 機能豊富、複雑 |
| Cloudflare Stream | 動画分:$5/1000min保存, $1/1000min配信 | △ 統合が楽だが MORM の content-addressed と摩擦 |

**設計判断**: Phase 25Vc の標準推奨は **Cloudflare R2 + Cloudflare CDN**。
- R2 は egress 無料のため運用コスト圧縮
- CDN Cache Rules で `.m4s` を `Edge TTL = 1 year` 設定可能 (`max-age=31536000` を尊重)
- 「法人なし」 3原則との緊張: Cloudflare 単一企業依存。逃げ道として **Origin (Edge Node 自前) のみで動く構成を保証**。

**Cache 戦略**:

```
.m3u8 (master)        → CDN edge TTL = 5 min  (再エンコード時のみ更新)
.m3u8 (sub-playlist)  → CDN edge TTL = 5 min
.m4s + init.mp4       → CDN edge TTL = 1 year + immutable
```

**Origin Shield** (Phase 25c+ オプション):
- CloudFront Origin Shield や Cloudflare Tiered Cache で中間キャッシュ層を追加。
- 人気動画の最初のヒットで Origin (MORM Edge Node) を一回しか叩かないようにする。

**ウォームアップ** (公開直後):
- master.m3u8 + 各解像度の index.m3u8 + 先頭 5 segments を curl で CDN 経由 GET。
- Phase 25Vc の `morm-l1/ops/warm-up.sh` として実装。

**検証**:
- Cloudflare Tunnel 経由で R2-backed origin を公開、`chrome://media-internals` で
  CDN ヒット率と segment 配信遅延を測定。

---

## 5. Tx-format changes (minimal)

既存 tx kind を**変更しない**。新フィールドを optional で追加するだけ。

| Tx | 変更点 | 互換性 |
|---|---|---|
| `REGISTER_CONTENT` | `payload.master_playlist_hash` を optional 追加 (= sha256 of `master.m3u8`)。既存 `root_hash` は cell manifest 用に維持 | ✓ 旧 tx も valid |
| `VIEW_REWARD` | `payload.segment_v_hash` を optional 追加 (改ざん検知用)。なくても従来動作 | ✓ |
| `POST_JOB` | encoder job のメタデータ (resolution ladder, bitrate) を `payload.spec` に追加 | ✓ optional |

---

## 6. Spec-aligned principles (誇大せずに主張)

`feedback_morm_design.md` 3原則 + `RESEARCH_ORIGINALITY.md` の Prior Art と整合する Phase 25 の表現:

| 主張 | 正しい表現 | 禁止表現 |
|---|---|---|
| 動画分割 | "MORM は HLS/CMAF segment を Walletless ID + V-Hash + Per-segment視聴報酬と統合した最初の実装" | "MORM が動画分割配信を発明した" |
| ABR | "業界標準の MPEG-DASH/HLS ABR を MORM Chain と統合" | "MORM ABR (HMAR)" 等のサブブランド名 |
| CDN | "Edge Node 自前運用が標準パス、CDN は任意の高速化層" | "MORM は Cloudflare/AWS が必須" |
| 改ざん検知 | "V-Hash + Per-segment 検証は MORM 固有 (Numbers Protocol / C2PA は file 単位)" | "改ざん検知 AI を MORM が世界初開発" |

---

## 7. Estimated effort

| Phase | Code | Tests | Verification | Total |
|---|---|---|---|---|
| 25Va (Encoder + Player + Origin) | 6 | 2 | 2 | **10 h** |
| 25Vb (Object Storage + Upload) | 4 | 2 | 2 | **8 h** |
| 25Vc (CDN integration, opt-in) | 3 | 1 | 2 | **6 h** |

合計: **~24 h**。Phase 24c/24d/QUIC との並行進行可。Phase 25Va だけでも
iOS native 再生 + ABR が手に入るので最小可動価値が高い。

## 8. Open questions

1. **Cell vs Segment 命名**: 内部コードでは `cell` と `segment` のどちらを正にするか。
   提案: chain-side (state.py の views テーブル等) は `cell_index` のまま、
   media-pipeline 側 (encoder, player) は `segment` に統一、両者は同じ整数値を指す。

2. **既存 Phase 1 WebM Cell コンテンツの扱い**: 既存 PoC の WebM cell コンテンツを
   HLS に再エンコードするマイグレーションスクリプトを書くか、それとも新規アップロードのみ
   HLS にして共存させるか。提案: 後者 (共存)、`contents.root_hash` の prefix で判別。

3. **`init.mp4` の content-addressing**: `.m4s` セグメントは V-Hash でアドレス可能だが、
   `init.mp4` (CMAF init segment) はメディア内容を持たないので別ハッシュが必要。
   提案: SHA256(init.mp4) を `contents.payload.init_hash` に記録。

4. **モバイル recording 統合 (Phase 16a/b)**: ブラウザで録画 → 即 HLS 化のリアルタイムパスは
   Phase 25 で扱うか、Phase 16 の延長で扱うか。提案: Phase 25 では VOD のみ、
   recording は Phase 16 + 25 の交差点として別タスク。

5. **VIEW_REWARD のサンプリング**: 1080p で 1分動画 = 20 segments。視聴者ごとに
   20 tx 飛ぶのは finality と finality_depth=3 ですぐ詰まる。提案: サンプリング (10秒に1回) または
   バッチ tx (Phase 26 候補)。Phase 25 の段階では小規模 PoC なので問題化しない。

## 9. Relation to other Phases

- **Phase 11d (Player ↔ Chain)**: 結線そのまま流用。`cell_index` → segment 番号として解釈。
- **Phase 14 (AI Generation ID)**: master.m3u8 のメタデータに `generation_id` を埋める。
  AI service signature の検証フロー不変。
- **Phase 16a/b (real camera + screening)**: 録画動画を HLS encoder にかけてアップロード。
  `cut_score` 検証は HLS segment 単位で実施可能 (デモコードに追加)。
- **Phase 22/22b (P2P + TURN)**: WebRTC で配信する binary を `.cell` から `.m4s` に変更。
  チャンクサイズと chunked transfer は変わらない。
  → **Phase 22-Video (2026-04-30 着地)** で実装完了:
  `morm-p2p.js` の announce/serve key を `cell_index:int` から `seg_id:string`
  (`"<ladder>/<file>"`) に切替、cache 名は `morm-cells-v1` → `morm-hls-v1`、
  `player-hls.js` の hls.js `fLoader` 経路で **opportunistic P2P first-try → origin
  fallback** wiring 済 (`buildP2PLoader(Hls)` 参照)。HUD に
  `p2p-hits/bytes/peers/ICE` pill 追加。デバッグ用の `?p2p-debug=1` で
  signal/PC state log を有効化、`?force-hlsjs=1` で iOS Safari でも custom loader
  経路を強制可能、`?morm-peer=<id>` で multi-iframe テスト用に peer id を override 可。
  実装中に発見した bug: (1) inbox poll が `for(...) handleSignal(m)` で並列 dispatch
  され、ICE handler が offer handler の `setRemoteDescription` 完了前に
  `addIceCandidate` を呼んで silently drop していた → sequential `await` 化、
  (2) 失敗した `RTCPeerConnection` を `outgoingPCs` に持ち続けるため、retry でも
  fresh handshake が走らずすぐ timeout していた → connectionState 監視 + timeout 時
  `dropOutgoing(peer_id)` で復旧。POLL_INTERVAL_MS は 800ms → 200ms に短縮
  (handshake roundtrip < 2s)。
- **Phase 24a/b (DAG)**: 関係なし、独立して進行。
- **Phase 26 (セキュリティ)**: 署名付きURL / Token認証 / Referer制限 / DRM は Phase 26 へ。

## 10. Demo flow (Phase 25 完了後の想定)

```
1. ユーザーが iOS Safari で /player-hls を開く
2. Passkey ログイン (Phase 7)
3. <video src="/api/video/<cid>/master.m3u8"> が native HLS で再生開始
4. hls.js (or native HLS) が 1080p からスタート → 帯域に応じて 720p/480p に切替
5. 各 segment 視聴ごとに passkey 署名 VIEW_REWARD tx が L1 に飛ぶ
6. balance HUD が cell ごとに +1 µMORM
7. P2P mesh (Phase 22) で他の視聴者から segment を直接受信 (cell hit カウンタ表示)
8. 改ざんされた .m4s を含む CDN を試すと V-Hash 不一致で即拒否、再生停止
```

これで「合法な分散動画SNS + 視聴者参加報酬 + 改ざん耐性 + モバイル native」を
**業界標準フォーマット + MORM固有のオリジナリティ** で同時に実現する。

---

## 11. Migration risks & mitigations

| Risk | Mitigation |
|---|---|
| FFmpeg encoder が CPU重い | バックグラウンド queue + ジョブ並列度制限 (Phase 25b) |
| HLS で Range request が CDN ABR と衝突 | Cache-Control を厳格に、master.m3u8 のみ短期 TTL |
| iOS の native HLS は機能制限あり (DRM等) | hls.js fallback で feature parity |
| WebRTC P2P と CDN edge cache の二重配信 | morm-p2p.js が CDN を first-try、P2P を opportunistic に保つ (Phase 22-Video の `buildP2PLoader` で実装: P2P を 1500ms 試行 → miss なら `super.load` で origin/CDN にフォールバック、1度 fetch した segment は `morm-hls-v1` cache に積んで他 peer に配信可能) |
| ABR 4 ladder で stoarge 4倍 | Phase 25Vb で R2 (egress無料) 利用、cold storage 移動 (Phase 25c+) |
| 既存 WebM cell コンテンツの非互換 | 共存運用、`contents.root_hash` prefix で判別 |
