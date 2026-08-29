// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title GuardianMultisig — M-of-N off-chain-signature multisig for holding a
///        privileged role (designed to be the MORMExportBridge `guardian`).
/// @notice Signers sign an execution digest off-chain; any submitter relays
///         >= threshold signatures to execute exactly one call. Mirrors the
///         bridge's verification: digest bound to
///         (this, chainid, purpose, target, keccak(data), nonce) so a signature
///         can't be replayed on another multisig/chain/target/payload; signers
///         strictly ascending => dedup; low-s enforced => no malleability; a
///         monotonic nonce => no replay of a past approval.
///
///         Separation of duties: deploy with a signer set DISTINCT from the
///         bridge's mint signers, so a mint-quorum compromise does not also
///         grant pause/guardian control (and vice-versa).
contract GuardianMultisig {
    address[] public signers;
    uint256 public immutable threshold;
    mapping(address => bool) public isSigner;
    uint256 public nonce; // monotonic anti-replay

    // secp256k1 order / 2 — reject high-s (EIP-2) signatures
    uint256 internal constant HALF_N =
        0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0;

    event Executed(uint256 indexed nonce, address indexed target, bytes data);

    error BadSignerCount();
    error ZeroAddress();
    error DuplicateOrUnknownSigner();
    error BadSignature();
    error NotEnoughSignatures();
    error CallFailed();

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

    /// @notice Digest the signers sign (EIP-191 prefixed on top of this).
    function execDigest(address target, bytes calldata data, uint256 n)
        public view returns (bytes32)
    {
        return keccak256(abi.encode(
            address(this), block.chainid, "GuardianMultisig:exec",
            target, keccak256(data), n));
    }

    /// @notice Execute one call to `target` with `data` given >= threshold
    ///         distinct signer signatures over the current-nonce digest.
    function execute(address target, bytes calldata data, bytes[] calldata signatures)
        external returns (bytes memory)
    {
        if (signatures.length < threshold) revert NotEnoughSignatures();
        bytes32 ethDigest = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n32", execDigest(target, data, nonce)));

        address last = address(0);
        uint256 valid;
        for (uint256 i; i < signatures.length; ++i) {
            address signer = _recover(ethDigest, signatures[i]);
            if (signer == address(0) || !isSigner[signer]) revert BadSignature();
            if (signer <= last) revert DuplicateOrUnknownSigner(); // strictly ascending
            last = signer;
            unchecked { ++valid; }
        }
        if (valid < threshold) revert NotEnoughSignatures();

        uint256 n = nonce;
        unchecked { ++nonce; } // effect before interaction
        emit Executed(n, target, data);
        (bool ok, bytes memory ret) = target.call(data);
        if (!ok) revert CallFailed();
        return ret;
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
        if (uint256(s) > HALF_N) return address(0);
        if (v < 27) v += 27;
        if (v != 27 && v != 28) return address(0);
        return ecrecover(hash, v, r, s);
    }
}
