// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title MORMBridgeMS — multi-sig (M-of-N) federated lock/unlock for ETH
/// @notice Hardens MORMBridge: a quorum of distinct signers must each sign
///         the unlock claim before any single relayer can submit it on-chain.
///         The signed digest binds (recipient, amount, mormBurnId, address(this))
///         so a signature gathered for one bridge can't be replayed elsewhere.
contract MORMBridgeMS {
    address[] public signers;
    uint256 public immutable threshold;

    uint256 public lockNonce;
    uint256 public unlockNonce;
    mapping(bytes32 => bool) public unlocked;
    mapping(address => bool) public isSigner;

    event Locked(uint256 indexed lockNonce, address indexed sender,
                  bytes20 indexed mormAddress, uint256 amount);
    event Unlocked(uint256 indexed unlockNonce, address indexed recipient,
                    bytes32 indexed mormBurnId, uint256 amount);

    error AlreadyUnlocked();
    error TransferFailed();
    error ZeroAmount();
    error ZeroAddress();
    error BadSignerCount();
    error DuplicateOrUnknownSigner();
    error BadSignature();
    error NotEnoughSignatures();

    constructor(address[] memory _signers, uint256 _threshold) {
        if (_signers.length == 0 || _threshold == 0 || _threshold > _signers.length)
            revert BadSignerCount();
        threshold = _threshold;
        for (uint256 i; i < _signers.length; ++i) {
            if (_signers[i] == address(0)) revert ZeroAddress();
            if (isSigner[_signers[i]]) revert DuplicateOrUnknownSigner();
            isSigner[_signers[i]] = true;
            signers.push(_signers[i]);
        }
    }

    function lock(bytes20 mormAddress) external payable {
        if (msg.value == 0) revert ZeroAmount();
        if (mormAddress == bytes20(0)) revert ZeroAddress();
        unchecked { ++lockNonce; }
        emit Locked(lockNonce, msg.sender, mormAddress, msg.value);
    }

    /// @notice Submit `signatures` from at least `threshold` distinct signers
    ///         attesting to (recipient, amount, mormBurnId). The signatures
    ///         are 65-byte (r,s,v) eth_sign-compatible blobs concatenated.
    ///
    /// Phase 26f audit notes:
    ///   - "arbitrary-send-eth": Slither flags the recipient.call below as
    ///     unauthenticated, but the M-of-N signature loop above is THE
    ///     authentication: every released ETH transfer must carry signatures
    ///     from `threshold` distinct registered signers over the exact
    ///     (recipient, amount, mormBurnId, chainId, this) digest. This is
    ///     the documented bridge security model.
    ///   - CEI: `unlocked[mormBurnId] = true` and `++unlockNonce` are written
    ///     BEFORE the external call, so a malicious recipient cannot
    ///     re-enter and double-claim the same burn id.
    function unlock(
        address recipient,
        uint256 amount,
        bytes32 mormBurnId,
        bytes[] calldata signatures
    ) external {
        if (recipient == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (unlocked[mormBurnId]) revert AlreadyUnlocked();
        if (signatures.length < threshold) revert NotEnoughSignatures();

        bytes32 digest = unlockDigest(recipient, amount, mormBurnId);
        bytes32 ethDigest = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n32", digest));

        // Phase 26f — explicit zero-init silences Slither's
        // uninitialized-local even though Solidity already defaults
        // these to address(0) / 0; clarity over compiler quirks.
        address last  = address(0);   // signers ordered ascending → dedup
        uint256 valid = 0;
        for (uint256 i; i < signatures.length; ++i) {
            address signer = _recover(ethDigest, signatures[i]);
            if (signer == address(0) || !isSigner[signer]) revert BadSignature();
            if (signer <= last) revert DuplicateOrUnknownSigner();
            last = signer;
            unchecked { ++valid; }
        }
        if (valid < threshold) revert NotEnoughSignatures();

        unlocked[mormBurnId] = true;
        unchecked { ++unlockNonce; }
        // slither-disable-next-line arbitrary-send-eth
        (bool ok, ) = recipient.call{value: amount}("");
        if (!ok) revert TransferFailed();
        emit Unlocked(unlockNonce, recipient, mormBurnId, amount);
    }

    function unlockDigest(address recipient, uint256 amount, bytes32 mormBurnId)
        public view returns (bytes32)
    {
        return keccak256(abi.encode(
            address(this), block.chainid, "MORMBridgeMS:unlock",
            recipient, amount, mormBurnId
        ));
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
        if (v < 27) v += 27;
        if (v != 27 && v != 28) return address(0);
        return ecrecover(hash, v, r, s);
    }

    receive() external payable {
        revert ZeroAmount();
    }
}
