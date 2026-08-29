# MORM 本番デプロイ手順（Base mainnet・3-of-5・実 Circle USDC）

対象: wMORM export スタック（WMORM + MORMExportBridge）を **Base mainnet(chainId 8453)** に
3-of-5 threshold で新規デプロイし、**実 Circle USDC** と Uniswap v3 プールを作る。
本ドキュメントは **②deploy / ③env / ④pool / ⑤ドライラン+移行** 分（①分散署名は別途）。

> ★**broadcast は deployer 鍵での on-chain 送信＝ユーザーが実行**。エージェントは準備・検証・ドライランまで。
> ★このリポは **PUBLIC**。秘密鍵/seed は `.mainnet-deploy.env`（.gitignore 済）にのみ置き、**絶対コミットしない**。

---

## 0. 確定パラメータ（本セッションで決定）

| 項目 | 値 | 種別 |
|---|---|---|
| chain | Base mainnet `8453` | — |
| USDC | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`（native Circle・6dec・検証済） | 実資産 |
| NPM(Uniswap v3) | `0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1`（検証済） | 公開 |
| **THRESHOLD / signers** | **3 of 5** | ★immutable |
| WINDOW_LEN | 3600 | ★immutable |
| MAX_MINT_PER_WINDOW | 1e24（100万 wMORM/時） | ★immutable |
| MAX_SUPPLY | 1e27（10億 wMORM） | ★immutable |
| MIN_EXIT | 1e18（1 wMORM） | ★immutable |
| GUARDIAN | 実 Gnosis Safe | 可変(setGuardian) |
| 初期プール | 100 USDC + 10,000 wMORM @ $0.01・fee 1%・full-range | 可変(いつでも追加) |

★immutable = 変更にはフルスタック再デプロイ要（`setBridge` one-shot のため）。signer 鍵ローテも不可
＝**3-of-5 で紛失/漏洩耐性を確保**。初動は現体制（全鍵1ホスト）で可、分散化は再デプロイ不要で後追い。

---

## 1. 事前準備（ユーザー）

- [ ] **実 ETH** を Base mainnet の deployer アドレスへ（deploy ガス＋当面運用。0.05 ETH 目安）
- [ ] **実 USDC 100 枚** を deployer アドレスへ（プール片側）
- [ ] **5本の署名鍵**を生成しアドレスを控える（初動は同一ホスト可・後で独立ホストへ）
- [ ] **Gnosis Safe**（guardian 用）を Base mainnet に用意しアドレスを控える
- [ ] `.mainnet-deploy.env` を作成:
      ```bash
      cd ~/Desktop/MORM/morm-chain
      cp mainnet-deploy.env.example ../.mainnet-deploy.env   # .gitignore 済
      # <FILL_...> を実値で埋める（RPC / SIGNERS / GUARDIAN / DEPLOYER_PK）
      ```

## 2. ドライラン（送信なし・エージェント/ユーザー両方可）

```bash
cd ~/Desktop/MORM/morm-chain
forge build
set -a; source ../.mainnet-deploy.env; set +a
# ★broadcast 前チェック（未設定なら Anvil 既定鍵に silent fallback するので必須）
: "${DEPLOYER_PK:?DEPLOYER_PK unset}"; : "${SIGNERS:?SIGNERS unset}"; : "${GUARDIAN:?GUARDIAN unset}"
echo "signers=$(echo $SIGNERS | tr ',' '\n' | wc -l) threshold=$THRESHOLD mock=$DEPLOY_MOCK_USDC"
forge script script/DeployExportBridge.s.sol --rpc-url "$RPC_URL"    # --broadcast なし＝シミュレーションのみ
```
ログで **signerCount=5 / threshold=3 / MockUSDC=(空)** を確認（`DEPLOY_MOCK_USDC=false` で mock を焼かない）。

## 3. 本番 broadcast（★ユーザー実行）

```bash
forge script script/DeployExportBridge.s.sol --rpc-url "$RPC_URL" --broadcast --verify
```
- ログ末尾の **WMORM / MORMExportBridge** の新アドレスを控える（MockUSDC は false なので出ない）。
- `w.setBridge(newBridge)` は run() 内で自動（新 WMORM を新 bridge に one-shot バインド）。
- `.mainnet-deploy.env` に `WMORM_ADDR` / `BRIDGE_ADDR` を追記。

## 4. デプロイ検証

```bash
B=$BRIDGE_ADDR
cast call $B "threshold()(uint256)"        --rpc-url "$RPC_URL"   # → 3
cast call $B "signerCount()(uint256)"      --rpc-url "$RPC_URL"   # → 5
cast call $B "maxSupply()(uint256)"        --rpc-url "$RPC_URL"   # → 1e27
cast call $B "maxMintPerWindow()(uint256)" --rpc-url "$RPC_URL"   # → 1e24
cast call $B "minExit()(uint256)"          --rpc-url "$RPC_URL"   # → 1e18
cast call $B "guardian()(address)"         --rpc-url "$RPC_URL"   # → Gnosis Safe
for s in $(echo $SIGNERS | tr ',' ' '); do echo -n "$s isSigner="; cast call $B "isSigner(address)(bool)" $s --rpc-url "$RPC_URL"; done
cast call $WMORM_ADDR "bridge()(address)"  --rpc-url "$RPC_URL"   # → BRIDGE_ADDR
```

## 5. wMORM を入手（プール片側 10,000 wMORM）

wMORM は **bridge 経由でのみ**発行（onlyBridge）。①分散署名 relayer 本番化前でも、暫定的に現行
relayer（全鍵1ホスト）を **mainnet 設定で1回だけ**動かして 10,000 MORM を forward し、wMORM を
deployer に mint する。→ relayer runbook（`agent-lane/ops/relayer-deploy.md`）を mainnet env で:
`BRIDGE_ADDR`=新・`CHAIN_ID=8453`・`RPC_URL`=mainnet・`SIGNER_PKS`=5鍵・`SUBMITTER_PK`=deployer。
（★これは初動限定。分散署名 relayer が本番化したら差し替え。）

## 6. プール作成 + 流動性（100 USDC + 10,000 wMORM）

```bash
set -a; source ../.mainnet-deploy.env; set +a   # WMORM_ADDR/USDC_ADDR/NPM_ADDR/SEED_* を含む
# ドライラン
forge script script/SeedPool.s.sol --rpc-url "$RPC_URL"
# 本番（★ユーザー・deployer 鍵）
forge script script/SeedPool.s.sol --rpc-url "$RPC_URL" --broadcast
```
- ログの **pool / token0 / token1** と `seed USDC=100 / seed wMORM=10000` を確認。
- `SeedPool` は `require(SEED_WMORM == SEED_USDC*100)` で $0.01 balanced を検算、token 順序で
  sqrtP を自動選択（新 WMORM が USDC より小さければ wMORM=token0）。
- fee=1%（tickSpacing200・full-range TL/TU=∓887200）。
- `.mainnet-deploy.env` に `POOL_ADDR` を追記。

## 7. 移行（新アドレスを全参照へ）

- [ ] `.mainnet-deploy.env`: `WMORM_ADDR`/`BRIDGE_ADDR`/`POOL_ADDR` 確定
- [ ] **relayer 運用 env**: `BRIDGE_ADDR`=新・`CHAIN_ID=8453`・`RPC_URL`=mainnet（①分散署名で本番化）
- [ ] **morm-market**（UI・別途 mainnet 版）: `app.html`/`index.html` の WMORM/BRIDGE/USDC/POOL/POOL_BLOCK/
      CHAIN/RPC/SWAP(=SwapRouter02 0x2626…)/FEE を mainnet 値へ。`priceFromSqrt` は token 順序で再確認。
- [ ] `POOL_BLOCK` = プール作成トランザクションのブロック番号（チャートの増分取得起点）

## 8. ロールバック / 緊急時

- 緊急: guardian（Gnosis Safe）から `setPaused(true)` で mint/exit 即停止。
- deploy は新規スタックなので、問題時は旧構成に切替えず**再デプロイ**（immutable 値の誤りは
  再デプロイでしか直せない＝2〜4節を再実行）。

---

## 付録: Base mainnet 公開アドレス（オンチェーン検証済 2026-08-29）
| name | address |
|---|---|
| USDC (native Circle) | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| Uniswap v3 NPM | `0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1` |
| Uniswap SwapRouter02 | `0x2626664c2603336E57B271c5C0b26F421741e481` |
| Uniswap v3 Factory | `0x33128a8fC17869897dcE68Ed026d694621f6FDfD` |

★broadcast 前に上記を Uniswap 公式 docs で最終照合すること（本手順は 2026-08-29 時点）。
