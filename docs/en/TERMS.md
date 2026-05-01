# MORM Terms of Service

**Version**: 0.1 (Draft)
**Last Updated**: 2026-04-25
**Effective Date**: TBD

---

> ⚠️ **Important Notice**
> These Terms are a draft based on the project's technical design and operating philosophy. Before public launch, mandatory legal review by qualified counsel in each applicable jurisdiction is required. This draft does not constitute legal advice.

---

## Article 1 (Purpose & Scope)

1. These Terms apply to all users, node operators, creators, buyers, and sellers (collectively, "Users") who use MORM (the "Service").
2. The Service operates on a decentralized network and **has no legal entity** (no Corporation, Foundation, or DAO LLC). All operations run autonomously via Smart Contracts, AI Agents, and the DAO. These Terms set out the operating philosophy and rules of participation. See [AGENTS.md](AGENTS.md) for details.
3. By launching or using the Service, the User is deemed to have agreed to these Terms.

---

## Article 2 (Definitions)

| Term | Definition |
|---|---|
| MORM Chain | The proprietary decentralized blockchain underlying the Service |
| MORM Cells | Encrypted video segments split into 3-second units |
| Node | Any device contributing resources to the Service |
| NodePower | Higher-tier nodes providing high-end resources such as GPU |
| MORM Token | The base crypto asset within the Service |
| MORM Shop | The P2P commerce feature using the physical-evidence protocol |
| Generation ID | Originality proof ID for AI-generated works |
| Node-Lock | Freezing/exile sanction triggered upon detection of fraud |

---

## Article 3 (Accounts & Authentication)

1. The Service generates accounts using device biometrics and Passkeys, without seed phrases or private keys.
2. Users are responsible for managing their authentication devices. The Service bears no liability for damages caused by lost or stolen devices.
3. Account recovery is performed via social recovery using multiple registered owned devices. If all owned devices are lost, account recovery may be impossible.
4. A single User may not create duplicate accounts. Duplicate registrations using the same biometrics will be automatically rejected.

---

## Article 4 (Age & Regional Restrictions)

1. Use of the Service requires Users to be **at least 13 years old** (some jurisdictions impose higher age thresholds).
2. Users **under 18 years old** may not engage in MORM Shop transactions, staking, token purchases, or paid-content uploads.
3. Where local law restricts the use of the Service, use from such regions is prohibited. The Service does not intend to provide services to legally restricted jurisdictions.

---

## Article 5 (User Content)

### 5.1 Posting Rights

Users gain posting privileges according to their Proof of Contribution level (see Whitepaper).

### 5.2 Prohibited Content

The following content is prohibited:

1. Any child sexual exploitation material (CSAM)
2. Content inciting violence or threats against real persons
3. Sale or facilitation of illegal drugs
4. Human trafficking, weapons trafficking, terrorism support
5. Content infringing third-party copyright, trademark, image rights, or privacy
6. Non-consensual deepfakes and synthetic sexual content
7. Content for malware, phishing, or fraud
8. Content promoting animal cruelty or self-harm/suicide
9. Content violating any applicable national law

### 5.3 User Warranties

Users represent and warrant the following for any uploaded content:
- They hold legitimate rights to upload the content
- The content does not infringe any third-party rights
- The content has not been tampered with or fabricated

### 5.4 Sanctions for Violations

Violations are addressed in escalating steps via AI pre-screening, community reports, and Validator review:

- Garbage Collection of the offending content
- Forfeiture of the upload deposit
- Node-Lock of the uploader
- Slashing of stake and accumulated rewards
- Permanent ban at the device-ID and biometric level

### 5.5 Content License

Users retain copyright in their uploaded content. However, to the extent necessary to provide the Service (storage on distributed nodes, delivery, transcoding, thumbnail generation, search indexing, etc.), Users grant the Service and its nodes a worldwide, non-exclusive, royalty-free, sublicensable license to use the content.

---

## Article 6 (Node Operation)

### 6.1 Conditions

1. Node operators must participate using hardware and network connectivity to which they hold legitimate rights.
2. Unauthorized use of third-party resources is prohibited.
3. If permission from an employer or other organization is required for the resources contributed, such permission must be obtained in advance.

### 6.2 Node Responsibilities

1. Nodes are obligated to maintain the integrity of the data they store.
2. If the uptime of stored data falls below a threshold, partial reward reduction or stake slashing may occur.
3. Nodes are deemed to consent to the automatic deletion of any illegal content as soon as it is identified.

### 6.3 Rewards

1. Node rewards are auto-distributed by smart contracts.
2. The Service does not compensate for missed rewards due to network failures, internet outages, or device malfunctions.

---

## Article 7 (MORM Shop)

### 7.1 Parties to a Transaction

1. Transactions on MORM Shop occur peer-to-peer (P2P) between sellers and buyers. The Service is not a party to the transaction; it provides only the trust infrastructure and escrow.
2. Primary responsibility for product quality, fitness, and legality lies with the seller.

### 7.2 Proof of Physical Evidence

1. Sellers consent to recording a packing video using the dedicated camera prior to shipment.
2. Buyers consent to recording an unboxing video using the dedicated camera upon receipt.
3. Videos captured by means other than the dedicated camera will not be accepted as evidence.
4. The latest block hash will be embedded in the video as a watermark at the moment of capture.

### 7.3 Escrow

1. 1% of the purchase amount is automatically collected as the operator fee, and the remaining 99% is escrowed in a smart contract.
2. Once both video proofs match and the dispute window expires, the escrow is released to the seller.
3. In the event of mismatch, AI analysis or Validator review determines refund or release.

### 7.4 Dispute Resolution

1. Disputes are first handled by the Service's arbitration protocol.
2. Users may request community-Validator review if they object to AI judgements.
3. Disputes that cannot be resolved by the arbitration protocol are governed by the laws of each User's jurisdiction.

### 7.5 Prohibited Trades

The following may not be traded:
- Illegal goods (drugs, weapons, counterfeits, stolen items)
- Goods restricted by law
- Personal data, confidential information
- Goods violating any country's import/export controls

---

## Article 8 (Crypto Assets & MORM Token)

1. MORM Token and other crypto assets exchanged on the Service are managed in compliance with the laws of each jurisdiction.
2. Crypto assets fluctuate in value and entail loss risk. Users participate at their own risk.
3. The Service does not offer MORM Token as an "investment product." MORM Token is a utility token for infrastructure operation and incentive design.
4. Users are responsible for verifying the applicability of securities and financial regulations in their jurisdictions.

---

## Article 9 (Privacy & Data)

1. The Service stores User content and metadata across distributed nodes. Details are governed by a separate Privacy Policy.
2. By uploading, Users consent to the storage and replication of their content across the distributed network. Once content has propagated, complete deletion may be technically infeasible.
3. The Service has no obligation to permanently delete content, except for the following:
   - Statutory deletion obligations (CSAM, DMCA-equivalent notices, etc.)
   - Automatic removal of duplicates by V-Hash
   - Automatic removal by Garbage Collection
   - Removal due to violations of these Terms

---

## Article 10 (Intellectual Property)

1. The name "MORM," the logos, and related taglines (including "The Swarm for Every Frame") belong to the Service.
2. Copyright in user-uploaded content remains with the uploader (see Section 5.5).
3. For AI-generated works with a Generation ID, the user who first records the ID on-chain is recorded as the original poster.
4. Content judged to be a copy or unauthorized clip will be rejected; repeated offenses trigger Node-Lock.

---

## Article 11 (Prohibited Conduct)

Users may not:

1. Attack, gain unauthorized access to, or maliciously reverse-engineer the Service's network or smart contracts
2. Use automation tools for fraudulent engagement (fake likes, fake views, bot uploads)
3. Impersonate others
4. Harass, harm, harbor hate speech against, or coordinate defamation toward other users
5. Defraud others using the deposit or escrow mechanisms
6. Attempt 51% attacks or otherwise interfere with consensus
7. Spoof nodes to obtain rewards fraudulently
8. Take any action undermining the transparency or fairness of the Service

---

## Article 12 (Disclaimers)

1. The Service is provided "AS IS." No warranties of merchantability, fitness for a particular purpose, or non-infringement, whether express or implied, are made.
2. By the nature of decentralized networks, the Service bears no liability for:
   - Temporary unavailability due to network or node outages
   - Losses caused by crypto-asset price movements
   - Damages caused by Users' own device or authentication mismanagement
   - Disputes arising between Users and third-party node operators
3. The Service's liability is limited to the maximum extent permitted by applicable law.

---

## Article 13 (Changes to Terms)

1. These Terms may be amended via the governance process (DAO vote or core team decision).
2. Material changes will be announced in advance through in-Service notifications and the official website.
3. The "Immutable Parameters" defined in Section 9.2 of the Whitepaper (e.g., the 1% operator fee) cannot be changed even by amendments to these Terms.

---

## Article 14 (Governing Law & Dispute Resolution)

1. The interpretation and application of these Terms are governed by the law of each User's jurisdiction (where mandatory consumer-protection laws apply).
2. The Service itself is decentralized and does not impose a specific forum. Because there is no legal entity behind the Service, there is no traditional "operator" to sue. Disputes will first attempt resolution via the Service's DAO arbitration protocol and AI-Agent initial review.

---

## Article 15 (Contact)

- Official site: TBD
- Official X (Twitter): TBD
- Official Discord: TBD
- Legal contact: TBD

---

## Supplementary Provisions

These Terms become effective on TBD, 2026.

---

*These Terms were drafted with AI assistance. Mandatory review by qualified counsel in each jurisdiction is required prior to actual deployment. Particular attention should be given to:*
- *Crypto-asset regulation (securities classification, financial-instrument applicability)*
- *Consumer-protection law (especially for goods and escrow)*
- *Data-protection law (GDPR, CCPA, APPI, etc.)*
- *Youth protection*
- *Content moderation duties (DSA, KOSA, etc.)*
