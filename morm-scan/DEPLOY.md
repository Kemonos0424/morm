# MORMSCAN デプロイ手順（scan.morm.one・静的＋生成スクリプト・market と同方式）

**構成**: cloudflared(tunnel `f60ef43f-8ba5-45ee-946f-1c1f673df231`) → `localhost:8080`(nginx)
→ server_name 別 vhost で静的配信。生成スクリプトが 2 分毎に `mormscan-data.json` を出力。
L1 本番ノード(:8900)は **read-only RPC を読むだけ**（改修・再起動なし）。

- `index.html` … エクスプローラ本体（`mormscan-data.json` を fetch して描画）
- `mormscan-data-gen.py` … L1 RPC(:8900) + Base 公開RPC を読み JSON を生成（`market-data-gen.py` と同系）

## 実施済み（このセッション）
- `scp morm-scan/index.html ts-mini:/Users/user/zoku-sites/morm-scan/`
- `scp morm-scan/mormscan-data-gen.py ts-mini:/Users/user/Desktop/MORM/morm-scan/`
- 生成スクリプトを本番パスへ実行し `mormscan-data.json` を配置（sha 確認）

## 残り（ユーザー実行・ts-mini / インフラ再起動を含む）

### 1. nginx vhost `/opt/homebrew/etc/nginx/servers/morm-scan.conf`
```nginx
server {
    listen 8080;
    server_name scan.morm.one;
    root /Users/user/zoku-sites/morm-scan;
    index index.html;
    charset utf-8;
    location ~ /\.(?!well-known) { deny all; }
    location / { try_files $uri $uri/ =404; }
}
```
```bash
/opt/homebrew/bin/nginx -t && /opt/homebrew/bin/nginx -s reload
curl -H "Host: scan.morm.one" http://localhost:8080/ -s -o /dev/null -w "%{http_code}\n"   # 200
```

### 2. cloudflared ingress `/Users/user/.cloudflared/config.yml`
catch-all(`- service: http_status:404`)の直前に追加:
```yaml
  - hostname: "scan.morm.one"
    service: http://localhost:8080
```
```bash
cloudflared tunnel ingress validate
launchctl kickstart -k gui/501/com.cloudflared.tunnel   # ★再起動中は全サイト一時530→数秒で回復
```

### 3. cron（2 分毎に JSON 更新）
`crontab -e` に追記（market-data-gen と同様）:
```
*/2 * * * * cd /Users/user/Desktop/MORM && /usr/bin/python3 morm-scan/mormscan-data-gen.py >> /tmp/mormscan-gen.log 2>&1
```

### 4. DNS（gated＝morm.one CF アカウント・ユーザー手動）
morm.one ゾーンに **proxied CNAME**:
`scan.morm.one` → `f60ef43f-8ba5-45ee-946f-1c1f673df231.cfargotunnel.com`
（www / market と同方式。★`cloudflared tunnel route dns` は誤って ctai.online ゾーンに付けるので使わない）

### 5. 検証（DNS 伝播後）
```bash
curl -sI https://scan.morm.one/ | head -1                 # 200
curl -s https://scan.morm.one/mormscan-data.json | head -c 200
```

## 更新時
- UI 変更: `index.html` を scp し直すだけ（静的・再起動不要）
- 生成ロジック変更: `mormscan-data-gen.py` を scp（cron が次回実行で反映）

## データ範囲（MVP）
- chain 概況 / 直近 60 ブロック / 直近 120 tx / ブリッジ直近 120 件（L1→Base は /bridge/burns で状態付き、Base→L1 は Base ログ）
- 将来: tx/アカウント個別ページ、Base→L1 の L1 反映確定フラグ、ページネーション
