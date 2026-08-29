# morm-market デプロイ手順（market.morm.one・静的・www と同方式）

**状態（2026-08-29）**: Mac Mini 側（scp＋nginx＋cloudflared ingress）**完了**。残りは
**morm.one ゾーンの DNS レコード作成のみ**（gated＝ユーザーの morm.one Cloudflare アカウント）。

**方式**: cloudflared(tunnel `f60ef43f-8ba5-45ee-946f-1c1f673df231`) → `localhost:8080`(nginx)
→ server_name 別 vhost で静的配信。www.morm.one と同一構成（参考 vhost=`morm-apex.conf`）。
中身は静的HTML2枚（`index.html`=価格チャート/入口、`app.html`=ブリッジ&スワップ・**Base Sepolia testnet**）。

## 実施済み（Mac Mini `ts-mini` / user）
1. **自己参照を相対リンク化**（`morm-market.zoku.one`→相対）: index.html→`app.html` / app.html→`index.html`（commit 4222502・host非依存）。
2. **scp**: `scp morm-market/{index,app}.html ts-mini:/Users/user/zoku-sites/morm-market/`（sha一致確認）。
3. **nginx vhost** `/opt/homebrew/etc/nginx/servers/morm-market.conf`:
   ```nginx
   server {
       listen 8080;
       server_name market.morm.one;
       root /Users/user/zoku-sites/morm-market;
       index index.html;
       charset utf-8;
       location ~ /\.(?!well-known) { deny all; }
       location / { try_files $uri $uri/ =404; }
   }
   ```
   `/opt/homebrew/bin/nginx -t` OK → `nginx -s reload`。確認: `curl -H "Host: market.morm.one" http://localhost:8080/` = 200。
4. **cloudflared ingress** `/Users/user/.cloudflared/config.yml` の catch-all(`- service: http_status:404`)直前に追加:
   ```yaml
     - hostname: "market.morm.one"
       service: http://localhost:8080
   ```
   `cloudflared tunnel ingress validate` OK → `launchctl kickstart -k gui/501/com.cloudflared.tunnel`（★再起動中は全サイト一時 530→数秒で回復。SSH は mini.ctai.online 経由のため一旦切断される）。

## 残り（gated＝要ユーザー・morm.one CF アカウント）
5. **DNS**: morm.one ゾーンに **proxied CNAME**
   `market.morm.one` → `f60ef43f-8ba5-45ee-946f-1c1f673df231.cfargotunnel.com`
   を作成（www.morm.one / play.morm.one と同方式）。
   - ⚠️ `cloudflared tunnel route dns` は tunnel 既定ゾーン **ctai.online** にレコードを付けてしまう
     （実際 `market.morm.one.ctai.online` を誤作成済→**ctai.online ゾーンで削除**推奨）。morm.one は
     別アカウント管理のため、**CF ダッシュボード/該当アカウントの API** で手動作成すること。
6. **検証**（DNS 伝播後）:
   ```bash
   curl -sI https://market.morm.one/           # 200
   curl -s  https://market.morm.one/app.html | head -c 200
   ```
   ブラウザで入口→`app.html`（Base Sepolia ブリッジ/スワップ）動作確認。
   ※ mainnet 化する場合は app.html の RPC/contract を別途更新（現状 testnet）。

## 更新時
- 手順2の scp をやり直すだけ（静的・再起動不要）。ARCHITECTURE.md の market 行を live に更新。
