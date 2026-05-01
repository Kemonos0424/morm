# MORM Tokenomics

**Version**: 0.1 (Draft)
**Date**: 2026-04-25
**Status**: Pre-TGE / Draft

---

> ⚠️ All numbers in this document are draft and may change before the TGE (Token Generation Event). Legal review is mandatory.

---

## 1. Token Basics

| Item | Value |
|---|---|
| Symbol | $MORM |
| Total Supply | 10,000,000,000 (10B) — fixed |
| Decimals | 18 |
| Base Chain | MORM Chain (custom L1, not ERC-20) |
| Bridges | wMORM (MORM Phase 2+: Ethereum / Solana) |
| Type | Utility Token |

Total supply is **permanently fixed**. Cannot be changed even by DAO vote.

---

## 2. Allocation

| Bucket | % | Amount | Vesting |
|---|---|---|---|
| Node Reward Pool | **50%** | 5,000,000,000 | Linear release over 10 years from TGE |
| Community / Airdrop | **15%** | 1,500,000,000 | See §2.2 |
| Ecosystem Fund | **15%** | 1,500,000,000 | 4-yr linear (DAO post-MORM Phase 1) |
| Core Contributors | **10%** | 1,000,000,000 | 1-yr cliff + 3-yr linear |
| Initial Backers | **5%** | 500,000,000 | 1-yr cliff + 2-yr linear |
| Treasury | **5%** | 500,000,000 | DAO-controlled (post-MORM Phase 1) |

### 2.1 Node Reward Pool (50%)

**Purpose**: rewards for the operators who power the network.

**Release**: 10 years from TGE. Emission curve:

| Year | Release Rate | Cumulative |
|---|---|---|
| Year 1 | 12% | 12% |
| Year 2 | 11% | 23% |
| Year 3 | 10% | 33% |
| Year 4 | 9% | 42% |
| Year 5 | 8% | 50% |
| Year 6 | 7% | 57% |
| Year 7 | 7% | 64% |
| Year 8 | 7% | 71% |
| Year 9 | 7% | 78% |
| Year 10 | 7% | 85% |
| Year 11+ | Remaining 15% adaptive | 100% |

**Distribution logic**: auto-allocated by PoUW contribution (transcoding / AI / delivery / verification).

### 2.2 Community / Airdrop (15%)

| Sub-bucket | % of total | Amount | Detail |
|---|---|---|---|
| MORM Initial Airdrop | 5% | 500M | Early Discord members, Testnet participants, SNS engagement |
| Quest System | 5% | 500M | 3-year recurring community-task rewards |
| Creator Bonus | 5% | 500M | First 100k Creators reaching threshold |

### 2.3 Ecosystem Fund (15%)

| Sub-bucket | % of total | Amount | Detail |
|---|---|---|---|
| Grants | 6% | 600M | Third-party developer grants |
| Partnerships | 4% | 400M | Strategic partner integrations |
| Hackathons & Events | 2% | 200M | Community events |
| Education & Marketing | 3% | 300M | Educational content, global expansion |

**MORM Phase 1+**: allocation can be re-balanced via DAO vote.

### 2.4 Core Contributors (10%)

- 1-year cliff (0% unlock for the first 12 months from TGE)
- After cliff: monthly linear release over 3 years
- Total vesting: 4 years
- Covers pseudonymous/anonymous core contributors (**not employees** — no employment contracts)
- Distribution: via Bounty Contract (per individual contribution)
- Because MORM has no legal entity, each person bears tax responsibility as an independent contractor / individual

### 2.5 Initial Backers (5%)

- 1-year cliff + 2-year linear (3 years total)
- **No public sale** at this stage
- Strategic investors only (those contributing to protocol operations)
- Offered only to qualified investors per applicable securities law

### 2.6 Treasury (5%)

- Transferred to DAO multi-sig at TGE
- MORM Phase 1+: managed via DAO vote
- Used for emergency funds, legal, market interventions

---

## 3. Token Utility

| Use | Detail |
|---|---|
| **Posting Deposit** | Lock MORM when uploading videos. Slashed if judged spam |
| **Node Staking** | Required for node operation. Minimum stake by Tier |
| **Governance** | DAO vote weight (1 MORM = 1 vote, capped) |
| **Shop Settlement** | Escrow and final settlement currency |
| **Tier Upgrade** | Holdings required for Creator / Publisher / Pioneer |
| **AI Lab Credits** | Pay for video generation in MORM AI Lab |
| **Tx Fees** | On-chain transaction fees (very small) |

### 3.1 Tier Minimum Stake (tentative)

| Tier | Min Stake | Other |
|---|---|---|
| Viewer | 0 MORM | Run device as a node |
| Creator | 100 MORM | + 50h/month uptime |
| Publisher | 10,000 MORM | + 24h GPU contribution |
| Pioneer | 100,000 MORM | + 1+ year of continuous contribution |

---

## 4. Economic Sinks (deflationary)

Mechanisms that maintain network health:

| Sink | Burn Rate | Estimated Annual Volume |
|---|---|---|
| Posting deposit slashing (spam) | 50% burn / 50% to victim | 0.3-0.5% of circulating |
| Fraud Slash | 50% burn / 50% network redistribution | 0.1-0.2% |
| AI Lab generation fees | 50% burn / 50% to GPU provider | 0.5-1.0% |
| Shop fraud penalty | 50% burn / 50% to victim | 0.1-0.3% |
| **Total annual burn (mature phase)** | — | **2-3%** |

By balancing emission and burn, net inflation converges near 0% in the mature phase.

---

## 5. Network Growth Targets

| Phase | Circulating Supply | Staking Ratio | Estimated Node APY |
|---|---|---|---|
| MORM Phase 0 (0–6mo) | 500M | 30% | 18-25% |
| MORM Phase 1 (6–18mo) | 1.5B | 40% | 12-18% |
| MORM Phase 2 (18–36mo) | 4B | 50% | 8-12% |
| MORM Phase 3 (36mo+) | 7B | 55% | 5-8% |

APY is a function of new emission, burn, and utilization. Naturally declines as the network matures.

---

## 6. Multi-Currency Gateway

- **Accepted currencies**: BTC / ETH / SOL / USDC / USDT / major fiat-pegged stablecoins
- **Auto-swap**: instant conversion to MORM via internal DEX
- **Escrow value pegging**: USD-denominated pin option (auto-hedged)
- **Use cases**: Shop settlement, AI Lab credits, node fees

---

## 7. Bridge Strategy (MORM Phase 2+)

| Bridge | Format | Release |
|---|---|---|
| Ethereum | wMORM (ERC-20) | MORM Phase 2 |
| Solana | wMORM (SPL) | MORM Phase 2 |
| Bitcoin Lightning | Atomic swap | Phase MORM Phase 3 |
| Other L2s | TBD | DAO vote |

**Model**: lock-and-mint. Lock MORM on MORM Chain, mint equivalent wMORM. Reverse: burn + unlock.

**Security**: multi-stakeholder multi-sig + DAO oversight. Conservative design given the history of bridge hacks.

---

## 8. Anti-Whale Mechanisms

| Limit | Detail |
|---|---|
| Max stake (single node) | Up to 0.5% of total supply |
| Vote-weight cap | Single address capped at 1% of total voting power |
| Single Shop transaction cap | $1M equivalent (no KYC) / unlimited (KYC) |
| Quest reward cap | 0.1% of total per address |

---

## 9. Legal Design

### 9.1 Regulatory Stance

- MORM is designed as a **Utility Token**
- No investment solicitation
- Securities classification per jurisdiction is the user's responsibility
- **US**: out of scope for now (pending securities-law evaluation)
- **EU**: aiming for MiCA compliance
- **Japan**: anticipated to be accessed via licensed exchange operators (MORM Phase 2+)

### 9.2 KYC/AML

| Tx size | Requirement |
|---|---|
| <$1,000 equivalent | No KYC |
| $1,000–$10,000 | Light KYC |
| >$10,000 | Full KYC + AML screening |

Phased rollout post-MORM Phase 1.

### 9.3 Tax

- User responsibility
- Subject to local crypto-asset tax rules
- Tax-form issuance considered MORM Phase 2+

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Token-price volatility | Auto-hedging in escrow, stablecoin payment options |
| Early sell pressure | Long vesting for team/backers, DAO migration |
| Excessive concentration | Anti-whale limits, vote caps |
| Bridge hacks | Conservative phased rollout MORM Phase 2+, multi-sig |
| Regulatory shifts | Phased KYC, regional opt-out |
| Liquidity shortage | Ecosystem Fund DEX-LP injection |

---

## 11. Governance Parameters

### 11.1 Immutable (cannot be changed by DAO)

- Total supply (10B)
- Operator fee rate (1.0%)
- Tier minimum-stake floor (can only increase, never decrease)

### 11.2 DAO-votable

- Node reward weighting coefficients
- Burn rate
- Staking-reward rate adjustments
- Ecosystem Fund allocation
- New-feature priority
- Various thresholds (spam, Slash triggers, etc.)

---

## 12. Use-Case Economic Flows

### 12.1 General Viewer

```
Turn device on
   ↓
Run as node (provide a few hundred MB of bandwidth)
   ↓
Earn 0.05–0.5 MORM/day (tentative)
   ↓
1.5–15 MORM/month
```

### 12.2 Creator

```
Stake 100 MORM + run node
   ↓
Upload video (10 MORM deposit)
   ↓
Reward by view count + completion rate
   ↓
Average video: 20–200 MORM
   ↓
Viral video: thousands–tens of thousands MORM
```

### 12.3 NodePower (GPU operator)

```
1 × RTX 4090 running 24h
   ↓
Transcoding + AI analysis
   ↓
50–200 MORM/day (tentative)
   ↓
1,500–6,000 MORM/month
   ↓
Net positive after electricity costs
```

### 12.4 Shop User

```
Buy $100 item
   ↓
$1 (1%) operator fee
   ↓
$99 locked in escrow
   ↓
Verify shipping/unboxing evidence
   ↓
$99 released to seller
```

---

## 13. TGE & Launch Schedule

| Event | Timing | Detail |
|---|---|---|
| Whitelist | TBD | Discord / Testnet participants |
| MORM Initial Airdrop Snapshot | TBD | 30 days before TGE |
| TGE | TBD | DEX listing, MORM Initial Airdrop distribution |
| Public Trading | TBD | TGE day |
| Vesting Start | TGE | Team/Backers/Ecosystem |
| First Node Rewards | TGE + 1 day | PoUW-based distribution begins |

Specific dates finalized as MORM Phase 0 progresses.

---

## 14. Comparison with Existing Projects

| Project | Total Supply | Node Allocation | Fees | Burn |
|---|---|---|---|---|
| MORM | 10B | 50% | 1% fixed | 2-3% / yr |
| Livepeer | ~29M | ~80% | Variable | Yes |
| Theta | 1B | Ecosystem + node | Variable | Yes |
| Filecoin | 2B | 55% | Variable | Yes |
| Chingari (GARI) | 1B | Community + rewards | Unclear | Unclear |

---

## 15. Disclaimer

- This is a draft prepared in advance
- Material changes may occur before TGE
- Crypto assets carry price-volatility risk
- Subject to regulatory restriction in some jurisdictions
- Participation is at your own risk; this is not investment advice

---

*Final tokenomics will be locked via smart contract before TGE. The 1% fee, total-supply cap, and core utility design are immutable thereafter.*
