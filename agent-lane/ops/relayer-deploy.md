# export_relayer 常駐化 runbook（EVM↔L1 ブリッジ relayer）

`export_relayer.py`（hardened: last_block 永続化＋dust ALERT）を常駐サービス化する。**双方向**を担う:
- **L1 BRIDGE_BURN(MORM)** → EVM `bridge.mintFromBurn()`（EVM signer 秘密鍵を threshold 署名）
- **EVM `exit()`(wMORM burn)** → L1 `BRIDGE_MINT`（L1 treasury seed＋TREASURY_SIGNER_SEEDS で multisig cosign）

★ ブリッジの**発行権限を両方向で保持**する機微サービス。鍵配置と起動＝**ユーザー実行**（エージェントは
コード配置・runbook・依存確認まで）。

## ★ C-2 との順序
現行 bridge `0xf7a4c27a…` は `minExit=0`。[[REDEPLOY-MINEXIT]]（C-2）で新 bridge を出すなら、
**C-2 後に新 BRIDGE_ADDR で relayer を起動**するのが無駄がない。今すぐ exit 処理を回したい場合は
現行 bridge で起動→C-2 後に `BRIDGE_ADDR` を差し替え。

## ホスト（推奨）
- **Mac Mini（`ts-mini`）** = L1（:8900）隣接・`web3 7.16.0`/`eth_account` 導入済・cloudflared 常駐。
  testnet は単一ホストで可（本番は signer を分散/HSM 推奨＝コード冒頭コメント）。
- EVM_RPC = `https://sepolia.base.org`（外部・Mac Mini から到達可）。

## 1. コード配置（エージェント実施済 or 実施可）
```bash
scp export_relayer.py ts-mini:/Users/user/morm-relayer/export_relayer.py
scp -r morm-chain/out ts-mini:/Users/user/morm-relayer/abi   # bridge ABI（out/MORMExportBridge.sol/…）が必要な場合
```
（相対 import 無し・単体スクリプト。ABI は `../morm-chain/out` 参照 or 同梱）

## 2. env（★鍵はユーザーが配置・commit/表示しない）
`~/.morm-relayer/relayer.env`（0600）:
```
EVM_RPC=https://sepolia.base.org
MORM_RPC=http://127.0.0.1:8900
BRIDGE_ADDR=0xF7A4C27aC202638372540899dFf9D474Db10A818   # C-2後は新bridgeへ
CHAIN_ID=84532
THRESHOLD=2
EXPORT_TOKEN=MORM
# EVM 側 mintFromBurn の threshold 署名鍵（.testnet-keys.env の SIGNER_*_PK・カンマ区切り）:
SIGNER_PKS=<A_PK>,<B_PK>,<C_PK>
# EVM tx を実送信しガスを払う口座（署名者と別でも可・Base Sepolia ETH を保有させる）:
SUBMITTER_PK=<submitter_pk>
# L1 側 BRIDGE_MINT の treasury＋multisig cosign 鍵:
TREASURY_SEED_HEX=<L1 treasury seed>
TREASURY_SIGNER_SEEDS=<seedA>,<seedB>
TREASURY_MS_THRESHOLD=2
```
（変数名は `export_relayer.py` の `os.environ` 定義に厳密一致: `SIGNER_PKS`・`SUBMITTER_PK`・
`TREASURY_SEED_HEX`・`TREASURY_SIGNER_SEEDS` 等。SUBMITTER は Base Sepolia のガス代 ETH が要る）

## 3. 事前検証（鍵不要 or 最小）
```bash
cd /Users/user/morm-relayer
set -a; source ~/.morm-relayer/relayer.env; set +a
python3 export_relayer.py selftest    # digest/署名 parity をチェーンと突合（起動前の健全性確認）
```

## 4. 常駐（launchd）
`~/Library/LaunchAgents/one.morm.relayer.plist`（EnvironmentVariables に上記 env、または env ファイルを
読む wrapper）→
```bash
launchctl bootstrap gui/501 ~/Library/LaunchAgents/one.morm.relayer.plist
launchctl kickstart -k gui/501/one.morm.relayer
```
- ログ: StandardOut/ErrorPath を `/Users/user/morm-relayer/relayer.{log,err}` に。
- 監視: `.export_relayer_state.json`（last_block 前進）／`.export_relayer_dust.jsonl`（dust ALERT）。

## 5. 検証
- テスト: Base Sepolia で小額 `exit()` → 数ブロック後に L1 で該当 m0r の残高増（BRIDGE_MINT）。
- 逆: L1 で小額 BRIDGE_BURN → EVM で wMORM mint。
- 冪等: 同一 burn の再処理で二重クレジットしない（evm_lock_id / minted[]）。

## 非緊急
現状 relayer 未稼働＝EVM→L1 exit は未処理。testnet・実資金なし。C-2 とまとめて実施推奨。
