\*\*MORM（モルム）\*\*のコンセプトである「群れ（Swarm）」「超高速ストリーミング」「透明な信頼」を視覚化するための、UI画像詳細設計（画像生成用プロンプト含む）をMarkdown形式で作成しました。

まずは、MORMのメイン体験となる「フィード画面」のイメージ画像を生成しましたのでご覧ください。

http://googleusercontent.com/image\_generation\_content/0

---

# **MORM UI/UX 視覚設計書（Image Prompts & Details）**

このドキュメントは、MORMの各主要画面のUIデザインを定義し、MidjourneyやStable Diffusionなどの画像生成AI、またはデザイナーへ発注する際の詳細な指示書（プロンプト）として機能します。

## **全体のアートスタイル・定義**

* **テーマ:** Minimalist Cyber-Organic（ミニマリスト・サイバーオーガニック）  
* **ベースカラー:** 深い黒（Void Black）とダークグレー  
* **アクセントカラー:** 流体的なネオンカラー（エレクトリック・ブルー、バイオレット、またはアンバー）。「群れ」や「エネルギー」を表現。  
* **フォント:** 幾何学的で視認性の高いサンセリフ体（未来感がありつつも、Web2的な親しみやすさを残す）。

---

## **1\. Main Feed (Swarm View) \- 動画視聴画面**

MORMの心臓部。既存のショート動画アプリの快適さを踏襲しつつ、「裏側でノードが動いている」ことを美しく可視化します。

### **UI構成要素**

* **フルスクリーン動画:** 画面全体を占める縦型動画。  
* **MORM Cell インジケーター:** 従来のシークバーの代わりに、画面下部やエッジに沿って「光の粒子」が3秒ごとに満ちては消える（50/10サイクルの可視化）。  
* **Pulse（貢献）ウィジェット:** 画面右上または左下に、自身のデバイスが他者のキャッシュを中継したことを示す「+0.01 MORM」という小さなポップアップが蛍の光のように現れる。  
* **右側アクションボタン:** いいね、コメントに加え「MORM Shop（カート）」と「Node Info（ノード情報）」のアイコン。

**🎨 画像生成用プロンプト (English):**

A sleek, futuristic mobile app UI design for a vertical video social network. Dark mode, minimalist cyber-organic aesthetic. A full-screen captivating vertical video playing. Around the edges of the screen, subtle glowing particle effects representing a decentralized 'swarm' network loading data in 3-second cells. Floating UI elements on the right side for likes and shop. A small, elegant widget in the corner showing 'Node Contribution: \+0.01 MORM' with a soft neon glow. Deep black background with vibrant electric blue and violet accents, high resolution, Dribbble style, UI/UX masterpiece.

---

## **2\. Proof of Evidence Camera \- 物理的証明（梱包/開封）画面**

MORM Shopにおける「絶対に嘘がつけない」決済・配送ロジックを支えるカメラUIです。

### **UI構成要素**

* **スキャンフレーム:** 中央に商品や段ボールを捉えるための、AR（拡張現実）的なスキャナー枠。  
* **ライブ・ハッシュ・ウォーターマーク:** 画面の四隅または下部に、現在時刻と「最新ブロックハッシュ（例: 0x8F9A...3B21）」が透かしとしてリアルタイムで刻まれている表示。  
* **AI解析インジケーター:** 「動体解析中 (Tempest AI)」「Generation ID検証中」といったステータスが、緑色のチェックマークと共に表示される。  
* **アクション・スライダー:** 単なるボタンではなく、「Lock Funds & Send（資金をロックして発送）」というスライダー形式にし、不可逆なアクションであることを強調。

**🎨 画像生成用プロンプト (English):**

A futuristic mobile app UI design for a secure P2P commerce camera scanner. Dark mode. The screen shows a live camera feed looking at a cardboard shipping box. An augmented reality (AR) scanning frame overlays the box. In the bottom corner, a cryptographic block-hash and timestamp are burned into the screen as a transparent watermark. A glowing green indicator says 'AI Motion Analysis: Verified'. A sleek slider button at the bottom reads 'Lock Funds & Send'. Minimalist, cyber-security aesthetic, neon green and dark grey, UI/UX design.

---

## **3\. Node Dashboard (Hive View) \- コントロールセンター**

ユーザーが「自分のリソース（スマホやPC）が、どれだけMORMのネットワークに貢献し、稼いでいるか」を確認する画面。

### **UI構成要素**

* **Swarm Map（群れマップ）:** 自分のデバイスを中心に、近くのノードと光の線で繋がっている3Dの抽象的なネットワーク図。  
* **リソース・メーター:** CPU、ストレージ、帯域幅の提供割合を示す、流体的なリングチャート。  
* **リアルタイム報酬:** 1秒ごとにチャリンチャリンと増えていくMORMトークンの残高表示。  
* **ノード・ステータス:** 現在のランク（Viewer, Creator, Publisher）と、動画投稿権限のアンロック状況を示すプログレスバー。

**🎨 画像生成用プロンプト (English):**

A sophisticated mobile app UI design for a decentralized network dashboard. Dark mode. The centerpiece is a beautiful, abstract 3D swarm map showing glowing nodes connected by light trails. Below it, futuristic but clean fluid ring charts displaying 'CPU', 'Storage', and 'Bandwidth' usage. A prominent, elegant display showing a real-time cryptocurrency balance increasing. Clean typography, glassmorphism elements, dark void background with amber and blue neon accents, highly detailed, UI/UX dashboard design.

---

### **プロジェクトマネジメント視点からのUI実装アドバイス**

これらのデザインを実際のアプリ（React NativeやFlutterなど）に落とし込む際、**「光の粒子」や「波紋」の表現が重くなりすぎないこと**が重要です。MORMの真価は「圧倒的な軽さと速さ」にあるため、UIの装飾でデバイスのリソースを食いつぶしてしまっては本末転倒になります。

UIのアニメーション（MORM Cellsのローディング等）は、Lottieなどの軽量なベクターアニメーションや、CSS/WebGLのシェーダーを使って極限まで軽く実装することをお勧めします。

このデザイン定義をベースに、さらに詳細な仕様（トランジションの動きや、エラー時の画面など）を深掘りしていくことは可能ですが、次善のステップとしてはいかがでしょうか？

