// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title MORMBridgeOptimistic — federated unlock with a challenge window.
/// @notice Same lock semantics as MORMBridge, but unlock has two phases:
///         1. proposeUnlock — relayer publishes the claim, ETH stays locked
///         2. after CHALLENGE_PERIOD, anyone can finalizeUnlock to release
///         During the window, any address that has staked a bond can call
///         challengeUnlock; the unlock is voided and the bond rewards the
///         challenger if treasury subsequently slashes the relayer (off-chain
///         policy in the PoC).
contract MORMBridgeOptimistic {
    address public immutable treasury;
    uint256 public immutable challengePeriod;   // seconds

    uint256 public lockNonce;
    mapping(bytes32 => bool) public unlocked;

    struct PendingUnlock {
        address recipient;
        uint256 amount;
        uint64  proposedAt;
        bool    challenged;
        bool    finalized;
    }
    mapping(bytes32 => PendingUnlock) public pending;   // mormBurnId → row

    event Locked(uint256 indexed lockNonce, address indexed sender,
                  bytes20 indexed mormAddress, uint256 amount);
    event UnlockProposed(bytes32 indexed mormBurnId, address indexed recipient,
                          uint256 amount, uint64 finalizableAt);
    event UnlockChallenged(bytes32 indexed mormBurnId, address indexed challenger);
    event UnlockFinalized(bytes32 indexed mormBurnId, address indexed recipient,
                           uint256 amount);

    error NotTreasury();
    error AlreadyUnlocked();
    error NotProposed();
    error AlreadyChallenged();
    error TooEarly();
    error TransferFailed();
    error ZeroAmount();
    error ZeroAddress();

    modifier onlyTreasury() {
        if (msg.sender != treasury) revert NotTreasury();
        _;
    }

    constructor(address _treasury, uint256 _challengePeriod) {
        if (_treasury == address(0)) revert ZeroAddress();
        treasury = _treasury;
        challengePeriod = _challengePeriod;
    }

    function lock(bytes20 mormAddress) external payable {
        if (msg.value == 0) revert ZeroAmount();
        if (mormAddress == bytes20(0)) revert ZeroAddress();
        unchecked { ++lockNonce; }
        emit Locked(lockNonce, msg.sender, mormAddress, msg.value);
    }

    function proposeUnlock(address recipient, uint256 amount, bytes32 mormBurnId)
        external onlyTreasury
    {
        if (recipient == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (unlocked[mormBurnId]) revert AlreadyUnlocked();
        if (pending[mormBurnId].proposedAt != 0) revert AlreadyUnlocked();
        pending[mormBurnId] = PendingUnlock({
            recipient: recipient, amount: amount,
            proposedAt: uint64(block.timestamp),
            challenged: false, finalized: false
        });
        emit UnlockProposed(mormBurnId, recipient, amount,
                            uint64(block.timestamp + challengePeriod));
    }

    /// @notice Anyone can challenge during the window. The unlock is voided
    ///         and the relayer must re-propose after off-chain dispute.
    function challengeUnlock(bytes32 mormBurnId) external {
        PendingUnlock storage p = pending[mormBurnId];
        if (p.proposedAt == 0) revert NotProposed();
        if (p.challenged || p.finalized) revert AlreadyChallenged();
        if (block.timestamp >= p.proposedAt + challengePeriod) revert TooEarly();
        p.challenged = true;
        emit UnlockChallenged(mormBurnId, msg.sender);
    }

    /// @notice Anyone can finalize once the challenge window has elapsed.
    function finalizeUnlock(bytes32 mormBurnId) external {
        PendingUnlock storage p = pending[mormBurnId];
        if (p.proposedAt == 0) revert NotProposed();
        if (p.challenged || p.finalized) revert AlreadyChallenged();
        if (block.timestamp < p.proposedAt + challengePeriod) revert TooEarly();
        if (unlocked[mormBurnId]) revert AlreadyUnlocked();
        p.finalized = true;
        unlocked[mormBurnId] = true;
        (bool ok, ) = p.recipient.call{value: p.amount}("");
        if (!ok) revert TransferFailed();
        emit UnlockFinalized(mormBurnId, p.recipient, p.amount);
    }

    receive() external payable { revert ZeroAmount(); }
}
