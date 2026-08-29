// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {WMORM} from "./WMORM.sol";

/// @title MORMExportBridge — M-of-N federated mint/burn bridge for wMORM.
/// @notice Exports L1 MORM onto this EVM chain as a tradable ERC-20 (wMORM),
///         so a wMORM/USDC Uniswap pool yields a real MORM/USD chart.
///
///  Forward (L1 -> EVM):  a user does BRIDGE_BURN on the MORM L1. A quorum of
///  registered signers each attest to that burn (recipient, amount, mormBurnId)
///  and the bridge MINTS wMORM to the recipient here. One-shot per mormBurnId.
///
///  Reverse (EVM -> L1):  a user calls exit(amount, mormAddress). The bridge
///  BURNS their wMORM and emits Exit; the relayer submits BRIDGE_MINT on the L1
///  to credit their MORM back.
///
///  Security model (hardens the single-relayer PoC — MORMBridge.sol):
///   - M-of-N signatures over a digest bound to (this, chainid, purpose) so a
///     signature can't be replayed on another bridge/chain (see MORMBridgeMS).
///   - Signers submitted strictly ascending => dedup; low-s enforced => no
///     signature malleability; one-shot mormBurnId => no double-mint.
///   - Circuit breaker: mint is rate-limited per rolling window AND a guardian
///     can pause() — so even a signer-quorum compromise cannot drain unbounded
///     wMORM before humans intervene.
///   - CEI: state (minted flag, window accrual) is written before the external
///     token.mint call.
///
///  Testnet-first: signer set is fixed at deploy. Mainnet adds signer rotation
///  behind a timelock + external audit (see repo notes).
contract MORMExportBridge {
    WMORM public immutable token;

    address[] public signers;
    uint256 public immutable threshold;
    mapping(address => bool) public isSigner;

    mapping(bytes32 => bool) public minted;   // per-L1-burn one-shot
    uint256 public exitNonce;

    // --- circuit breaker ---
    address public guardian;                  // can pause + rotate guardian
    bool public paused;
    uint256 public immutable windowLen;       // seconds (mint velocity window)
    uint256 public immutable maxMintPerWindow;// velocity cap per window
    uint256 public immutable maxSupply;       // absolute cap on outstanding wMORM (magnitude)
    uint256 public immutable minExit;         // dust floor for exit() (0 = disabled)
    uint256 public windowStart;
    uint256 public mintedInWindow;

    // secp256k1 order / 2 — reject high-s (EIP-2) signatures
    uint256 internal constant HALF_N =
        0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0;

    event MintedFromBurn(address indexed recipient, uint256 amount, bytes32 indexed mormBurnId);
    event Exit(uint256 indexed exitNonce, address indexed from, bytes20 indexed mormAddress, uint256 amount);
    event Paused(bool paused);
    event GuardianChanged(address indexed newGuardian);

    error ZeroAddress();
    error ZeroAmount();
    error BadSignerCount();
    error DuplicateOrUnknownSigner();
    error BadSignature();
    error NotEnoughSignatures();
    error AlreadyMinted();
    error IsPaused();
    error NotGuardian();
    error RateLimited();
    error CapExceeded();
    error BelowMinExit();

    modifier notPaused() {
        if (paused) revert IsPaused();
        _;
    }

    constructor(
        address _token,
        address[] memory _signers,
        uint256 _threshold,
        address _guardian,
        uint256 _windowLen,
        uint256 _maxMintPerWindow,
        uint256 _maxSupply,
        uint256 _minExit
    ) {
        if (_token == address(0) || _guardian == address(0)) revert ZeroAddress();
        if (_signers.length == 0 || _threshold == 0 || _threshold > _signers.length)
            revert BadSignerCount();
        if (_windowLen == 0 || _maxMintPerWindow == 0 || _maxSupply == 0) revert ZeroAmount();
        token = WMORM(_token);
        threshold = _threshold;
        for (uint256 i; i < _signers.length; ++i) {
            if (_signers[i] == address(0)) revert ZeroAddress();
            if (isSigner[_signers[i]]) revert DuplicateOrUnknownSigner();
            isSigner[_signers[i]] = true;
            signers.push(_signers[i]);
        }
        guardian = _guardian;
        windowLen = _windowLen;
        maxMintPerWindow = _maxMintPerWindow;
        maxSupply = _maxSupply;
        minExit = _minExit;
        windowStart = block.timestamp;
    }

    /// @notice Mint wMORM for a confirmed L1 BRIDGE_BURN. Requires `threshold`
    ///         distinct signer signatures over (recipient, amount, mormBurnId).
    function mintFromBurn(
        address recipient,
        uint256 amount,
        bytes32 mormBurnId,
        bytes[] calldata signatures
    ) external notPaused {
        if (recipient == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (minted[mormBurnId]) revert AlreadyMinted();
        if (signatures.length < threshold) revert NotEnoughSignatures();

        bytes32 ethDigest = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n32",
            mintDigest(recipient, amount, mormBurnId)));

        address last = address(0);
        uint256 valid;
        for (uint256 i; i < signatures.length; ++i) {
            address signer = _recover(ethDigest, signatures[i]);
            if (signer == address(0) || !isSigner[signer]) revert BadSignature();
            if (signer <= last) revert DuplicateOrUnknownSigner();  // strictly ascending
            last = signer;
            unchecked { ++valid; }
        }
        if (valid < threshold) revert NotEnoughSignatures();

        // magnitude cap: outstanding wMORM can never exceed maxSupply, so a
        // signer-quorum compromise is bounded absolutely (not just per window).
        if (token.totalSupply() + amount > maxSupply) revert CapExceeded();

        // effects before interaction (CEI)
        minted[mormBurnId] = true;
        _accrue(amount);
        emit MintedFromBurn(recipient, amount, mormBurnId);
        token.mint(recipient, amount);
    }

    /// @notice Burn wMORM to move value back to the L1. Relayer observes Exit
    ///         and submits BRIDGE_MINT (token=MORM) crediting `mormAddress`.
    function exit(uint256 amount, bytes20 mormAddress) external notPaused {
        if (amount == 0) revert ZeroAmount();
        if (amount < minExit) revert BelowMinExit();
        if (mormAddress == bytes20(0)) revert ZeroAddress();
        unchecked { ++exitNonce; }
        token.burn(msg.sender, amount);   // effect first — reverts if caller lacks balance
        emit Exit(exitNonce, msg.sender, mormAddress, amount);
    }

    // --- rate limiter (rolling window circuit breaker) ---
    function _accrue(uint256 amount) internal {
        if (block.timestamp >= windowStart + windowLen) {
            windowStart = block.timestamp;
            mintedInWindow = 0;
        }
        uint256 next = mintedInWindow + amount;
        if (next > maxMintPerWindow) revert RateLimited();
        mintedInWindow = next;
    }

    // --- guardian controls ---
    function setPaused(bool p) external {
        if (msg.sender != guardian) revert NotGuardian();
        paused = p;
        emit Paused(p);
    }

    function setGuardian(address g) external {
        if (msg.sender != guardian) revert NotGuardian();
        if (g == address(0)) revert ZeroAddress();
        guardian = g;
        emit GuardianChanged(g);
    }

    // --- views / helpers ---
    function mintDigest(address recipient, uint256 amount, bytes32 mormBurnId)
        public view returns (bytes32)
    {
        return keccak256(abi.encode(
            address(this), block.chainid, "MORMExportBridge:mint",
            recipient, amount, mormBurnId));
    }

    function signerCount() external view returns (uint256) { return signers.length; }

    function _recover(bytes32 hash, bytes memory sig) internal pure returns (address) {
        if (sig.length != 65) return address(0);
        bytes32 r; bytes32 s; uint8 v;
        assembly {
            r := mload(add(sig, 32))
            s := mload(add(sig, 64))
            v := byte(0, mload(add(sig, 96)))
        }
        if (uint256(s) > HALF_N) return address(0);   // reject malleable high-s
        if (v < 27) v += 27;
        if (v != 27 && v != 28) return address(0);
        return ecrecover(hash, v, r, s);
    }
}
