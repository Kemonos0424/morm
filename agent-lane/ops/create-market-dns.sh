#!/bin/bash
# create-market-dns.sh — market.morm.one の proxied CNAME を Cloudflare(morm.one ゾーン)に作成する。
#   Mac Mini 側(nginx vhost + cloudflared ingress)は完成済。残りはこの DNS レコード1件のみ。
#   ★あなたの Cloudflare API トークンで実行(ボタン)。トークンは env で渡し、表示しない。
#
#   使い方:
#     CF_API_TOKEN='<Zone:DNS:Edit 権限のトークン>' ./create-market-dns.sh
#   (トークンは Cloudflare dashboard → My Profile → API Tokens → Create Token →
#    "Edit zone DNS" テンプレ → Zone Resources = morm.one、で発行)
set -euo pipefail
: "${CF_API_TOKEN:?CF_API_TOKEN 未設定。CF_API_TOKEN='...' ./create-market-dns.sh の形で実行}"
API="https://api.cloudflare.com/client/v4"
TUNNEL="f60ef43f-8ba5-45ee-946f-1c1f673df231"
TARGET="${TUNNEL}.cfargotunnel.com"
NAME="market.morm.one"

hdr=(-H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json")

echo "== 1) morm.one ゾーンID 取得 =="
ZID="$(curl -s "${hdr[@]}" "$API/zones?name=morm.one" | python3 -c 'import sys,json
d=json.load(sys.stdin); r=d.get("result") or []
print(r[0]["id"] if r else "")')"
[ -n "$ZID" ] || { echo "morm.one ゾーンが見つからない(トークン権限/アカウント確認)"; exit 1; }
echo "  zone id: ${ZID:0:8}…"

echo "== 2) 既存 market レコードの有無 =="
EXIST="$(curl -s "${hdr[@]}" "$API/zones/$ZID/dns_records?name=$NAME" | python3 -c 'import sys,json
d=json.load(sys.stdin); r=d.get("result") or []
print(r[0]["id"] if r else "")')"

BODY="{\"type\":\"CNAME\",\"name\":\"market\",\"content\":\"$TARGET\",\"proxied\":true}"
if [ -n "$EXIST" ]; then
  echo "  既存あり → 更新(PUT)"
  RESP="$(curl -s -X PUT "${hdr[@]}" "$API/zones/$ZID/dns_records/$EXIST" -d "$BODY")"
else
  echo "  新規作成(POST)"
  RESP="$(curl -s -X POST "${hdr[@]}" "$API/zones/$ZID/dns_records" -d "$BODY")"
fi

echo "== 3) 結果 =="
echo "$RESP" | python3 -c 'import sys,json
d=json.load(sys.stdin)
if d.get("success"):
    r=d["result"]; print(f"  OK: {r[\"name\"]} CNAME -> {r[\"content\"]} proxied={r[\"proxied\"]}")
else:
    print("  FAILED:", d.get("errors")); raise SystemExit(1)'
echo "== 完了。伝播後 https://market.morm.one/ が live(エージェントが確認します)。 =="
