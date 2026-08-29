// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {WMORM} from "../src/WMORM.sol";
import {MORMExportBridge} from "../src/MORMExportBridge.sol";

/// Adversarial review harness — empirically verifies the security claims:
/// cross-chain / cross-contract replay binding, high-s malleability rejection,
/// signature ordering, recipient binding, and the rate-limit boundary.
contract MORMExportBridgeAdversarialTest is Test {
    WMORM token;
    MORMExportBridge bridge;

    uint256 constant K1 = 0xA11CE;
    uint256 constant K2 = 0xB0B;
    uint256 constant K3 = 0xC0C;
    address s1; address s2; address s3;
    address guardian = makeAddr("guardian");
    address bob   = makeAddr("bob");
    address eve   = makeAddr("eve");
    bytes20 mormAddr = bytes20(keccak256("morm"));

    // secp256k1 group order
    uint256 constant N =
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141;

    uint256 constant WINDOW = 1 hours;
    uint256 constant MAXW   = 1_000 ether;

    uint256 constant CAP = 1_000_000 ether;

    function setUp() public {
        s1 = vm.addr(K1); s2 = vm.addr(K2); s3 = vm.addr(K3);
        token = new WMORM();
        address[] memory three = _sortAsc3(s1, s2, s3);
        bridge = new MORMExportBridge(address(token), three, 2, guardian, WINDOW, MAXW, CAP, 0);
        token.setBridge(address(bridge));
    }

    function test_absolute_supply_cap_enforced() public {
        // dedicated bridge with a tiny absolute cap
        WMORM t2 = new WMORM();
        address[] memory three = _sortAsc3(s1, s2, s3);
        // large per-window budget so the *absolute* cap is what bites
        MORMExportBridge b = new MORMExportBridge(
            address(t2), three, 2, guardian, WINDOW, 1_000_000 ether, 100 ether, 0);
        t2.setBridge(address(b));

        bytes32 d1 = b.mintDigest(bob, 100 ether, keccak256("c1"));
        b.mintFromBurn(bob, 100 ether, keccak256("c1"), _orderedTwo(K1, K2, d1));
        assertEq(t2.totalSupply(), 100 ether);

        // one more wei over the absolute cap reverts, even within the window
        bytes32 d2 = b.mintDigest(bob, 1, keccak256("c2"));
        vm.expectRevert(MORMExportBridge.CapExceeded.selector);
        b.mintFromBurn(bob, 1, keccak256("c2"), _orderedTwo(K1, K2, d2));

        // after a user exits, headroom frees up and minting resumes
        vm.prank(bob);
        b.exit(40 ether, mormAddr);
        assertEq(t2.totalSupply(), 60 ether);
        b.mintFromBurn(bob, 40 ether, keccak256("c2"), _orderedTwo(K1, K2, b.mintDigest(bob, 40 ether, keccak256("c2"))));
        assertEq(t2.totalSupply(), 100 ether);
    }

    function test_min_exit_enforced() public {
        WMORM t2 = new WMORM();
        address[] memory three = _sortAsc3(s1, s2, s3);
        MORMExportBridge b = new MORMExportBridge(
            address(t2), three, 2, guardian, WINDOW, MAXW, CAP, 5 ether);   // minExit = 5
        t2.setBridge(address(b));
        b.mintFromBurn(bob, 10 ether, keccak256("m"), _orderedTwo(K1, K2, b.mintDigest(bob, 10 ether, keccak256("m"))));

        vm.prank(bob);
        vm.expectRevert(MORMExportBridge.BelowMinExit.selector);
        b.exit(4 ether, mormAddr);

        vm.prank(bob);
        b.exit(5 ether, mormAddr);   // exactly the floor is allowed
        assertEq(t2.balanceOf(bob), 5 ether);
    }

    function test_cross_chain_replay_rejected() public {
        // sign the digest as computed on the CURRENT chainid
        bytes32 digest = bridge.mintDigest(bob, 10 ether, keccak256("x"));
        bytes[] memory sigs = _orderedTwo(K1, K2, digest);
        // now pretend we're on a different chain; contract recomputes digest
        // with the new chainid -> gathered sigs no longer recover to signers
        vm.chainId(999);
        vm.expectRevert(MORMExportBridge.BadSignature.selector);
        bridge.mintFromBurn(bob, 10 ether, keccak256("x"), sigs);
    }

    function test_cross_contract_replay_rejected() public {
        // a second bridge with the SAME signer set
        address[] memory three = _sortAsc3(s1, s2, s3);
        MORMExportBridge bridge2 =
            new MORMExportBridge(address(token), three, 2, guardian, WINDOW, MAXW, CAP, 0);
        // signatures gathered for `bridge` (its address in the digest)
        bytes32 digest = bridge.mintDigest(bob, 10 ether, keccak256("y"));
        bytes[] memory sigs = _orderedTwo(K1, K2, digest);
        // replaying on bridge2 fails: digest binds address(this)
        vm.expectRevert(MORMExportBridge.BadSignature.selector);
        bridge2.mintFromBurn(bob, 10 ether, keccak256("y"), sigs);
    }

    function test_high_s_malleable_signature_rejected() public {
        bytes32 digest = bridge.mintDigest(bob, 10 ether, keccak256("z"));
        bytes32 ethDigest = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n32", digest));
        // low-s sigs from the two lowest-address signers, in ascending order
        (uint256 ka, uint256 kb) = _ascKeys(K1, K2);
        bytes memory lowA = _sigMalleated(ka, ethDigest);
        bytes memory sigB = _sign(kb, ethDigest);
        bytes[] memory sigs = new bytes[](2);
        sigs[0] = lowA;   // malleated (high-s) form of signer A
        sigs[1] = sigB;
        vm.expectRevert(MORMExportBridge.BadSignature.selector);
        bridge.mintFromBurn(bob, 10 ether, keccak256("z"), sigs);
    }

    function test_descending_order_rejected() public {
        bytes32 digest = bridge.mintDigest(bob, 10 ether, keccak256("o"));
        bytes32 ethDigest = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n32", digest));
        (uint256 ka, uint256 kb) = _ascKeys(K1, K2);
        // deliberately reversed (descending) -> signer <= last triggers
        bytes[] memory sigs = new bytes[](2);
        sigs[0] = _sign(kb, ethDigest);
        sigs[1] = _sign(ka, ethDigest);
        vm.expectRevert(MORMExportBridge.DuplicateOrUnknownSigner.selector);
        bridge.mintFromBurn(bob, 10 ether, keccak256("o"), sigs);
    }

    function test_recipient_binding_rejected() public {
        // signers attest to bob; submitter tries to redirect to eve
        bytes32 digest = bridge.mintDigest(bob, 10 ether, keccak256("r"));
        bytes[] memory sigs = _orderedTwo(K1, K2, digest);
        vm.expectRevert(MORMExportBridge.BadSignature.selector);
        bridge.mintFromBurn(eve, 10 ether, keccak256("r"), sigs);
    }

    function test_rate_limit_exact_boundary() public {
        // exactly the cap in one shot is allowed
        _mint(bob, MAXW, keccak256("cap"));
        assertEq(token.balanceOf(bob), MAXW);
        // one wei more within the same window is rejected
        bytes32 d = bridge.mintDigest(bob, 1, keccak256("over"));
        bytes[] memory sigs = _orderedTwo(K1, K2, d);
        vm.expectRevert(MORMExportBridge.RateLimited.selector);
        bridge.mintFromBurn(bob, 1, keccak256("over"), sigs);
    }

    // -- helpers ----------------------------------------------------------
    function _mint(address to, uint256 amt, bytes32 id) internal {
        bytes32 d = bridge.mintDigest(to, amt, id);
        bytes[] memory sigs = _orderedTwo(K1, K2, d);
        bridge.mintFromBurn(to, amt, id, sigs);
    }

    function _sign(uint256 pk, bytes32 ethDigest) internal pure returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, ethDigest);
        return abi.encodePacked(r, s, v);
    }

    /// return a malleated (high-s) but otherwise valid signature: s' = N - s,
    /// v flipped. ecrecover would still return the same signer, but the
    /// contract's s > HALF_N guard must reject it.
    function _sigMalleated(uint256 pk, bytes32 ethDigest) internal pure returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, ethDigest);
        uint256 sFlipped = N - uint256(s);
        uint8 vFlipped = v == 27 ? 28 : 27;
        return abi.encodePacked(r, bytes32(sFlipped), vFlipped);
    }

    function _signEthDigest(uint256 pk, bytes32 digest) internal pure returns (bytes memory) {
        bytes32 ethDigest = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n32", digest));
        return _sign(pk, ethDigest);
    }

    function _orderedTwo(uint256 ka, uint256 kb, bytes32 digest)
        internal pure returns (bytes[] memory out)
    {
        out = new bytes[](2);
        if (vm.addr(ka) < vm.addr(kb)) {
            out[0] = _signEthDigest(ka, digest);
            out[1] = _signEthDigest(kb, digest);
        } else {
            out[0] = _signEthDigest(kb, digest);
            out[1] = _signEthDigest(ka, digest);
        }
    }

    function _ascKeys(uint256 ka, uint256 kb) internal pure returns (uint256, uint256) {
        return vm.addr(ka) < vm.addr(kb) ? (ka, kb) : (kb, ka);
    }

    function _sortAsc3(address a, address b, address c)
        internal pure returns (address[] memory out)
    {
        address[] memory arr = new address[](3);
        arr[0] = a; arr[1] = b; arr[2] = c;
        for (uint256 i; i < 3; ++i)
            for (uint256 j = i + 1; j < 3; ++j)
                if (arr[j] < arr[i]) { (arr[i], arr[j]) = (arr[j], arr[i]); }
        out = arr;
    }
}
