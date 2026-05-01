#!/usr/bin/env bash
# Phase 25Vc — CDN warm-up. Pulls master.m3u8 + each ladder's index.m3u8
# + the first N segments through the CDN edge so that the first real
# viewer hits cached content. Designed to run right after publishing
# (`morm-core hls-encode` followed by REGISTER_CONTENT).
#
# Usage:
#   ./warm-up.sh <cdn-base-url> <content-id> [num-segments]
#   ./warm-up.sh https://cdn.morm.io 78de3c45669888fd 5
set -euo pipefail

cdn="${1:?usage: warm-up.sh <cdn-base-url> <content-id> [num-segments]}"
cid="${2:?usage: warm-up.sh <cdn-base-url> <content-id> [num-segments]}"
n_segs="${3:-5}"

cdn="${cdn%/}"
prefix="${cdn}/api/video/${cid}"

# helper that hits a URL once and reports cache status
warm() {
  local url="$1"
  local status
  status=$(curl -sS -o /dev/null -w '%{http_code} %{time_total}s' "$url")
  printf '  %-7s  %s\n' "$status" "$url"
}

echo "[warm-up] master + per-ladder index"
warm "${prefix}/master.m3u8"

# Parse master.m3u8 client-side to discover ladder names. We fetch with
# curl and grep relative ladder paths; the rewrite from --cdn-base-url is
# already absolute when served by the gateway, so we accept both.
mapfile -t ladders < <(
  curl -sS "${prefix}/master.m3u8" \
  | awk '/^[^#]/ && /index\.m3u8/ {
      sub("^https?://[^/]+/api/video/[^/]+/", "")
      sub("/index\\.m3u8$", "")
      print
    }'
)
if [[ ${#ladders[@]} -eq 0 ]]; then
  echo "[warm-up] WARN: no ladders parsed from master.m3u8" >&2
fi

for rung in "${ladders[@]}"; do
  warm "${prefix}/${rung}/index.m3u8"
done

echo "[warm-up] first ${n_segs} segments per ladder"
for rung in "${ladders[@]}"; do
  # fetch the ladder's index.m3u8 and parse first N segment lines
  mapfile -t segs < <(
    curl -sS "${prefix}/${rung}/index.m3u8" \
    | awk '/^[^#]/ && /\.m4s$/ {
        sub("^https?://[^/]+/api/video/[^/]+/[^/]+/", "")
        print
      }' | head -n "$n_segs"
  )
  for s in "${segs[@]}"; do
    warm "${prefix}/${rung}/${s}"
  done
  # also fetch the init segment(s) — there is one per ladder
  mapfile -t inits < <(
    curl -sS "${prefix}/${rung}/index.m3u8" \
    | awk -F'"' '/EXT-X-MAP:URI=/ {
        u=$2
        sub("^https?://[^/]+/api/video/[^/]+/[^/]+/", "", u)
        print u
      }'
  )
  for i in "${inits[@]}"; do
    warm "${prefix}/${rung}/${i}"
  done
done

echo "[warm-up] done"
