# MORM wMORM ブリッジ — 監査準備パッケージ / 脅威モデル・自己監査

作成: 2026-08-10 ／ 対象コミット状態: forge test 52/52 PASS（本書末尾に実測）
目的: 外部監査に渡せる「スコープ・信頼モデル・自己監査・既知リスク・メインネット前チェックリスト」を1枚に。

---

## 1. スコープと成果物

| 種別 | 実体 | 役割 |
|---|---|---|
| コントラクト | `src/WMORM.sol`（107行） | wMORM ERC-20（mint/burnはbridge限定） |
| コントラクト | `src/MORMExportBridge.sol`（207行） | M-of-N フェデレーテッド mint/burn ブリッジ |
| （既存/対象外） | `src/MORMBridge*.sol` `MORMEscrow.sol` `MockUSDC.sol` | 旧PoC/テスト用。今回の実運用経路ではない |
| オフチェーン | `~/Desktop/MORM/export_relayer.py` | 閾値署名リレーヤ（forward/reverse） |
| L1 | `~/Desktop/MORM/morm-l1/morm_l1/`（state.py/tx.py 他） | native MORM チェーン（bridge_burn/mint, treasury多重署名） |
| デプロイ済（Base Sepolia 84532） | WMORM `0x5cd8…c74C` / Bridge `0xF7A4…A818` / USDC `0x2B66…f453` / Pool `0x9E62…5789` | 実チェーン稼働・Uniswap v3プールLIVE |

依存: forge-std のみ（コントラクトは外部依存ゼロ・自己完結）。solc `^0.8.20`（checked算術）。

---

## 2. アーキテクチャと信頼モデル

- **Forward（L1 MORM → Base wMORM）**: ユーザーがL1で `BRIDGE_BURN`（native残高をburn）→ リレーヤのN署名者が各自 **L1のburnを独立検証してから** `mintDigest(recipient,amount,mormBurnId)` に署名 → ≥threshold署名を集約し `mintFromBurn` で wMORM を mint。
- **Reverse（Base wMORM → L1 MORM）**: ユーザーが `exit(amount, mormAddress)` → wMORM burn＋`Exit`イベント → リレーヤが `EVM_CONFIRMS` ブロック確認後に L1 `BRIDGE_MINT`（treasury）で MORM を credit。
- **信頼の核**: フェデレーテッド＝**署名者の正直多数**。コントラクトはL1のburnを自前検証できない（できない設計）。安全性は「署名者quorumの健全性＋回路ブレーカ（レート制限/絶対上限/guardian pause）」で担保。
- **スケール**: 1 L1 MORM = 1e18 wMORM-wei（リレーヤの `L1_MORM_SCALE`）。

---

## 3. 自己監査（コントラクト）

重大度: Critical / High / Medium / Low / Info。状態: 緩和済 / testnet許容 / **メインネット前に修正** / 情報。

### 3.1 MORMExportBridge.sol
| ID | 重大度 | 所見 | 状態 | 参照 |
|---|---|---|---|---|
| B-1 | Info(強) | mint digest が `(address(this), chainid, "MORMExportBridge:mint", recipient, amount, mormBurnId)` に束縛 → クロスチェーン/クロス契約リプレイ不可 | 緩和済（敵対テスト実証） | `MORMExportBridge.sol:184-190` |
| B-2 | Info(強) | 署名は**厳密昇順**で重複排除＋`low-s`(HALF_N)強制＝マレアビリティ不可 | 緩和済（敵対テスト実証） | `:127-134, 202` |
| B-3 | Info(強) | `minted[mormBurnId]` one-shot ＋ CEI（flag/accrueを`token.mint`前に）＝二重mint/リエントランシ無し | 緩和済 | `:118, 140-144` |
| B-4 | Info(強) | 二重の回路ブレーカ: 窓レート制限 `maxMintPerWindow` ＋ **絶対上限 `maxSupply`** → quorum漏洩でも被害を上限で封じる。guardian `pause()` | 緩和済 | `:138, 158-167, 170-174` |
| **B-5** | **Medium** | **署名者ローテ不可**。`signers`/`threshold`はconstructorで固定・変更関数なし。署名者鍵の紛失/漏洩時、pause以外に復旧手段がない | **メインネット前に修正**（timelock付きローテ or 再デプロイ移行手順） | `:34-35, 94-99` |
| **B-6** | **Medium(=M3)** | **guardian が単一EOA**。pauseとguardian移譲の権限が1鍵に集中 | **✅ 対応済(2026-08-10)**: guardian を **2-of-3 GuardianMultisig `0x9eb4c134A85c707E10D3413d757a2ba938B94599`**（Base Sepolia）へ委譲。署名者はブリッジ署名者と**別鍵**（責務分離）。pause/unpause制御を実チェーンで実証。※mainnetはtimelock追加＋鍵の物理分散が残 | `:42, 169-181` / `src/GuardianMultisig.sol` |
| B-7 | Low(=M2) | レート制限が**タンブリング窓**（境界で最大2×maxMintPerWindow）。ただし絶対上限`maxSupply`が全体を封じる | testnet許容（`maxSupply`で緩和・境界テスト有） | `:159-167` |
| B-8 | Low | リレーヤ**submitter単一鍵**（gas支払い＋mintFromBurn送信）。漏洩でも署名が無ければ偽造不可＝検閲/griefingに限定 | testnet許容 | relayer `SUBMITTER_PK` |
| B-9 | Info | `mintFromBurn`の`amount`は署名者の属性証明でありコントラクトはL1 burnと独立照合しない（＝信頼モデル通り）。リレーヤ側 `verify_and_sign` がL1 burnと recipient/amount/token 一致を各署名者が独立検証 | 情報（設計） | relayer `Signer.verify_and_sign` |

### 3.2 WMORM.sol
| ID | 重大度 | 所見 | 状態 | 参照 |
|---|---|---|---|---|
| W-1 | Info(強) | mint/burn は `onlyBridge`。`setBridge` は deployer が**一度だけ**配線→以降deployerもmint権なし。供給=L1 export量の鏡 | 緩和済 | `WMORM.sol:37-55, 88-106` |
| W-2 | Low | `burn(from, value)` は任意`from`をburn可能だがbridge限定。現状 `exit()` のみが `burn(msg.sender)` で呼ぶ＝他人残高burn不可。将来bridgeに別のburn呼出しを足す際は`from`拘束を要確認 | testnet許容（不変条件） | `WMORM.sol:95-106`, `Bridge:154` |
| W-3 | Medium | 手起こしERC-20（permit無し・OZ非採用）。監査簡便化のため意図的だが、**メインネットは監査済OZ ERC-20 + ERC-2612 permit へ差替**をコメントで明記済 | **メインネット前に差替** | `WMORM.sol:11-13` |
| W-4 | Info | `totalSupply += value`(mint)は0.8のchecked算術（overflow revert）。`balanceOf`加算のみunchecked（totalSupply/ maxSupplyで有界） | 情報 | `WMORM.sol:90-91` |

### 3.3 リレーヤ（export_relayer.py）
| ID | 重大度 | 所見 | 状態 |
|---|---|---|---|
| R-1 | Info(強) | forward=**verify-before-sign**（各署名者がL1 burn行と recipient/amount/token 一致を検証してから署名）。冪等: on-chain `minted[burnId]` ＋ L1 `bridge_mints(evm_lock_id)` | 緩和済 |
| R-2 | Info | reverse=`Exit`監視→`EVM_CONFIRMS`(3)ブロック確認後にL1 `BRIDGE_MINT`。宛先=treasuryにすると差引0になるため別アドレス検証（既知の注意） | 情報 |
| **R-3** | **Medium(=M1)** | reverse の L1 `BRIDGE_MINT` は **treasury単一鍵**署名（treasury多重署名を有効化していない現状）。メインネット前に**L1 treasury多重署名を有効化し、リレーヤreverseを`MULTISIG_TX`ラップへ改修**が必須 | **M1で対応**（下記§6） |
| R-4 | Low | reverse の `last_block` 未永続化・launchd未化（プロセス断で取りこぼし/巻き戻しリスク） | 運用堅牢化（別途） |

### 3.4 L1（state.py / tx.py）
| ID | 重大度 | 所見 | 状態 |
|---|---|---|---|
| L-1 | Info(強) | treasury限定kind `{BRIDGE_MINT, REGISTER_AI_SERVICE, REGISTER_PRODUCER, FINALIZE}` は多重署名有効化時に M-of-N（`_tx_multisig_tx`・treasury_nonceで再送防止・cosig昇順dedup） | 情報（有効化はM1） |
| L-2 | Info | nonce厳格・locked口座拒否・`tx.verify()`必須。bridge_burnは`evm_recipient`=0x+40hex必須、native残高debit | 情報 |
| L-3 | Medium | 現状**単一ノード/treasury=producer**。genesis lockdown(height<100はtreasury署名ブロックのみ)。分散化・複数producerはメインネット設計事項 | メインネット設計 |
| L-4 | Info | treasury seed=`~/.morm-l1/producer.seed`（Mac Mini・producer兼務）。単一障害点＝運用上の要保護 | 運用 |

---

## 4. 脅威モデル（攻撃者シナリオ → 防御）

1. **署名者quorum漏洩で無限mint** → `maxSupply`絶対上限＋窓レート制限＋guardian pause で被害を上限化・人間介入猶予（B-4）。**残**: 署名者ローテ不可（B-5）ゆえ、漏洩後の恒久対処は再デプロイ移行。
2. **署名の別チェーン/別契約リプレイ** → digest束縛で不可（B-1・敵対テスト）。
3. **署名マレアビリティ/重複で threshold 水増し** → low-s＋厳密昇順dedup で不可（B-2）。
4. **同一L1 burnで二重mint** → `minted[burnId]` one-shot（B-3）。
5. **guardian鍵漏洩** → mint権は無く資金流出不可。pause解除/guardian移譲によるDoS・ガバナンス乗っ取りに限定（B-6＝M3で多重署名化）。
6. **reverse の L1 credit 偽造** → treasury権限が要る。**現状treasury単一鍵**（R-3＝M1で多重署名化必須）。
7. **リレーヤsubmitter漏洩** → 署名無しでは偽造不可、検閲/griefingのみ（B-8）。
8. **プールへの操作（価格操作）** → testnetの薄い流動性ゆえ容易だが実害は表示価格のみ。メインネットはLP厚み・オラクル設計事項。

---

## 5. テスト実測（証跡）

- `forge test` = **52 passed / 0 failed / 0 skipped**（7スイート）。内訳: MORMExportBridge 12、Adversarial 8（クロスチェーン/クロス契約リプレイ拒否・high-s拒否・降順拒否・宛先束縛・絶対上限・最小exit・レート境界）、他既存32。
- 未実施（監査で推奨）: フォーマル検証/シンボリック実行（Halmos/Certora）、ファズ拡充、gasグリーフィング、外部監査。

---

## 6. メインネット前チェックリスト（優先度順）

- [ ] **M1（R-3/L-1）**: L1 treasury 多重署名を有効化（`REGISTER_TREASURY_SIGNERS`）し、**リレーヤreverseを `MULTISIG_TX` ラップに改修**→ reverse全ループ再検証。※`REGISTER_TREASURY_SIGNERS`は**一度きり**・原単一鍵のみ実行可＝署名者集合/閾値を確定してから。※MORM Playのpayoutは`TRANSFER`(非treasury限定)ゆえ影響なし。
- [x] **M3（B-6）✅**: bridge guardian を **2-of-3 GuardianMultisig `0x9eb4…4599`** へ委譲済（署名者=ブリッジ署名者と別鍵・pause/unpause実証）。残: mainnetでtimelock追加＋guardian鍵の物理分散・ローテ運用。
- [ ] **B-5**: 署名者ローテ機構（timelock付き）を追加、または再デプロイ移行runbookを用意。
- [ ] **W-3**: WMORM を監査済OZ ERC-20 + ERC-2612 permit へ差替。
- [ ] **R-4**: リレーヤ launchd/systemd 常駐化＋reverse `last_block` 永続化。
- [ ] 外部監査（コントラクト＋リレーヤ＋L1 bridgeパス）＋フォーマル検証。
- [ ] 実LP拠出・自由売買の**法務ゲート**（金商法/資金決済法・[[feedback_morm_design]] 法人なし方針）—技術ではなく事業判断。

---

## 7. 監査人への引き継ぎメモ
- コントラクトは意図的に手起こし・依存ゼロ（可読性重視）。信頼モデルは明示的にフェデレーテッド（正直多数）。
- 「ペグ」ではなく**フロート**（1 wMORM=$0.01は発行内部基準、市場はプールで変動）。ステーブルコインではない。
- 実チャート: https://morm-market.zoku.one ／ dapp: https://morm-market.zoku.one/app.html ／ 価格API: https://api.morm.one/api/price 。
