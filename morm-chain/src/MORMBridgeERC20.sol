// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// @title MORMBridgeERC20 — federated lock/unlock for arbitrary ERC-20s
/// @notice Spec ref: MORM.md §1, §4 — "BTC/ETH/SOL を受け入れて DEX で MORM
///         tokenにスワップ". Same shape as MORMBridge but the asset is an
///         ERC-20 token, not native ETH. The L1 mints/burns a parallel
///         token-kind balance (e.g. USDC.morm) keyed off the (token,
///         amount) tuple in the Locked event.
///
///         Phase 13b/13c upgrades (multi-sig + challenge window) will be
///         layered onto a derived Bridge contract; this base file stays
///         minimal so the relayer's mental model is "lock → mint" / "burn → unlock".
contract MORMBridgeERC20 {
    address public immutable treasury;

    uint256 public lockNonce;
    uint256 public unlockNonce;

    mapping(bytes32 => bool) public unlocked;

    event TokenLocked(
        uint256 indexed lockNonce,
        address indexed sender,
        address indexed token,
        bytes20 mormAddress,
        uint256 amount
    );
    event TokenUnlocked(
        uint256 indexed unlockNonce,
        address indexed recipient,
        address indexed token,
        bytes32 mormBurnId,
        uint256 amount
    );

    error NotTreasury();
    error AlreadyUnlocked();
    error TransferFailed();
    error ZeroAmount();
    error ZeroAddress();

    modifier onlyTreasury() {
        if (msg.sender != treasury) revert NotTreasury();
        _;
    }

    constructor(address _treasury) {
        if (_treasury == address(0)) revert ZeroAddress();
        treasury = _treasury;
    }

    /// @notice Pull `amount` of `token` from the caller (after they
    ///         `approve(address(this), amount)`) and emit the Locked event.
    function lockToken(address token, uint256 amount, bytes20 mormAddress) external {
        if (amount == 0) revert ZeroAmount();
        if (token == address(0) || mormAddress == bytes20(0)) revert ZeroAddress();
        bool ok = IERC20(token).transferFrom(msg.sender, address(this), amount);
        if (!ok) revert TransferFailed();
        unchecked { ++lockNonce; }
        emit TokenLocked(lockNonce, msg.sender, token, mormAddress, amount);
    }

    /// @notice Treasury-relayed unlock after observing a token-aware
    ///         BRIDGE_BURN on the L1.
    function unlockToken(
        address token,
        address recipient,
        uint256 amount,
        bytes32 mormBurnId
    ) external onlyTreasury {
        if (recipient == address(0) || token == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (unlocked[mormBurnId]) revert AlreadyUnlocked();
        unlocked[mormBurnId] = true;
        unchecked { ++unlockNonce; }
        bool ok = IERC20(token).transfer(recipient, amount);
        if (!ok) revert TransferFailed();
        emit TokenUnlocked(unlockNonce, recipient, token, mormBurnId, amount);
    }
}
