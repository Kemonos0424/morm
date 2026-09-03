# MORM Wallet (Chrome extension)

MORM 純正のノンカストディアル・ウォレット。第1形態は **Chrome 拡張 (MV3)**。
本番クライアント `https://www.morm.one/account.html` と暗号プリミティブ・アドレス・
リカバリー形式が **完全互換**で、`morm-l1` (Python) の署名とも**バイト一致**。

設計と決定の正本は `~/.claude` メモリ `project_morm_wallet_extension.md`。

## レイアウト

```
morm-wallet-ext/
  packages/wallet-core/     @morm/wallet-core — 依存ゼロの共有コア(全端末で再利用)
    src/                    blake2b / base32 / address / canonical / ed25519 / tx / recovery / vault / rpc
    test/golden.test.mjs    Python↔TS バイト一致のゴールデンベクタ(コアの背骨)
    test/golden.json        ↑の期待値(tools/gen_golden.py が生成)
  extension/                MV3 拡張スキャフォールド(manifest/背景/ポップアップ/アイコン)
  webauthn-ror/             morm.one に置く Related Origins 設定(同一passkey解錠用)
  tools/gen_golden.py       morm-l1 から期待値を生成
```

## 開発

```bash
# ゴールデンベクタ再生成(morm-l1 の Python 正本から)
python3 tools/gen_golden.py

# コアのバイト一致テスト
cd packages/wallet-core && node --test
```

拡張を読み込む前に **ビルド**（`wallet-core` を `extension/walletcore/` にコピー。
`extension/walletcore/` は生成物なので `.gitignore` 済み＝clone 後は必ず実行）:

```bash
node tools/build_ext.mjs
```

Chrome で読み込む(unpacked): `chrome://extensions` → デベロッパーモード →
「パッケージ化されていない拡張機能を読み込む」で `extension/` を指定。
固定 ID = `enmmpmpjbdplcglnncnkjbebehddbeka`(manifest の `key` 由来)。
ソース編集後は `node tools/build_ext.mjs` を再実行 → 拡張をリロード。

## 確定仕様(要点)

- 署名 = **ed25519**(WebCrypto)。seed = 生 32byte。
- アドレス = `m0r` + base32(BLAKE2b-256(pubkey) 末尾20byte)、**チェックサム無し**。
- tx 署名対象 = `{kind,nonce,payload,sender}` の**正準JSON**(各階層キー昇順・compact)。送金 = `kind 6`。
- リカバリー = `morm-rk1-<base32(seed)>`(web と相互運用の橋)。
- 保管 = AES-GCM。鍵導出 = **パスキー PRF→HKDF**(web と同一)/ パスワード→PBKDF2。
- 解錠 = **morm.one と同一 passkey**(要 `webauthn-ror/` を morm.one に設置)。

## セキュリティ実装方針(Phase 1 で必須)

- リカバリーキーは生シード。1回表示・伏字・スクショ警告・コピー後クリップボード自動クリア・入力欄は使用後即クリア。
- 送金はチェックサム無し前提で **ハンドル解決 + 明示確認必須**、手打ち警告、先頭/末尾強調。
- 復号 seed はメモリのみ・署名の瞬間だけ・アイドル/ロックで即破棄。storage は暗号文のみ。
- tx 確認 UI で金額/宛先/kind を人間可読表示(盲目署名させない)。
- CSP 厳格・外部スクリプト無し・API は `api.morm.one` 固定・`externally_connectable` は morm.one 限定。

## セキュリティ注意(鍵の取扱い)

拡張の**署名用秘密鍵** `morm-ext-key.pem` はリポジトリに含めない(スクラッチパッドに退避済み)。
Web Store 公開時に必要になるので**安全に保管**すること。マニフェストの `key`(公開鍵)は
コミット可。リポジトリは公開のため、いかなる seed / 秘密鍵もコミットしないこと。
