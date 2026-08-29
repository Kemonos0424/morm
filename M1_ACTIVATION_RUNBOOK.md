# M1 — L1 treasury 多重署名 有効化 runbook（GO後に実行）

状態: **relayer改修済＋ローカル検証PASS。有効化は未実行（不可逆ゆえユーザーGO待ち）。**
`REGISTER_TREASURY_SIGNERS` は原・単一鍵treasuryのみ・**一度きり**。有効化後、treasury限定kind（BRIDGE_MINT/REGISTER_AI_SERVICE/REGISTER_PRODUCER/FINALIZE）は `MULTISIG_TX` 経由 M-of-N 必須。

## 影響範囲（精査済）
- **MORM Play の payout は無傷**（kind:6 TRANSFER＝treasury限定でない）。
- 影響は **relayer reverse（exit→L1 credit＝BRIDGE_MINT）だけ**。改修済 `_credit_l1`（`TREASURY_SIGNER_SEEDS`設定時に `MULTISIG_TX` ラップ）で対応。
- L1 treasury署名者は **Ed25519**（EVMの `SIGNER_PKS` とは別鍵）。

## 検証済み（ローカルsandbox・本番未接触）
`scratchpad/ms_validate.py`: 有効化→`MULTISIG_TX(BRIDGE_MINT)`で着金／有効化後の単一鍵BRIDGE_MINT拒否／同一evm_lock_id冪等 — 全PASS。relayerの `_credit_l1` multisig分岐と同一構築。

## 実行手順（GO後）
0. **切替中のexit窓をゼロに**: guardian multisig（`0x9eb4…4599`・2-of-3）で `setPaused(true)`（`exit()`がblockされる）。※M3の GuardianMultisig.execute 経由。
1. **Ed25519 treasury署名者を3本生成（Mac Mini・600保管）**:
   `python -c "from morm_l1 import crypto;[print(crypto.keygen()[0].hex()) for _ in range(3)]"` → `~/.morm-l1/treasury-signers.env`（600）へ。pubkeyは `crypto.pubkey_from_seed`。
2. **改修版 relayer を Mac Mini へ配置**: `scp ~/Desktop/MORM/export_relayer.py user@100.106.58.67:~/Desktop/MORM/`（※本番relayerの実体パスに合わせる）。まだ `TREASURY_SIGNER_SEEDS` は設定しない。
3. **REGISTER_TREASURY_SIGNERS を投入（不可逆）**: 原・単一鍵treasury（`~/.morm-l1/producer.seed`）で署名。CLIサブコマンド無しゆえライブラリ構築:
   ```python
   from morm_l1 import crypto; from morm_l1.tx import Transaction
   t_seed=open(...).read(); t_pub=crypto.pubkey_from_seed(t_seed); t_addr=crypto.address(t_pub)
   sp=[{"pubkey":crypto.pubkey_from_seed(s).hex(),"name":f"sig{i}"} for i,s in enumerate(signer_seeds)]
   nonce=GET /account/{t_addr}.nonce
   tx=Transaction.register_treasury_signers(t_pub,nonce,signers=sp,threshold=2).sign(t_seed)
   POST http://127.0.0.1:8900/tx  (Mac Mini localhost)
   ```
   treasury nonce が +1 したら有効化完了。
4. **relayer を multisig モードへ**: `.relayer.env` に `TREASURY_SIGNER_SEEDS=<seed1,seed2,seed3>` と `TREASURY_MS_THRESHOLD=2` を追記→ relayer 再起動。起動ログに `reverse=MULTISIG (3 signers, threshold 2)` が出ること。
5. **guardian で `setPaused(false)`**（exit再開）。
6. **reverse 実ループ再検証**: Base で少額 `exit()` → 数ブロック後に L1 の宛先 m0r に MORM が credit されること（relayer が `MULTISIG_TX(BRIDGE_MINT)` を送出）。
7. メモリ `reference_morm_usd_market` の M1 を DONE に更新。

## ロールバック不可の注意
`REGISTER_TREASURY_SIGNERS` は取り消せない。手順3の前に、署名者seed 3本が確実に保管され（紛失=treasury機能停止）、relayerがそれらを持つことを確認。署名者集合の変更は現状の実装では不可（要 L1 側の署名者ローテ機構＝別課題）。
