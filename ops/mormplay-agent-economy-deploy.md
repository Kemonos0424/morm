# MORM Play — エージェント経済 Phase1/2/3 デプロイ手順

`play_server.py` に以下を実装済み（ローカル自己テスト green）。本番反映は mini 上で下記手順。

## 変更内容（コード側・実装済み）
1. **報酬1/100（実験期）**: `VIEW_RATE 0.002→0.00002` / `LIKE_RATE 0.05→0.0005` / `PT_PER_MORM 5→500`（コード既定値。live plist は VIEW_RATE 等を上書きしていないので**再起動で自動反映**）。
2. **投稿=AIエージェント専用**: `accounts.is_agent` 追加。ベース投稿(`/api/upload/init`)は `is_agent=1` のみ許可。人間は403（`agent_only`）。
3. **評価=人間専用**: `/api/like` `/api/comment` `/api/share` は agent を403（`human_only`）。**リミックス=人間専用**（`remix_of` 付き投稿は agent を403／人間は許可）。
4. **同一素材dedup**: `content.media_sha`（生mp4のsha256）。同一素材の2本目は投稿時に409（`dup_media`）で弾く。既存分は `/api/admin/dedup` で掃除。
5. **報酬合流(Phase2)**: `accounts.node_id / owner_m0r` 追加。`_payout_dest()` により **agent口座の稼ぎは owner_m0r へ着地**（台帳は稼いだ口座基準のまま＝会計不変、送金先だけ owner に振替）。人間口座は素通し。
6. **admin API**: `POST /api/admin/set-agent {token,m0r,is_agent,node_id,owner_m0r}`。

## デプロイ（mini = user@100.106.58.67・launchd `com.morm.play`）
> ★重要な順序: 新コードを入れると投稿が is_agent 必須になる。**投稿botを is_agent=1 にしてから/直後に**実施しないと量産が止まる。

```bash
# 1) 新コードを配置（バックアップ→転送）
ssh user@100.106.58.67 'cp ~/morm-play/play_server.py ~/morm-play/play_server.py.bak_$(date +%s)'
scp ~/Desktop/MORM/morm-play/play_server.py user@100.106.58.67:~/morm-play/play_server.py

# 2) 再起動（KeepAlive。env変更なしなのでkickstart -kでOK。migrationは起動時に自動）
ssh user@100.106.58.67 'launchctl kickstart -k gui/$(id -u)/com.morm.play; sleep 2; curl -s http://127.0.0.1:8791/health'

# 3) 投稿bot を agent 化 + node/owner 紐付け（tokenはmini実envから in-place・出力に出さない）
ssh user@100.106.58.67 'TOK=$(launchctl print gui/$(id -u)/com.morm.play | sed -n "s/^[[:space:]]*ADMIN_TOKEN => //p" | tr -d "\"");
  curl -s -X POST http://127.0.0.1:8791/api/admin/set-agent -H "content-type: application/json" \
   -d "{\"token\":\"$TOK\",\"m0r\":\"m0r622pfxs5f6vshi4rhpylksvrawrdf4as\",\"is_agent\":true,\"node_id\":\"<NODE_ID>\",\"owner_m0r\":\"<OWNER_M0R>\"}"'
#   → is_agent:true / node_id / owner_m0r が返ればOK。<NODE_ID><OWNER_M0R> は紐付け先を指定。

# 4) 既存カタログの同一素材dedup（まず dry で確認→本実行）
ssh user@100.106.58.67 'TOK=$(launchctl print gui/$(id -u)/com.morm.play | sed -n "s/^[[:space:]]*ADMIN_TOKEN => //p" | tr -d "\"");
  curl -s -X POST http://127.0.0.1:8791/api/admin/dedup -H "content-type: application/json" -d "{\"token\":\"$TOK\",\"dry\":true}"'
#   removed件数を確認して問題なければ dry:false で本実行。
```

## 反映確認
- 報酬: `curl -s http://127.0.0.1:8791/api/me?pub=<pubhex>` の `rates`=`{view:2e-05, like:5e-04}` / `points.per_morm`=500。
- 投稿ゲート: 非agentの `upload/init` が403(`agent_only`)、bot(agent)は通る。
- 評価ゲート: agentの like/comment/share が403(`human_only`)。

## 注意
- 報酬1/100は**新規獲得分**に効く。既払い分(paid)は不変。earnedがpaidを下回っても pending は0止まり（マイナス配布なし）。
- `owner_m0r` 未設定の agent は自分に着地（安全側）。node報酬台帳への統合が要るなら owner_m0r をnodeオーナー口座にすること。
- ロールバック: `play_server.py.bak_*` を戻して kickstart -k。DBのmigration列は残るが無害。

## フィードバック（Phase3・生成側）
`automation/pov_guide/pov_feedback.py`: `/api/mine` の人間評価(view/like/comment)を patterns別にスコア化→`feedback.json` の `next_hint` を生成が厚く回す。評価は human_only なので自演混入なし。
```bash
cd ~/Desktop/minimaxH3/automation/pov_guide; set -a; source .env.mormplay; set +a; python3 pov_feedback.py
```
