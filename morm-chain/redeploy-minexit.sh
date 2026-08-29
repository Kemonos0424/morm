#!/bin/bash
# redeploy-minexit.sh — MORMExportBridge を minExit=1e18 で Base Sepolia に再デプロイ(ワンコマンド)。
#   ★deployer 鍵での on-chain broadcast を伴う。実行=あなた(ボタン)。testnet(実資金なし)・非緊急。
#   手順の背景/移行は REDEPLOY-MINEXIT.md を参照。
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1) env 読込 (.testnet-deploy.env / .testnet-keys.env) =="
set -a; source ../.testnet-deploy.env; source ../.testnet-keys.env; set +a
: "${DEPLOYER_PK:?DEPLOYER_PK が未設定(.testnet-keys.env)。Anvil鍵への silent fallback を防ぐため中止}"
: "${RPC_URL:?RPC_URL 未設定}"
: "${GUARDIAN_MULTISIG_ADDR:?}" ; : "${GUARDIAN_THRESHOLD:?}"
: "${SIGNER_A_ADDR:?}" ; : "${SIGNER_B_ADDR:?}" ; : "${SIGNER_C_ADDR:?}"

# 現行 bridge に整合するパラメータ + 今回の変更点 MIN_EXIT=1e18
export GUARDIAN="$GUARDIAN_MULTISIG_ADDR" THRESHOLD="$GUARDIAN_THRESHOLD"
export SIGNER_A="$SIGNER_A_ADDR" SIGNER_B="$SIGNER_B_ADDR" SIGNER_C="$SIGNER_C_ADDR"
export WINDOW_LEN=3600
export MAX_MINT_PER_WINDOW=1000000000000000000000000       # 1e24
export MAX_SUPPLY=100000000000000000000000000              # 1e26
export MIN_EXIT=1000000000000000000                        # ★1e18 = 1 MORM floor
export DEPLOY_MOCK_USDC=true

echo "== 2) 設定確認 =="
echo "  RPC        : $RPC_URL   (chain ${CHAIN_ID:-?})"
echo "  GUARDIAN   : $GUARDIAN  THRESHOLD=$THRESHOLD"
echo "  SIGNERS    : $SIGNER_A / $SIGNER_B / $SIGNER_C"
echo "  MIN_EXIT   : $MIN_EXIT (=1e18)"
echo "  MockUSDC   : $DEPLOY_MOCK_USDC"
echo "  DEPLOYER   : ${DEPLOYER_ADDR:-<from PK>} (鍵は表示しない)"
echo
read -r -p "この内容で Base Sepolia に broadcast しますか? (yes/no) " ans
[ "$ans" = "yes" ] || { echo "中止しました。"; exit 1; }

echo "== 3) forge build (compile 確認) =="
forge build >/dev/null && echo "  build OK"

echo "== 4) broadcast =="
forge script script/DeployExportBridge.s.sol --rpc-url "$RPC_URL" --broadcast --verify

echo
echo "== 完了。ログ末尾の WMORM / MORMExportBridge / MockUSDC の新アドレスを控えてエージェントへ。 =="
echo "   その後: 検証(cast call <NEW_BRIDGE> 'minExit()(uint256)' → 1e18) + BRIDGE_ADDR 全参照移行 + C-1 relayer 起動。"
