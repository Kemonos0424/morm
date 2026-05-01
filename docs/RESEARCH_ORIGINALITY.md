# MORM 技術スタック オリジナリティ調査

**Date**: 2026-04-25
**Status**: Internal — ホワイトペーパー記述の調整に使用

---

## 結論サマリー

MORMは**プリミティブ発明ではなく、システム統合プレイ**。10要素中8要素には直接的な先行プロジェクトが存在する。「初の発明」ではなく「初の統合スタック」として位置づけるのが誠実かつ強い。

### 真のモート（オリジナリティ・モート）3つ

| # | 要素 | 評価 |
|---|---|---|
| 1 | **梱包/開封動画 + ブロックハッシュ透かし + スマコン解放条件** | 学術プロトタイプのみ。商用シップなし。**最強候補** |
| 2 | **不正検知時のSlash + 生体認証レベル永久ban** | Worldcoin/HumanityはSybil防止のみ。詐欺Slashとの結合は未シップ。法的リスク注意 |
| 3 | **トランスコード + AI推論 + 配信を統合したPoUWを動画L1の合意基盤に** | Livepeerは合意基盤ではなく報酬層。統合は未シップ |

### 過剰主張に注意すべき要素

| # | 要素 | 既存プロジェクト |
|---|---|---|
| 2 | 分散型ショート動画SNS | **Chingari (5M DAU)**、TokTok、CanCan、TALORA、DTube、Odysee、3Speak |
| 4 | Walletless ID（Passkey + 生体 + 復旧） | **Coinbase Smart Wallet**、Privy、Magic.link、Web3Auth |
| 6 | V-Hash重複検知 | YouTube Content ID、Audible Magic、pHash（15年来の標準技術） |
| 7 | Generation ID（AI動画証明） | **C2PA、SynthID、Numbers Protocol (ERC-7053)、Truepic** |
| 9 | 1%固定手数料 | Immutable X他多数。マーケティング表現に過ぎない |
| 1 | 3秒キャッシュ50%/10%サイクル | HLS/DASH + Akamai prefetch + LL-HLS。数値チューニングのみ |

---

## 要素別詳細

### 1. 3秒WebMセグメント + 50%/10%予測キャッシュ
**評価**: Common（既存プリフェッチ + エビクションのパラメータ調整）
- HLS/DASH（標準2-10秒）、Akamai Segment Prefetch、LL-HLS `EXT-X-PRELOAD-HINT`
- TikTok/Douyin/Kuaishouは既に積極的プリフェッチ実装
- 学術: Gamora（バッファ認識プリロード）

### 2. 分散型縦型ショート動画SNS
**評価**: Already done
- **Chingari** (Solana, 5M DAU, 200M videos/day)
- TokTok, TALORA, CanCan (DFINITY), DTube, Odysee, 3Speak, Audius, Lens, Subsocial

### 3. PoUW（動画トランスコード/AI/配信を合意基盤に）
**評価**: Novel combination
- Livepeer = トランスコード + AI、Theta = 配信、Filecoin = ストレージ、Bittensor = AI推論
- 「3つを単一PoUWに統合」は未シップ。**ただしフレーミング注意**: 「初のPoUW」ではなく「トランスコード+AI+配信統合の初のPoUW」

### 4. Walletless ID（Passkey/生体 + デバイス縛り + 社会復旧）
**評価**: Already done
- Coinbase Smart Wallet、Privy（TEE）、Web3Auth（MPC）、Magic.link、ERC-4337+WebAuthn
- 2025-2026時点でコモディティ化

### 5. Proof of Physical Evidence（梱包/開封動画 + ブロックハッシュ透かし）
**評価**: Novel combination ⭐ **最強モート候補**
- OpenBazaar/Particl/Originは2-of-3 multisigエスクローのみ（動画必須なし）
- Princeton学術論文（block hash in video for "filmed after T"）
- 「商用P2Pコマースでブロックハッシュ透かし動画を解放条件にする」は未シップ

### 6. V-Hash + オーディオ・フィンガープリント
**評価**: Common
- YouTube Content ID、Audible Magic、pHash.org、VideoHash
- 「最初の投稿者がオンチェーンで勝つ」ルールは学術プリアートあり

### 7. Generation ID（AI動画オンチェーン証明）
**評価**: Already done
- **Numbers Protocol + ERC-7053 + C2PA**でほぼカバー済み
- SynthID（Google）、Truepic、Adobe CAI、Sora（C2PAマニフェスト出力）
- 「C2PA準拠のオンチェーン証明をSNSフィードに統合」と再フレーミング推奨

### 8. Node-Lock + Slash + 生体認証レベル永久ban
**評価**: Novel combination ⭐
- Slashing（Eth/Cosmos/Polkadot）は標準
- Worldcoin/Humanity Protocol/Civicは生体Sybil防止のみ
- 「不正のSlashと生体永久banの結合」は未シップ
- ⚠️ **GDPR/忘れられる権利との衝突に注意**

### 9. 1%固定手数料（不変スマコン）
**評価**: Common
- マーケティング・ポジショニング。技術的にはproxyなしの非更新可能契約
- 信頼性の根拠は「実際にadmin keyがない」ことの検証可能性

### 10. DAG型独自L1 + PoUW + QUIC
**評価**: Novel combination（低確信度）
- 各要素は成熟（IOTA/Hedera/Sui = DAG、libp2p QUIC = 標準）
- 「ショート動画SNS専用appchainでDAG+PoUW+QUIC統合」は未シップ。Livepeerが最も近いがEthereum L2

---

## ホワイトペーパー記述への提言

### 修正すべき箇所

| 現状の記述 | 修正案 |
|---|---|
| 「分散型なのに速い」を独自性として強調 | 「TikTok級UXを独自統合スタックで」へ調整。先行例を脚注で言及 |
| 「Walletless ID」をMORM固有機能として強調 | 「業界標準のPasskey/FIDO2をMORM内動作として深く統合」へ |
| 「Generation ID」を独自概念として | 「C2PA/ERC-7053準拠のチェーン記録」と明示 |
| 「V-Hash」を新技術として | 「業界標準の知覚ハッシュ + オンチェーン優先順位ルール」へ |

### 強調すべき箇所（モート）

1. **Proof of Physical Evidence**: 「商用シップ初のブロックハッシュ透かし型エスクロー」
2. **Slash + 生体永久ban**: 「Sybil防止だけでなく、不正に対する生体永久排除を組み込んだ初のP2Pコマース」（GDPR配慮の文言追加）
3. **動画特化PoUW L1**: 「トランスコード・AI・配信を単一合意基盤に統合した初の動画L1」

### 比較表の追加を推奨

ホワイトペーパーに以下のような正直な比較表を入れると、信頼性が大幅に上がる：

| 機能 | MORM | Chingari | Livepeer | Theta | Numbers | C2PA |
|---|---|---|---|---|---|---|
| 短動画SNS | ✓ | ✓ | - | - | - | - |
| トランスコードPoUW | ✓ | - | ✓ | - | - | - |
| 配信PoE/PoUW | ✓ | - | - | ✓ | - | - |
| AI推論PoUW | ✓ | - | ✓ | - | - | - |
| AI証明（C2PA系） | ✓ | - | - | - | ✓ | ✓ |
| 物理エビデンスエスクロー | ✓ | - | - | - | - | - |
| 生体永久ban | ✓ | - | - | - | - | - |
| Walletless ID | ✓ | 部分 | - | - | - | - |

---

## 法的・倫理的フラグ

- **生体認証永久ban**: GDPR、CCPA、APPIで「生体情報の処理」「忘れられる権利」と衝突可能性。利用規約の同意設計が要
- **C2PA非互換のGeneration ID**: 標準と乖離するとEU AI Act等の将来規制対応で不利。**C2PA互換実装を強く推奨**
- **「初の○○」表現**: 法的リスクは低いが、競合からの反論で信頼性を失う。慎重な表現に

---

## 主要参考リンク

- [Chingari](https://getblock.io/marketplace/projects/chingari/)
- [Livepeer Whitepaper](https://github.com/livepeer/wiki/blob/master/WHITEPAPER.md)
- [Theta Network](https://s3.us-east-2.amazonaws.com/assets.thetatoken.org/Theta+white+paper+11.07.17.pdf)
- [Coinbase Smart Wallet Passkeys](https://help.coinbase.com/en/wallet/getting-started/smart-wallet-passkeys)
- [C2PA](https://c2pa.org/wp-content/uploads/sites/33/2025/10/content_credentials_wp_0925.pdf)
- [Numbers Protocol](https://numbersprotocol.io/)
- [Worldcoin World ID](https://world.org/world-id)
- [Humanity Protocol](https://www.humanity.org/protocol)
- [OpenBazaar](https://en.wikipedia.org/wiki/OpenBazaar)
- [Princeton: Block hash in video](https://www.cs.princeton.edu/~arvindn/publications/cryptocurrency-escrow.pdf)
- [libp2p QUIC](https://libp2p.io/docs/quic/)
