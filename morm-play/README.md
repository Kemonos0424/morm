# MORM Play — 動画ディスカバリ + 配信元秘匿プロキシ

**本番: https://play.morm.one** （2026-08-07 稼働）

`play_server.py` 1ファイル(stdlib のみ)に3責務を束ねる:

1. **カタログ** (SQLite `play_catalog.db`) — メディアメタ + 推薦ランキング(人気×時間減衰) + 検索 + いいね。
2. **★秘匿プロキシ `/m/<id>/...`** — 住宅edge(edge-mcXXXX.ctai.online)からHLSをサーバ側で取得し、
   プレイリスト内の全URLを `/m/<id>/` 相対へ書換、ノード識別ヘッダ(x-morm-edge等)を除去。
   クライアントには **play.morm.one しか見えず**、edgeのホスト/IP/実content-hash を一切露出しない。
   同一オリジン配信になるので旧・クロスオリジンMSE問題も解消。
3. **フロント `/`** — Pinterest風 masonry グリッド + 検索 + タグchip + HOT/NEW + モーダルhls.jsプレイヤー
   + いいね/シェア。ブランド=Vivid90s(light/dark対応)。生成的サムネ `/thumb/<id>.svg`。

## ファイル
- `play_server.py` — 本体(catalog/proxy/discovery/投稿/ゲート)
- `mormcrypto.py` — Ed25519 verify(純python)＋m0rアドレス導出(既存ウォレット互換)
- `DESIGN_posting.md` — 投稿/モデレーション/分析 設計書

## API — ディスカバリ/配信
- `GET /api/feed?sort=hot|new&q=&tag=&offset=&limit=` — ランキング(hot=`(likes*3+views*0.05)/(age_h+2)^1.5`)。**approvedのみ**
- `GET /api/content/<id>?uid=` — 詳細(+view) / `GET /api/tags` — 人気タグ
- `POST /api/like` `{id,account,sig?}` — いいねトグル(account単位重複防止)
- `GET /m/<id>/master.m3u8` 他 — ★秘匿HLSプロキシ(approvedのみ) / `GET /health`

## API — 投稿(P1・m0r Ed25519署名必須)
- `GET  /upload` — 投稿UI(WebCrypto Ed25519ウォレット内蔵)
- `GET  /api/me?pub=<hex>` — 口座ensure＋tier/limits/stake
- `GET  /api/mine?pub=<hex>` — 自投稿一覧(status付き)。★pubkey必須(IDOR封鎖: 公開アドレスm0rでは不可)
- `GET  /api/earnings?pub=<hex>` — 収益(views/likes/earned/pending)。★pubkey必須(IDOR封鎖)
- `POST /api/upload/init` `{kind:"upload.init",sender:<pubhex>,nonce,payload:{title,description,tags[],ar,duration,links[]},sig}` → 検証＋ゲート＋予約 `{id,token}`
- `POST /api/upload/<id>/media?token=` (生バイト) → hpmini gatewayでHLSエンコード→bind→`{status:approved|pending_review}`
- `POST /api/admin/ingest` `{token,play_cid,...}` — 実コンテンツ直投入(ADMIN_TOKEN)
- `GET  /api/admin/moderation/queue?token=` / `POST /api/admin/moderation/decide` `{token,id,decision:approved|rejected}`

## 投稿動画スペック / 変換
- 入力: MP4 / MOV / WebM / MKV など一般的な動画。gatewayが **アダプティブHLS(1080/720/480/360・H.264/AAC)へ自動変換**=正規化。
- 上限: ハード **512MB**（nginx client_max_body_size=512m）／最小1s／長さは tier 上限。
- **実尺・実解像度はサーバで確定**（`probe_encoded`= master RESOLUTION + variant EXTINF）。クライアント申告に依存せず encode後に tier 再検証（超過→rejected+strike）。

## モデレーション（非同期・テキスト＋映像フレーム）
- 投稿は encode+probe 後 **status='pending' で即返る**（DGX待ちなし）。
- **`mod_worker.py`** が `GET /api/mod/pull`→`moderation.moderate()`→`POST /api/mod/verdict`→`apply_verdict`。
  - **本番の実体は hpmini の systemd `morm-modworker.service`**（ffmpeg必須）。Mac Mini の launchd 版は `.disabled`。
  - `PLAY_URL`（play_server・既定 Mac Mini tailnet）/ `GATEWAY`（フレーム取得・hpmini localhost:8801）で疎結合。
- **映像フレーム判定（裏取り）**: `extract_frames`（HLS init+seg→ffmpeg 2枚JPEG）＋`analyze_frames`（**qwen2.5vl:7b** on dgx1）→ `{adult,nudity,csam_risk,real_violence,gore}`。統合は **severity上げ方向のみ**：危害はtext/frameのmax、映像 adult/nudity≥.5→rating r18、csam≥.5/violence≥.7→reject。→ SFW偽装タイトルの成人動画を検出しR18格上げ・人手キューへ。
  - env: `VL_MODEL`(既定 qwen2.5vl:7b) / `VL_OLLAMA`(既定 dgx1) / `FRAME_MOD`(on/off) / `FFMPEG`。
- 人手UI **`/admin/moderation`**（ADMIN_TOKEN・sessionStorage）: pending_review + pending キューを動画プレビュー付きカードで表示、AIラベルのバー、承認/却下。15秒自動更新。
- worker API: `GET /api/mod/pull?token=` / `POST /api/mod/verdict {token,id,verdict}`。暫定 `POST /api/admin/set-stake {token,m0r,staked_morm|trust_score}`（P5まで手動tier）。

## サンプル投入
- `samples/manifest.json`（20本・全ffprobe検証済）＋`seed_samples.py`（署名投稿・staked=自動承認/new=人手キュー）。`PLAY=… ADMIN=… [SKIP=N] python3 seed_samples.py`。

## カテゴリ別判定（DGX Ollama・moderation.py）
- `classify_and_judge`= **DGX AI**（dgx1/dgx2 Ollama・`qwen2.5:32b`・failover）**＋ルールfallback**。
- 返り: `{category(19種), rating(sfw|r15|r18), labels{illegal,csam_risk,real_violence,scam,spam,nonconsensual}}`。
- 最小規制の閾値: csam≥.5 / nonconsensual≥.6 / real_violence≥.7 / illegal≥.7 → **rejected**、spam|scam≥.7 → **pending_review**、他は tier既定。
- `CAT_POLICY`: adult→r18＆低信頼は必ずreview / news→review。category は tags に自動追加。
- env: `MOD_AI`(on/off) / `MOD_MODEL`(既定 qwen2.5:32b) / `DGX_OLLAMA`(カンマ区切りhost)。

## ハイブリッドゲート
tier T0-T3(投稿/日・尺・リンク・コメント上限)＝ `max(信頼スコア, ステーク由来)`。
`STAKE_T2=5000` / `STAKE_UNLIMITED=50000` MORM。新規T0=1投稿/日・60s・リンク不可・投稿は人手審査(pending_review)。
tier>=2 or staked は楽観approve。env: `GATEWAY`(hpmini encoder) / `ADMIN_TOKEN`。

## デプロイ (Mac Mini)
- 実体: `/Users/user/morm-play/play_server.py` / launchd `com.morm.play`(:8791, KeepAlive)
- nginx `morm-play.conf`: `play.morm.one` → 127.0.0.1:8791（`play.ctai.online` は旧picker:8790に残置）
- 経路: viewer → CF(play.morm.one) → zoku tunnel → Mac Mini nginx:8080 → :8791

再デプロイ:
```
scp play_server.py user@100.106.58.67:~/morm-play/play_server.py
ssh user@100.106.58.67 'launchctl unload ~/Library/LaunchAgents/com.morm.play.plist; launchctl load ~/Library/LaunchAgents/com.morm.play.plist'
```

## 現状 / TODO
- **シードカタログ16件**は全て実テスト動画(DEMO_CID=78bb0540b0b8775f)を指す=全タイル実再生可。実運用は `/api/admin/ingest` で実 play_cid を投入。
- いいねは `account`(localStorage `morm_m0r` 優先, 無ければ生成 `morm_play_uid`)単位。**Ed25519署名の実検証は未実装**(sigは保存のみ)=[[project_morm_walletless_accounts]]のウォレット連携が次段。
- edge health は内部専用(picker同等)。生存0でフェイルオープン。
