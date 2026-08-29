# SECRET ローテ Runbook / 公開露出インシデント（2026-08-29）

**状況**: `github.com/Kemonos0424/morm` は **PUBLIC**。初回リリースコミット `f82ea6e` が既に
`origin/main` に push 済みのため、以下の鍵素材が **GitHub 上で公開済み**（fork/clone/キャッシュ前提で
**恒久的に compromised**）。履歴 rewrite は公開後では無効 → **ローテ＋失効が唯一の有効策**。

---

## 1. `morm-aiservice/service-key.json`（✅解決 2026-08-29: 本番未登録＝ローテ不要）

**結論（確定）**: 本番 Mac Mini L1（`ts-mini`・:8900・head_height=23 の実チェーン）で
`GET /ai-services` = **`{"services": []}`**。漏洩pubkey `b88942..f291` は**本番L1に未登録**＝
attestation を強制される場面がなく**実権限なし**。→ **L1 失効/再登録は不要**。PoC鍵の再生成は
任意（衛生目的・`service-key.json` は既に不在＋`.gitignore`済で今後コミットもされない）。

---
### 参考（当初の調査・上記結論の根拠）

- **正体**: AIサービスの ed25519 恒久 identity（`seed`/`pubkey`/`address`）。
  用途 = 動画生成の attestation 署名（`aiservice.py`: `attestation = ed25519_sign(svc_seed, gen_id||cid)`）。
  「L1 が ai_service を既知パブリッシャとして強制」する設計。
- **露出**: `f82ea6e:morm-aiservice/service-key.json` に seed(64hex) 平文。origin/main のツリーに現存
  （untrack コミット `8cde7a0` は未push・push してもファイル削除は履歴を消さない）。
- **緩和材料**: `aiservice.py` は自称 **「PoC stand-in for a real video diffusion model」**。
  本番 L1 のパブリッシャ登録に**未連携なら実害は限定的**。鍵は `get_or_create_keypair()` で自動再生成。

### 露出鍵（公開情報・確認用）
- pubkey: `b88942319130adc2f65df83255ecf713556d4de8ffb02d7510e69b21e7f6f291`
- address: `0x32f40ad3b110000255d179eeb94fd910e89bc60a`

### 調査所見（2026-08-29・MacBook から実施）
- 旧 pubkey/address は **`morm-aiservice/generated/*/manifest.json`（PoC自身の生成物）にのみ**出現。
  L1 の allowlist / 他サービス / デプロイ設定には**一切なし**。
- morm-aiservice を起動するのは **`poc/scenario_aiservice.py`（PoCシナリオ）だけ**（launchd/systemd/pm2 の本番デプロイなし）。
- L1 には ai_services レジストリ有り（`morm-l1/morm_l1/rpc.py` の `GET /ai-services`、登録tx=`register_ai_service`）。
- MacBook から到達できた `127.0.0.1:8900/ai-services` は **`{"services": []}`（登録ゼロ）**。ただしこれが
  本番 Mac Mini L1 か別実体か未確定（当機に `~/.morm-l1` なし・Mac Mini :8900 は LAN直では不応答）。
- **暫定結論**: 漏洩鍵は **PoC専用で本番 L1 未登録の公算大＝実権限なし**。

### 対応（順に）
1. **[権威確認・gated=Mac Mini で1回]** 本番 L1 で登録有無を確定:
   ```
   ssh <MacMini> 'curl -s http://127.0.0.1:8900/ai-services' | python3 -m json.tool
   # 出力に pubkey b88942...f291 が無ければ = 本番未登録（rotation不要）
   ```
2. **登録あり（想定外）の場合 [gated=L1 admin操作]**: 旧pubkey を失効/de-register → 新鍵を生成し再登録。
   - 新鍵生成: サービスホストで旧 `service-key.json` を削除 → `python3 aiservice.py keygen`（`get_or_create_keypair()` が自動生成）。新 `pubkey`/`address` を控える。
3. **登録なし（想定どおり）の場合**: 実害なし。衛生目的でローカルの鍵ファイルを再生成して置換すれば足りる（L1 操作不要）。
4. **共通**: `service-key.json` は `.gitignore`（`*service-key.json`）済 = 今後コミットされない（確認済）。

---

## 2. `.claude/launch.json` の `--treasury-seed`（✅ローカル除去済・実害なし）

- **正体**: **anvil/dev 専用** treasury seed。同ファイルは `--evm-chain-id 31337`（anvil既定）・
  `--dev-mode`・`--bridge-addr 0x5fbdb2315678afecb367f032d93f642f64180aa3`（anvil決定的デプロイ）を伴い、
  参照先も archived 済みの `morm-player/server.py`・`passkey_morm.py`（**現存しない死設定**）。
- **本番との分離（確認済）**: 本番 treasury seed は **`~/.morm-l1/producer.seed`（リポ外）** から読む
  （`play_server.py: TREASURY_SEED_FILE`）。launch.json の dev seed は**本番権限ゼロ**。
- **対応**: 露出値を env placeholder `${MORM_DEV_TREASURY_SEED}` に置換済（このコミット）。
  露出済みの旧 dev seed は anvil 上で何も支配しないため**ローテ不要**。
- **推奨（任意・D/Phase2相当）**: 死んだ morm-player 設定の整理、または個人用ランチャなので
  `.claude/launch.json` 自体を untrack+gitignore（`git rm --cached` はディスク上のファイルを残す=ツール動作は不変）。

---

## 3. 履歴 rewrite について

- 公開後のため **rewrite は露出解消にならない**（GitHub の fork/clone/検索キャッシュに残存）。
- 主対策は #1 の**ローテ＋失効**。rewrite を行うなら別途ユーザー判断（全hash変更・force-push・
  submodule/参照影響）。**push前提の唯一の実利は本番 producer.seed 等の“まだ非公開”鍵の保護**だが、
  本番 seed はリポ外のため該当なし。

---

## 4. ユーザー判断が必要な項目
- [ ] AIサービス旧鍵（`address`）は本番 L1 のパブリッシャ登録を持つか？（→持てば #1-2 実施）
- [ ] service-key ローテ実施可否（L1 admin 操作・gated）
- [ ] 履歴 rewrite を行うか（原則不要の見解）
