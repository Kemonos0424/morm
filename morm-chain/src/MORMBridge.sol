// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title MORMBridge — federated lock/unlock for ETH ↔ MORM Chain swap
/// @notice Spec ref: MORM.md §1, §4 — "BTC/ETH/SOLを受け入れ、DEX経由でMORM
///         tokenにスワップ". This is the simplest realization: a relayer
///         (initially the treasury) observes lock events on this contract,
///         mints equivalent µMORM on the L1, and the reverse path observes
///         BRIDGE_BURN on the L1 to call unlock() here.
///
///         Production: replace the single relayer with a quorum of validator
///         signatures (multisig / threshold) and add a challenge window.
contract MORMBridge {
    address public immutable treasury;     // also the only allowed relayer

    /// @dev queue position so the off-chain relayer can dedupe and recover.
    uint256 public lockNonce;
    uint256 public unlockNonce;

    /// @dev replay-protection: an unlock claim by (mormBurnId) is one-shot.
    mapping(bytes32 => bool) public unlocked;

    event Locked(
        uint256 indexed lockNonce,
        address indexed sender,
        bytes20 indexed mormAddress,    // 20-byte MORM L1 address
        uint256 amount
    );
    event Unlocked(
        uint256 indexed unlockNonce,
        address indexed recipient,
        bytes32 indexed mormBurnId,     // L1 BRIDGE_BURN tx hash
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

    /// @notice Lock ETH on this side. The relayer mints `amount` µMORM on the
    ///         L1 to `mormAddress`. Pass any 20-byte L1 address.
    function lock(bytes20 mormAddress) external payable {
        if (msg.value == 0) revert ZeroAmount();
        if (mormAddress == bytes20(0)) revert ZeroAddress();
        unchecked { ++lockNonce; }
        emit Locked(lockNonce, msg.sender, mormAddress, msg.value);
    }

    /// @notice Called by the relayer after it observes a confirmed BRIDGE_BURN
    ///         on the L1. `mormBurnId` is the L1 tx hash (32 bytes), used as a
    ///         replay-protection key.
    function unlock(address recipient, uint256 amount, bytes32 mormBurnId)
        external onlyTreasury
    {
        if (recipient == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (unlocked[mormBurnId]) revert AlreadyUnlocked();
        unlocked[mormBurnId] = true;
        unchecked { ++unlockNonce; }
        (bool ok, ) = recipient.call{value: amount}("");
        if (!ok) revert TransferFailed();
        emit Unlocked(unlockNonce, recipient, mormBurnId, amount);
    }

    receive() external payable {
        // direct ETH sends are not supported — must go through lock()
        revert ZeroAmount();
    }
}
