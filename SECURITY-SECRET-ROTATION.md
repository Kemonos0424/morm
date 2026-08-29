# SECRET ローテ Runbook / 公開露出インシデント（2026-08-29）

**状況**: `github.com/Kemonos0424/morm` は **PUBLIC**。初回リリースコミット `f82ea6e` が既に
`origin/main` に push 済みのため、以下の鍵素材が **GitHub 上で公開済み**（fork/clone/キャッシュ前提で
**恒久的に compromised**）。履歴 rewrite は公開後では無効 → **ローテ＋失効が唯一の有効策**。

---

## 1. `morm-aiservice/service-key.json`（★要対応・一部 gated）

- **正体**: AIサービスの ed25519 恒久 identity（`seed`/`pubkey`/`address`）。
  用途 = 動画生成の attestation 署名（`aiservice.py`: `attestation = ed25519_sign(svc_seed, gen_id||cid)`）。
  「L1 が ai_service を既知パブリッシャとして強制」する設計。
- **露出**: `f82ea6e:morm-aiservice/service-key.json` に seed(64hex) 平文。origin/main のツリーに現存
  （untrack コミット `8cde7a0` は未push・push してもファイル削除は履歴を消さない）。
- **緩和材料**: `aiservice.py` は自称 **「PoC stand-in for a real video diffusion model」**。
  本番 L1 のパブリッシャ登録に**未連携なら実害は限定的**。鍵は `get_or_create_keypair()` で自動再生成。

### 対応（順に）
1. **[判断・要確認]** 旧 `address`/`pubkey` が **本番 L1 の既知パブリッシャ登録を持つか**を確認
   （L1 の publisher registry / 掌管 admin。Mac Mini :8900 側）。
2. **持つ場合 [gated=L1 admin操作]**: 旧pubkey を**失効/de-register** → 新鍵を生成し登録。
   - 新鍵生成: サービスホストで旧 `service-key.json` を削除 → `python3 aiservice.py keygen`（自動生成）
     もしくは `get_or_create_keypair()` 初回起動。新 `pubkey`/`address` を控える。
3. **持たない場合（PoC未連携）**: 実害低。ローカルで鍵ファイルを再生成して置換すれば足りる。
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
