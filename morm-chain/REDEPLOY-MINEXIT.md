# MORMExportBridge 再デプロイ手順（minExit=1e18・Base Sepolia）

**なぜ再デプロイか**: 稼働中 bridge `0xf7a4c27a…db10a818` の `minExit=0`（1MORM未満 exit がダスト永久損失
になり得る）だが、`minExit` は **immutable**（setter 無し）で変更不可。さらに既存 WMORM `0x5cd8…` の
`setBridge` は **one-shot**（旧 bridge に恒久バインド）で再ポイント不可。→ **新 WMORM＋新 bridge の
フルスタック再デプロイ**が必要（testnet・実資金なし）。deploy script はコード変更不要（`MIN_EXIT` env 対応）。

**★ broadcast は deployer 鍵での on-chain 操作＝ユーザーが実行**（エージェントは準備・検証まで）。

## 現行 bridge に合わせるパラメータ（読み取り済 2026-08-29）
| param | value |
|---|---|
| WINDOW_LEN | 3600（1h） |
| MAX_MINT_PER_WINDOW | 1000000000000000000000000（1e24） |
| MAX_SUPPLY | 100000000000000000000000000（1e26） |
| THRESHOLD | 2 |
| GUARDIAN | 0x9eb4c134A85c707E10D3413d757a2ba938B94599（GUARDIAN_MULTISIG_ADDR） |
| **MIN_EXIT** | **1000000000000000000（1e18＝1 MORM・今回の変更点）** |

## 1. 事前（ドライラン・任意）
```bash
cd ~/Desktop/MORM/morm-chain
forge build          # compile 確認（artifact present ならOK）
```
★**broadcast 前に必ず** `echo "${DEPLOYER_PK:?DEPLOYER_PK unset}"` で存在確認。未設定だと
DeployExportBridge.s.sol が **周知の Anvil #0 秘密鍵 `0xac0974…f2ff80` に silent fallback** して
その鍵でデプロイ/署名してしまう（GUARDIAN も未設定なら Anvil #1 に fallback）。`.testnet-keys.env` に
`DEPLOYER_PK` があることを `source` 後に確認すること。
本番同等シミュレーション（`--broadcast` 無し＝on-chain 送信なし・deployer鍵は startBroadcast に必要）:
```bash
set -a; source ../.testnet-deploy.env; source ../.testnet-keys.env; set +a
export GUARDIAN="$GUARDIAN_MULTISIG_ADDR" THRESHOLD="$GUARDIAN_THRESHOLD"
export SIGNER_A="$SIGNER_A_ADDR" SIGNER_B="$SIGNER_B_ADDR" SIGNER_C="$SIGNER_C_ADDR"
export WINDOW_LEN=3600 MAX_MINT_PER_WINDOW=1000000000000000000000000 MAX_SUPPLY=100000000000000000000000000
export MIN_EXIT=1000000000000000000 DEPLOY_MOCK_USDC=true
forge script script/DeployExportBridge.s.sol --rpc-url "$RPC_URL"    # シミュレーションのみ
```

## 2. 本番 broadcast（★ユーザー実行）
上記 env を設定したまま:
```bash
forge script script/DeployExportBridge.s.sol --rpc-url "$RPC_URL" --broadcast --verify
```
- ログ末尾の `WMORM` / `MORMExportBridge` / `MockUSDC` の**新アドレス**を控える。
- `w.setBridge(newBridge)` は run() 内で自動実行（新 WMORM は新 bridge に one-shot バインド）。

## 3. 検証
```bash
cast call <NEW_BRIDGE> "minExit()(uint256)" --rpc-url "$RPC_URL"   # → 1000000000000000000
cast call <NEW_BRIDGE> "threshold()(uint256)" --rpc-url "$RPC_URL" # → 2
```

## 4. 移行（新アドレスを全参照へ反映）
- `../.testnet-deploy.env`: `WMORM_ADDR` / `BRIDGE_ADDR` / `USDC_ADDR` を新値へ。`POOL_ADDR` は再作成後に。
- **export_relayer** の運用 env: `BRIDGE_ADDR` を新 bridge へ（[[C-1]] 反映と同時に）。
- **morm-market** `app.html`: 旧 contract 定数（WMORM/BRIDGE/USDC）を新値へ→再 scp（`morm-market/DEPLOY.md`）。
- **Uniswap(Base Sepolia)**: 新 WMORM/USDC プールを作成し `POOL_ADDR` 更新（app.html の価格チャート参照先）。
- 旧 bridge/WMORM は放置で可（testnet・残存 wMORM は旧 pool でのみ有効）。

## 補足
- 非緊急: relayer の dust ALERT で暫定緩和済。mainnet 化や他 bridge 変更とまとめて実施推奨。
- SIGNER_A/B/C は **アドレス**（deploy script は `vm.envOr("SIGNER_A", …)` を address として読む）。

---
## ★実施結果（2026-08-29 deploy 済・Base Sepolia）
- WMORM: `0x91FF1A51EEcCdBBC5d3A9ABD56E11352885667ed`
- MORMExportBridge: `0x97a84556abe75391CC177204AeE0D2f4c569Ab8E`（**minExit=1e18 検証済**・threshold=2・token=新WMORM）
- MockUSDC: `0xcC07858c6ba05A65eD47570233b9B010e2482Ea2`
- 新WMORM.bridge = 新bridge（setBridge one-shot 済）。
- 移行済: `.testnet-deploy.env`／`morm-market/{app,index}.html`／Mac Mini 再scp。relayer runbook の BRIDGE_ADDR も更新。
- **残**: 新 wMORM/USDC の Uniswap v3 プール作成→`index.html` の POOL/POOL_BLOCK 更新／C-1 relayer を新 bridge で起動。
