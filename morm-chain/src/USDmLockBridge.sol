// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title USDmLockBridge — M-of-N lock/unlock (escrow) bridge for USDm ↔ MORM L1.
/// @notice USDm already exists on this chain (USDC-backed), so unlike wMORM this
///         bridge does NOT mint — it ESCROWS the token and releases it on a
///         quorum-signed L1 burn. Mirrors MORMExportBridge's security so the
///         relayer can reuse the same signing (only the digest purpose differs).
///
///  Base → L1:  user calls lock(amount, mormAddress). USDm is pulled into escrow
///  and a Locked event is emitted; the relayer credits account_tokens[USDm] to
///  mormAddress on the L1 (BRIDGE_MINT token=USDm — a pure mirror, no L1 supply
///  is created).
///
///  L1 → Base:  user does BRIDGE_BURN(token=USDm) on the L1. A quorum of signers
///  attest to (recipient, amount, l1BurnId) and unlock() releases escrowed USDm.
///  One-shot per l1BurnId. Can only release what is escrowed ⇒ a signer-quorum
///  compromise is bounded by TVL, plus a per-window velocity cap and guardian
///  pause. CEI: state written before the token transfer.
///
///  ★ Holds real value (USDm = USDC): audit + confirm compliance before mainnet
///  use with significant funds. Signer set fixed at deploy (mainnet: add rotation
///  behind a timelock). Dependency-free to match this repo's style.
interface IERC20 {
    function transfer(address to, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
    function balanceOf(address) external view returns (uint256);
}

contract USDmLockBridge {
    IERC20 public immutable token;                 // USDm

    address[] public signers;
    uint256 public immutable threshold;
    mapping(address => bool) public isSigner;

    mapping(bytes32 => bool) public unlockedBurn;  // per-L1-burn one-shot
    uint256 public lockNonce;

    // --- circuit breaker ---
    address public guardian;
    bool public paused;
    uint256 public immutable windowLen;            // seconds (unlock velocity window)
    uint256 public immutable maxUnlockPerWindow;   // velocity cap per window (USDm base units)
    uint256 public immutable minLock;              // dust floor for lock/unlock (0 = disabled)
    uint256 public windowStart;
    uint256 public unlockedInWindow;

    uint256 internal constant HALF_N =
        0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0;

    event Locked(uint256 indexed lockNonce, address indexed from, bytes20 indexed mormAddress, uint256 amount);
    event Unlocked(address indexed recipient, uint256 amount, bytes32 indexed l1BurnId);
    event Paused(bool paused);
    event GuardianChanged(address indexed newGuardian);

    error ZeroAddress();
    error ZeroAmount();
    error BadSignerCount();
    error DuplicateOrUnknownSigner();
    error BadSignature();
    error NotEnoughSignatures();
    error AlreadyUnlocked();
    error IsPaused();
    error NotGuardian();
    error RateLimited();
    error BelowMinLock();
    error TransferFailed();

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
        uint256 _maxUnlockPerWindow,
        uint256 _minLock
    ) {
        if (_token == address(0) || _guardian == address(0)) revert ZeroAddress();
        if (_signers.length == 0 || _threshold == 0 || _threshold > _signers.length)
            revert BadSignerCount();
        if (_windowLen == 0 || _maxUnlockPerWindow == 0) revert ZeroAmount();
        token = IERC20(_token);
        threshold = _threshold;
        for (uint256 i; i < _signers.length; ++i) {
            if (_signers[i] == address(0)) revert ZeroAddress();
            if (isSigner[_signers[i]]) revert DuplicateOrUnknownSigner();
            isSigner[_signers[i]] = true;
            signers.push(_signers[i]);
        }
        guardian = _guardian;
        windowLen = _windowLen;
        maxUnlockPerWindow = _maxUnlockPerWindow;
        minLock = _minLock;
        windowStart = block.timestamp;
    }

    /// @notice Escrow USDm and signal the L1 to credit `mormAddress`.
    function lock(uint256 amount, bytes20 mormAddress) external notPaused {
        if (amount == 0) revert ZeroAmount();
        if (amount < minLock) revert BelowMinLock();
        if (mormAddress == bytes20(0)) revert ZeroAddress();
        uint256 pre = token.balanceOf(address(this));
        if (!token.transferFrom(msg.sender, address(this), amount)) revert TransferFailed();
        uint256 got = token.balanceOf(address(this)) - pre;   // actual escrowed
        unchecked { ++lockNonce; }
        emit Locked(lockNonce, msg.sender, mormAddress, got);
    }

    /// @notice Release escrowed USDm for a confirmed L1 BRIDGE_BURN(token=USDm).
    ///         Requires `threshold` distinct signer sigs over (recipient, amount, l1BurnId).
    function unlock(
        address recipient,
        uint256 amount,
        bytes32 l1BurnId,
        bytes[] calldata signatures
    ) external notPaused {
        if (recipient == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (unlockedBurn[l1BurnId]) revert AlreadyUnlocked();
        if (signatures.length < threshold) revert NotEnoughSignatures();

        bytes32 ethDigest = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n32",
            unlockDigest(recipient, amount, l1BurnId)));

        address last = address(0);
        uint256 valid;
        for (uint256 i; i < signatures.length; ++i) {
            address signer = _recover(ethDigest, signatures[i]);
            if (signer == address(0) || !isSigner[signer]) revert BadSignature();
            if (signer <= last) revert DuplicateOrUnknownSigner();   // strictly ascending
            last = signer;
            unchecked { ++valid; }
        }
        if (valid < threshold) revert NotEnoughSignatures();

        // effects before interaction (CEI)
        unlockedBurn[l1BurnId] = true;
        _accrue(amount);
        emit Unlocked(recipient, amount, l1BurnId);
        if (!token.transfer(recipient, amount)) revert TransferFailed();
    }

    // --- rate limiter (rolling window) ---
    function _accrue(uint256 amount) internal {
        if (block.timestamp >= windowStart + windowLen) {
            windowStart = block.timestamp;
            unlockedInWindow = 0;
        }
        uint256 next = unlockedInWindow + amount;
        if (next > maxUnlockPerWindow) revert RateLimited();
        unlockedInWindow = next;
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
    function unlockDigest(address recipient, uint256 amount, bytes32 l1BurnId)
        public view returns (bytes32)
    {
        return keccak256(abi.encode(
            address(this), block.chainid, "USDmLockBridge:unlock",
            recipient, amount, l1BurnId));
    }

    function signerCount() external view returns (uint256) { return signers.length; }
    function escrowed() external view returns (uint256) { return token.balanceOf(address(this)); }

    function _recover(bytes32 hash, bytes memory sig) internal pure returns (address) {
        if (sig.length != 65) return address(0);
        bytes32 r; bytes32 s; uint8 v;
        assembly {
            r := mload(add(sig, 32))
            s := mload(add(sig, 64))
            v := byte(0, mload(add(sig, 96)))
        }
        if (uint256(s) > HALF_N) return address(0);
        if (v < 27) v += 27;
        if (v != 27 && v != 28) return address(0);
        return ecrecover(hash, v, r, s);
    }
}
