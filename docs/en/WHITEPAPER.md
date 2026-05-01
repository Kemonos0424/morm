# MORM Whitepaper

**Version**: 0.2 (Draft)
**Date**: 2026-04-25
**Status**: Pre-Launch / Concept
**Tagline**: *The Swarm for Every Frame*

---

## 0. Executive Summary

### What we're building

MORM integrates **TikTok-class short-video experience** and **fraud-proof P2P commerce** on top of **fully decentralized infrastructure**. It is a substitute for parts of the existing SNS, payments, storage, CDN, and e-commerce stack — combined into one.

### Why now

Three transformations converge in 2026:

1. **The creator-economy meltdown** — frustration with 30% fees, sudden shadow-bans, and unauthorized AI training has reached a breaking point.
2. **Web3 UX maturity** — Passkey/FIDO2, ERC-4337, and C2PA standardization finally make blockchain usable without seed phrases.
3. **The flood of AI-generated content** — the social demand for provenance proof has become decisive, with regulations (EU AI Act, etc.) coming into effect.

### Total Addressable Market (TAM)

| Segment | Size | Source |
|---|---|---|
| Short-video SNS | ~$300B/year | Statista 2026 forecast |
| Creator economy | ~$104.1B | CB Insights |
| C2C commerce | $650B+ | eMarketer |
| DePIN | $3.2B → rapidly growing | Messari |
| **Combined TAM** | **>$1T** | — |

### Honest positioning

MORM is **not the inventor of new primitives**. This whitepaper takes the honest stance of acknowledging prior art for each component, while claiming value as the **first integrated stack**.

The genuine moats narrow to three:

1. **Proof of Physical Evidence (PoPE)** — escrow release gated on block-hash watermarked packing/unboxing videos (**first commercial implementation**)
2. **Slash + biometric permanent ban** — combining stake forfeiture with biometric-level permanent network exile (**no precedent**)
3. **Video-specialized unified PoUW L1** — the first video L1 unifying transcoding + AI inference + delivery in a single consensus base

### Operational structure declaration

MORM **has no legal entity**. No Corporation. No Foundation. No DAO LLC. Instead, operations run on three layers:

- **Smart Contracts** (immutable money flow)
- **AI Agents** (autonomous daily operations)
- **DAO** (parameter setting)

See [AGENTS.md](AGENTS.md) for details.

---

## 1. Problem Statement

### 1.1 Limits of centralized platforms

| Issue | Reality |
|---|---|
| Opaque censorship | TikTok shadow-bans, YouTube DMCA abuse |
| High fees | App Store/Google Play 30%, Meta/TikTok 50%+ on virtual gifts |
| Sudden policy changes | Repeated shifts in YouTube monetization rules |
| Loss of data sovereignty | Personal data owned by corporations, training AI for free |

### 1.2 Limits of existing decentralized services

The "replace it with Web3" vision has been repeated for a decade. Why hasn't it caught on?

- **Latency** — IPFS-based delivery has multi-second to multi-tens-of-seconds load time
- **Complexity** — cognitive load of wallet management, gas, chain selection
- **Quality** — flood of spam, copies, low-quality content
- **Scale** — network effects could not beat centralization

### 1.3 Limits of P2P commerce

- OpenBazaar shut down in 2018 (trust failure)
- Multisig escrow alone cannot prevent fraud
- Existing P2P marketplaces still rely on intermediaries with 10–30% fees

**MORM addresses all of these — through precise integration of existing tech and a small number of original designs.**

---

## 2. Vision

### 2.1 North Star

> Censorship-proof, fraud-proof, low-fee video + commerce infrastructure, run on the spare resources of devices around the world. No one depends on a central authority.

### 2.2 5-Year KPI Goals

| Metric | Target |
|---|---|
| MAU | 100M |
| Active nodes | 10M |
| Annual transaction volume | $10B |
| Creators | 10M |
| Avg. playback start time | <300ms |
| Fraud rate | <0.01% |
| TVL (escrow) | $500M |

### 2.3 What MORM Is NOT

To avoid hype, we make this explicit:

- Not compatible with existing Web3 wallets (MetaMask intentionally unsupported)
- Not "the fastest blockchain"
- Not an investment vehicle (MORM Token is a utility token)
- Not a replacement for all SNS features (initially focused on short video + commerce)

---

## 3. Honest Comparison with Prior Art

### 3.1 Feature comparison matrix

| Feature | MORM | Closest Prior Art | Differentiation |
|---|---|---|---|
| Decentralized short-video SNS | ✓ | Chingari, CanCan, 3Speak | Full-stack integration |
| 3-second WebM segment streaming | ✓ | HLS/DASH, LL-HLS, TikTok prefetch | Predictive cache integrated with PoUW |
| Walletless ID | ✓ | Coinbase Smart Wallet, Privy | Linked to biometric ban |
| AI video provenance | ✓ | C2PA, Numbers Protocol, SynthID | C2PA-compliant + feed integration |
| Perceptual-hash dedup | ✓ | YouTube Content ID, pHash | On-chain priority rule |
| Transcoding PoUW | ✓ | Livepeer | Unified with delivery + AI |
| Delivery PoUW/PoE | ✓ | Theta Network | Unified with transcoding + AI |
| AI-inference PoUW | ✓ | Bittensor | Video-specialized |
| P2P commerce escrow | ✓ | OpenBazaar, Particl | PoPE mandatory |
| **PoPE (mandatory physical evidence)** | **✓** | **Academic only** | **First commercial ship** |
| **Fraud-Slash + biometric ban** | **✓** | **Worldcoin/Humanity (Sybil only)** | **First fraud-linked** |
| 1% immutable fee | ✓ | Immutable X, Particl | Verifiable via no admin key |
| DAG L1 | ✓ | IOTA, Hedera, Sui | Video-SNS specialized |
| QUIC P2P transport | ✓ | libp2p QUIC | Optimized for streaming |

### 3.2 The Three Genuine Moats

#### Moat 1: Proof of Physical Evidence (PoPE)

No commercial P2P-commerce protocol has shipped block-hash-watermarked video as a smart-contract escrow release condition.

OpenBazaar/Particl/Origin only support multisig escrow. Princeton's 2018 paper is a proof-of-concept that was never productized. MORM will be the first commercial implementation.

#### Moat 2: Slash + biometric permanent ban

Worldcoin and Humanity Protocol do Sybil resistance only — they do not network-wide ban malicious actors. MORM combines:

- Financial slashing (stake forfeiture)
- Biometric-level permanent network exile
- Technical impossibility of rejoining via a different device or wallet

Implemented with proper legal design (GDPR/APPI/CCPA-aware consent flows).

#### Moat 3: Video-specialized unified PoUW L1

Domains that are split across Livepeer (transcoding + AI), Theta (delivery), and Filecoin (storage) get unified into a single PoUW consensus base. The first video L1 to do this.

---

## 4. System Architecture

### 4.1 Network tiers

| Tier | Name | Resources | Role |
|---|---|---|---|
| Tier 1 | **Validator (NodePower)** | GPU, CPU, RAM, NVMe | Encoding, AI analysis, block production, verification |
| Tier 2 | **Edge Node** | SSD, broadband | Holding MORM Cells, high-speed delivery to nearby devices |
| Tier 3 | **Light Client** | Phone / PC / console | Viewing, UI, temporary cache relay |

All tiers are part of the P2P network. Light Clients also act as Edge Nodes when surplus resources permit.

### 4.2 Communication layer

- **QUIC (UDP-based)** across all tiers
- **WebAssembly + WebTransport** for browser-tier P2P participation
- libp2p as base, optimized for parallel streaming of 3-second segments

### 4.3 MORM Chain

| Item | Spec |
|---|---|
| Structure | DAG-based parallel block production |
| Consensus | Proof of Useful Work (PoUW) |
| Finality | Within seconds (fast finality) |
| Design | Stateless (Light Clients hold no history) |
| Throughput | Design target 100,000 TPS |

PoUW certifies "video transcoding," "AI analysis," "delivery," and "physical-evidence verification" as useful work — unifying rewards and consensus.

---

## 5. Streaming Protocol (MORM Cells)

### 5.1 Segment specs

| Item | Value |
|---|---|
| Format | WebM (VP9 / AV1) |
| Duration | 3 seconds |
| Frame rate | ≤ 30 fps |
| Size guideline | hundreds of KB to ~1 MB / segment |

### 5.2 50% / 10% caching cycle

```
[Playback start]
   ↓
0.3s (10%)  → Reserve next Cell in background
   ↓
1.5s (50%)  → Purge old Cell from memory
   ↓
3.0s (100%) → Seamlessly switch to next Cell
```

Memory consumption stays flat; playback never stalls.

### 5.3 Relation to prior art

3-second segments and prefetch are well-established in HLS/DASH (standard 2-10s), Akamai Segment Prefetch, LL-HLS's `EXT-X-PRELOAD-HINT`, and so on. MORM's contribution is:

- Parameter optimization (TikTok-class feel in a decentralized environment)
- Linkage with PoUW (prefetch work itself is a NodePower reward target)
- WebM-native (most decentralized video stacks use HLS/MP4)

### 5.4 Turning load time into tasks

To absorb the inherent first-load latency of decentralized networks, leverage UX:

- Interactive ads (tap to earn tokens)
- AI annotation tasks (tagging, category verification)
- Prediction-market mini-games (predict the next video's traction)

---

## 6. ID & Authentication (Walletless)

### 6.1 Design philosophy

Hide seed phrases and private keys completely. This is the **industry-standard** direction as of 2025-2026; MORM differentiates by **integrating it with the biometric ban mechanism**.

### 6.2 Stack

- **Passkeys (FIDO2)**: FaceID / TouchID / Windows Hello / console biometrics
- **Secure Element**: per-device key generated in the secure chip
- **MPC-style key sharding**: split between device chip and network shards
- **Social Recovery**: recover via multiple owned devices

### 6.3 Relation to prior art

| Project | Offers | Difference |
|---|---|---|
| Coinbase Smart Wallet | Passkey + ERC-4337 | Integrated with video SNS, linked to biometric ban |
| Privy | Embedded wallet + Passkey | Same |
| Web3Auth | MPC + Social login | Same |

MORM does not invent the ID itself — it provides a **design that integrates ID tightly with the entire app** (posting rights, slashing, recovery).

---

## 7. Content Purity Protocol

### 7.1 V-Hash (deduplication)

- Perceptual hash (pHash) for video features
- Audio fingerprint for sound waveforms
- Vector-DB similarity search

**Prior art**: YouTube Content ID (since 2007), Audible Magic, pHash.org. MORM uses standard tech; the original contribution is the **on-chain priority rule**.

### 7.2 Duplicate handling

- **Timestamp race**: earliest block-recorded entry is canonical
- **Garbage Collection**: network-wide purge for duplicate Cells
- **Upload rejection**: already-registered hashes blocked at gateway

### 7.3 Generation ID (C2PA-compliant)

For videos created by MORM's built-in generative AI service, MORM issues a **C2PA Content Credentials**-compliant Generation ID and anchors it on MORM Chain.

| Compatibility | Detail |
|---|---|
| C2PA 2.x | Interoperable with Adobe CAI, Google SynthID, OpenAI Sora |
| ERC-7053 | Bridgeable to Numbers Protocol's video-NFT standard |
| EU AI Act | Transparency obligations met |

This means videos generated outside of MORM can also prove provenance via C2PA manifests, joining the broader provenance ecosystem.

---

## 8. MORM Shop / Trust Protocol

This is MORM's strongest moat.

### 8.1 Proof of Physical Evidence (PoPE)

```
[Sender]                       [Buyer]
   │                             │
   ├─ Record packing video       │
   │  via dedicated camera       │
   │  (with block-hash watermark)│
   ├─ Anchor video hash on-chain │
   ├─ Ship                       │
   │                             │
   │                             ├─ Receive
   │                             ├─ Record unboxing video
   │                             │  via dedicated camera
   │                             │  (with block-hash watermark)
   │                             └─ Anchor video hash on-chain
   ↓                             ↓
   ┌──────────────────────────────┐
   │ AI / Validator integrity check │
   │ ・Motion analysis              │
   │ ・Content matching             │
   │ ・Timestamp / hash consistency │
   └──────────────────────────────┘
            ↓                ↓
      [Match] release       [Mismatch] auto-refund + Node-Lock
```

### 8.2 Anti-tamper measures

- Only the dedicated MORM camera is accepted
- The latest block hash is burned into video frames at capture time
- Motion analysis detects unnatural cuts, loops, compositing
- Camera API authenticates via Secure Element; AI-generated videos are rejected

### 8.3 Smart escrow

- 99% of payment locked in smart contract
- Both videos match → release to sender
- Mismatch or dispute filed → community arbitration or AI judgement
- Confirmed fraud → instant refund to buyer

### 8.4 Node-Lock & Slash + biometric permanent ban

Upon confirmed fraud:

1. Freeze the offending node
2. Confiscate stake and accumulated rewards (used for victim restitution + redistribution)
3. **Permanently blacklist device ID and biometric ID**
4. **Bar the user from MORM on every device they own, forever**

#### Legal design (important)

For GDPR / APPI / CCPA alignment:

- Biometric templates are **stored as hashes only** (raw data not retained)
- Consent tiered (minor violations do not trigger biometric ban)
- Data minimization principle followed
- The tension between "right to be forgotten" and "Sybil-resistant retention" absorbed via tiered sanctions

---

## 9. Tokenomics

### 9.1 Base currency: MORM Token

> ⚠️ Numbers are draft.

| Item | Allocation |
|---|---|
| Total supply | 10B MORM (tentative) |
| Node Reward Pool | 50% (linear release over 10 years) |
| Community / Airdrop | 15% |
| Ecosystem Fund | 15% |
| Core Contributors | 10% (4-yr vesting + 1-yr cliff, distributed via Bounty Contract) |
| Initial Backers | 5% |
| Treasury | 5% |

### 9.2 Transparent 1% fee model

- Fixed in immutable smart contract (no admin key)
- 99% allocated to:
  - Escrow (Shop's 99% lock)
  - Viewer relay rewards
  - Node provider rewards
  - Creator rewards

### 9.3 Multi-resource reward weights

| Resource | Metric | Weight |
|---|---|---|
| GPU Power | Encoding, AI analysis, frame generation, verification | **Highest** |
| Bandwidth | P2P delivery volume | **High** |
| SSD Storage | MORM Cells held × duration | **Medium** |
| Active Time | Node uptime and stability | **Low** |

### 9.4 Token flywheel

```
[Viewer]
   ↓ Just having the device on earns relay rewards
[MORM Token earned]
   ↓ Stake to gain posting rights
[Becomes Creator]
   ↓ Original videos earn additional rewards
[Viewer count grows]
   ↓ Network attractiveness up
[NodePower demand grows]
   ↓ Incentives for node operators expand
[Node count grows]
   ↓ Delivery quality and decentralization improve
[Better viewing experience]
   ↓ More viewers
[Loop reinforces]
```

In parallel:

```
[MORM Shop transaction]
   ↓ 1% fee
[Treasury & Ecosystem Fund]
   ↓ Development, new features, global expansion
[Use cases expand]
   ↓ Transaction volume up
[Loop reinforces]
```

### 9.5 Multi-currency gateway

- Accepts BTC / ETH / SOL and other major crypto
- Internal DEX swaps to MORM Token instantly
- Volatility during escrow absorbed by automatic hedging
- Stablecoin-denominated payment options where needed

---

## 10. Use Cases & Scale Strategy

MORM is not just "the decentralized version of TikTok." As a base protocol, it opens the following domains in sequence.

### 10.1 Phase 1 use cases (core)

| Use case | Existing problem | MORM provides |
|---|---|---|
| Short-video entertainment | Censorship, shadow-bans | Censorship-proof, Generation ID protected |
| C2C secondhand sales | Fraud, manipulated reviews | PoPE → fraud-zero |
| Live commerce | 30% fees, trust issues | 1% fee, delivery evidence |

### 10.2 Phase 2 use cases (expansion)

| Use case | Opportunity |
|---|---|
| **Cross-border creator economy** | Bypass App Store / Google Play 30% tax; receive directly from fans worldwide |
| **AI-Native Creators** | Generation ID protects originality; rights chains for derivatives |
| **Uncensorable journalism** | Protect journalists, whistleblowers, citizen reporters; on-chain proof of recording time |
| **Digital tickets & events** | Unboxing video = entry; resale detection |
| **Educational content** | Creator-led learning platforms; certificates issued via Generation ID |

### 10.3 Phase 3 use cases (platformization)

| Use case | Opportunity |
|---|---|
| **MORM SDK** | Third-party developers build dApps on MORM |
| **MORM Live** | Live streaming on the same 3-second-Cells primitive |
| **MORM Spatial** | VR/AR / volumetric video on the same protocol |
| **MORM B2B** | Corporate training videos, internal comms on private nodes |
| **MORM IoT** | On-chain recording of sensor data and camera feeds |
| **MORM Bridge** | Eventual interoperation with other Web3 ecosystems |

### 10.4 Geographic strategy

| Phase | Focus regions | Reason |
|---|---|---|
| MORM Phase 0 | English-speaking + Japan | Web3 early-adopter density |
| MORM Phase 1 | Southeast Asia (India, Indonesia, Philippines) | Censorship concerns, smartphone penetration, creator energy |
| MORM Phase 2 | Latin America, Africa, South Asia | Highest regulatory risk for centralized SNS |
| Bridge | Greater China, MENA | Compliant variants prepared separately |

Prioritizing emerging markets avoids head-on collision with Chingari and similar competitors, while growing in regions where censorship resistance is most valuable.

---

## 11. Ecosystem Expansion

### 11.1 First-party product family

```
MORM Core (this whitepaper)
   ├── MORM Studio       — Creator-side video editor
   ├── MORM AI Lab       — Generative AI suite (video / audio / image)
   ├── MORM Live         — Live streaming
   ├── MORM Shop         — P2P commerce
   ├── MORM Hardware     — Dedicated cameras and node devices
   └── MORM SDK          — Third-party dApp development kit
```

### 11.2 Anticipated partners

| Category | Anticipated |
|---|---|
| Hardware | Camera OEMs, game console makers, node device vendors |
| AI | Generative AI providers, moderation AI providers |
| Logistics | Shipment tracking API providers |
| Existing Web3 | Bridges for interoperability (MORM Phase 2+) |
| Regulatory | Per-jurisdiction law firms, compliance partners |

### 11.3 Third-party developer opportunities

Through MORM SDK, the following kinds of apps become possible:

- Vertical-drama / short-film platforms
- Fitness coach / mentor video subscriptions
- High-value C2C markets (sneakers, antiques, etc.)
- Decentralized fan clubs
- 3D video distribution inside metaverses

---

## 12. Posting Rights & Anti-Spam (Proof of Contribution)

### 12.1 Status tiers

| Level | Name | Requirement | Permissions |
|---|---|---|---|
| 1 | Viewer | Run device as a node | View, comment, micro-rewards |
| 2 | Creator | Token holdings + NodePower | Up to 3 posts/day, priority transcoding |
| 3 | Publisher | Large holdings + 24h GPU | Unlimited posts, 4K delivery, fee share |
| 4 | Pioneer | Long-term ecosystem contribution | DAO vote weight, early-access to new features |

### 12.2 Posting deposit

- Small MORM stake locked at upload
- If viewing metrics (completion rate, 3-second reach rate, etc.) clear thresholds → deposit returned + reward
- If judged spam → deposit slashed

### 12.3 Proof of Effort

Token-less users can earn 1 daily posting slot by accumulating contribution score from AI annotation and verification tasks. A design choice respecting economic differences in emerging markets.

---

## 13. Governance (No-Entity Design)

### 13.0 Base structure

MORM **has no legal entity** (no Corporation / Foundation / DAO LLC). No central operating team. No CEO. No headquarters. Operations run on three layers:

```
Layer 3: DAO (token holders) ← parameter setting
Layer 2: AI Agents          ← autonomous daily ops
Layer 1: Smart Contracts    ← immutable money flow
```

See [AGENTS.md](AGENTS.md) for details.

### 13.1 Progressive autonomy

- **MORM Phase 0**: Pseudonymous core contributors bootstrap; initial Validators; initial Smart Contract deploy
- **MORM Phase 1**: Post-TGE all admin keys renounced; AI Agents production; DAO voting Live
- **MORM Phase 2**: Full AI Agent catalog operational; founding contributors hold no privilege; full DAO governance
- **MORM Phase 3**: Evolution to second-generation AI Agents; founding contributors are mere participants

### 13.2 Immutable parameters

Cannot be changed even by DAO vote:

- 10B MORM total supply
- 1.0% operator fee
- User-owned data rights
- Walletless ID principle
- PoPE mandatory principle

### 13.3 DAO-vote scope (by Tier)

**Tier 1 (minor, 48h, 3% quorum)**:
- Node-reward weighting coefficients
- Spam threshold fine-tuning
- AI Agent response template updates

**Tier 2 (mid-size, 7d, 10% quorum)**:
- Burn-rate adjustments
- AI Agent body swaps
- New language support

**Tier 3 (major, 14d, 20% quorum)**:
- New Smart Contract deploys
- Add/remove AI Agents
- Add bridges
- Large Treasury spend (>$1M-equivalent)

### 13.4 Emergency response

For situations too urgent for DAO process, **Emergency Multi-sig (5/7 sigs)** can pause. Signers are geographically distributed and DAO-elected. Within 72h, DAO formally ratifies/cancels.

---

## 14. Roadmap

| Phase | Period | Milestones | Key KPIs |
|---|---|---|---|
| **MORM Phase 0** | 0–6 mo | Custom-chain Testnet, PoC, Walletless ID, 5 AI Agents | 100 nodes |
| **MORM Phase 1** | 6–18 mo | TGE, closed beta, AI Agents production, MORM Shop α | 100k nodes, 1M videos/mo |
| **MORM Phase 2** | 18–36 mo | Public launch, all-device support, full AI Agent catalog | 1M nodes, 10M MAU |
| **MORM Phase 3** | 36 mo+ | SDK release, ecosystem expansion, 2nd-gen AI Agents | 10M nodes, 100M MAU |

---

## 15. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Insufficient initial nodes | Strong MORM Phase 0 incentives; core contributors run Validators |
| Regulatory exposure | Per-jurisdiction legal review; phased KYC/AML |
| 51% attack | PoUW makes useful-work cost asymmetric |
| Inappropriate content | Three-layer defense: AI pre-screen + community report + Slash |
| Token-price volatility | Auto-hedging in escrow; stablecoin-denominated options |
| **GDPR / biometric regulation** | **Hash-only template storage, tiered sanctions, explicit consent** |
| Competition (Chingari, etc.) | Emerging-market-first + PoPE/biometric-ban differentiation |
| C2PA non-compatibility risk | Generation ID designed C2PA 2.x compliant |
| App-store reviews | Web/PWA/direct APK distribution combined; crypto-friendly jurisdictions first |

---

## 16. Open Questions

- Benchmark accuracy of motion-analysis AI (false-positive / false-negative rates)
- Final DAG-consensus specification
- Whether to separate governance and reward tokens
- Securities classification per jurisdiction
- Fit for special shipping cases (food, perishables, digital goods)
- Accessibility (visual / hearing impairment considerations)

---

## 17. Why We Can Win (Closing)

MORM is not a project that invents new primitives. Passkey, C2PA, Livepeer, Theta, pHash, QUIC, DAG, ERC-4337 — all of these already exist.

But no one has implemented all of them as **a single integrated stack for video SNS plus P2P commerce**. And no project has placed **PoPE** and **Slash + biometric permanent ban** — two genuine inventions — on top of that integration.

We are not aiming to be the first inventor.
We aim to be **the first integrator**.

The role of firing the first ignition is held by **Founding Contributor: YACHIDA**. After TGE, YACHIDA transitions to a single participant among other core contributors, holding no operational control (cf. Satoshi Nakamoto / Bitcoin model).

The value of integration is proven the moment a user feels it.
The moment the swarm starts moving, it cannot be stopped.

**The Swarm for Every Frame.**

---

## Appendix A: Glossary

- **MORM Cells** — 3-second WebM video segments
- **NodePower** — Tier-1 node (provides GPU, etc.)
- **Edge Node** — Tier-2 node (provides SSD, bandwidth)
- **Light Client** — Tier-3 node (viewer device)
- **MORM Chain** — Custom decentralized blockchain
- **MORM Shop** — P2P commerce module with physical-evidence proofs
- **PoPE (Proof of Physical Evidence)** — Tamper-proof record of packing/unboxing
- **PoUW (Proof of Useful Work)** — Useful video-related computation as consensus base
- **PoC (Proof of Contribution)** — Status tiers for posting rights
- **V-Hash** — Perceptual fingerprint of video
- **Generation ID** — C2PA-compliant originality proof for AI-generated works
- **Node-Lock / Slash** — Freezing, confiscation, and exile sanction for malicious nodes
- **Walletless ID** — Passkey / Secure Element / MPC-based ID

## Appendix B: Major Prior-Art References

| Domain | Major prior art | Link |
|---|---|---|
| Walletless ID | Coinbase Smart Wallet | help.coinbase.com |
| Walletless ID | Privy | privy.io |
| AI provenance | C2PA | c2pa.org |
| AI provenance | Numbers Protocol | numbersprotocol.io |
| Transcoding PoUW | Livepeer | livepeer.org |
| Delivery PoUW | Theta Network | thetatoken.org |
| AI inference PoUW | Bittensor | bittensor.com |
| Dedup | YouTube Content ID | youtube.com |
| Short-video SNS | Chingari | chingari.io |
| Sybil-resistant biometrics | Worldcoin | world.org |
| Sybil-resistant biometrics | Humanity Protocol | humanity.org |
| DAG L1 | IOTA, Hedera, Sui | — |
| QUIC P2P | libp2p | libp2p.io |

---

*This whitepaper is a draft. Final specifications are subject to change. Legal review by qualified counsel in each jurisdiction is required.*
