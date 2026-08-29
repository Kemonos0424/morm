# morm-market デプロイ手順（market.morm.one・静的・www と同方式）

**方式（決定 2026-08-29）**: www.morm.one と同じ **Mac Mini へ scp（静的）→ nginx で配信 → Cloudflare
Tunnel で公開**。morm-market は**静的HTML2枚のみ**（`index.html`=LP/入口、`app.html`=ブリッジ&スワップ
UI。ビルド不要）。**実行は SSH/nginx/Cloudflare/DNS 操作＝gated（要ユーザー承認）**。

> ⚠️ Mac Mini 固有値（scp先ディレクトリ・nginx conf.d パス・cloudflared config パス・tunnel ローカル
> ポート）は www の「別配線」でリポ外。既存 www/play の実配線に合わせて下の `<...>` を確定すること。
> 参考パターン: `morm-play/morm-play.conf`（play は proxy_pass、market は静的 root なので下記に差し替え）。

## 1. 静的ファイルを Mac Mini へ転送
```bash
# Mac Mini（192.168.2.122）の配信ディレクトリへ（www と同じ親配下に揃える）
MM=<user>@192.168.2.122
DEST=<web root>/market.morm.one          # 例: /var/www/market.morm.one（www の site/ と同階層に）
ssh "$MM" "mkdir -p $DEST"
scp ~/Desktop/MORM/morm-market/index.html ~/Desktop/MORM/morm-market/app.html "$MM:$DEST/"
```

## 2. nginx vhost（静的配信）
`<nginx conf.d>/market.morm.one.conf`（play と違い proxy ではなく root 直配信）:
```nginx
server {
    listen <tunnel port>;            # 例: 8081（play=8080 と衝突しない空きポート）
    server_name market.morm.one;
    root <web root>/market.morm.one; # 手順1の DEST
    index index.html;
    location / { try_files $uri $uri/ =404; }
}
```
```bash
ssh "$MM" 'sudo nginx -t && sudo nginx -s reload'
```

## 3. Cloudflare Tunnel ingress
既存 cloudflared config（play/www と同じファイル）の `ingress:` に追加:
```yaml
  - hostname: market.morm.one
    service: http://localhost:<tunnel port>   # 手順2の listen ポート
```
```bash
# DNS ルート（未作成なら）: market.morm.one を tunnel に向ける
cloudflared tunnel route dns <tunnel name> market.morm.one
ssh "$MM" 'sudo systemctl restart cloudflared'   # または該当の再読込
```

## 3.5 デプロイ前の要編集（自己参照URL）
- app.html/index.html は **`https://morm-market.zoku.one/...` を自己参照**（canonical/og:url 等・既存
  zoku デプロイ痕跡）。market.morm.one へ出すなら該当箇所を `https://market.morm.one/...` へ置換:
  ```bash
  cd ~/Desktop/MORM/morm-market
  grep -rl "morm-market.zoku.one" . && sed -i '' 's#morm-market\.zoku\.one#market.morm.one#g' index.html app.html
  ```
  （zoku を staging として残すなら置換せず両建ても可＝ユーザー判断）。
- 中身は **Base Sepolia テストネット**（`sepolia.base.org`・chainId sepolia・testnet contracts）＝
  実 mainnet 資金は扱わない。プロダクションで mainnet に切替える場合は RPC/contract を別途更新。

## 4. 検証
```bash
curl -sI https://market.morm.one/            # 200・index.html
curl -s  https://market.morm.one/app.html | head -c 200
```
- ブラウザで `https://market.morm.one/`（入口）→ `app.html`（Base Sepolia ブリッジ/スワップ）動作確認。
- app.html が叩く価格/ブリッジ系の向き先（EVM RPC / api.morm.one `/api/price` 等）が本番を指すか確認。

## 5. 反映
- 更新時は手順1の scp をやり直すだけ（静的・再起動不要）。
- ARCHITECTURE.md の market.morm.one 行を live に更新。
