// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {WMORM} from "../src/WMORM.sol";
import {MORMExportBridge} from "../src/MORMExportBridge.sol";

contract MORMExportBridgeTest is Test {
    WMORM token;
    MORMExportBridge bridge;

    uint256 constant K1 = 0xA11CE;
    uint256 constant K2 = 0xB0B;
    uint256 constant K3 = 0xC0C;
    address s1; address s2; address s3;

    address alice = makeAddr("alice");
    address bob   = makeAddr("bob");
    address guardian = makeAddr("guardian");
    bytes20 mormAddr = bytes20(keccak256("morm"));
    bytes32 burnId   = keccak256("burn");

    uint256 constant WINDOW = 1 hours;
    uint256 constant MAXW   = 1_000_000 ether;   // per-window mint cap
    uint256 constant CAP    = 10_000_000 ether;  // absolute supply cap
    uint256 constant MINEX  = 0;                  // min exit disabled here

    function setUp() public {
        s1 = vm.addr(K1); s2 = vm.addr(K2); s3 = vm.addr(K3);
        token = new WMORM();
        address[] memory three = _sortAsc3(s1, s2, s3);
        bridge = new MORMExportBridge(address(token), three, 2, guardian, WINDOW, MAXW, CAP, MINEX);
        token.setBridge(address(bridge));   // 2-of-3
    }

    function test_mint_with_quorum_succeeds() public {
        bytes32 digest = bridge.mintDigest(bob, 100 ether, burnId);
        bytes[] memory sigs = _orderedTwo(K1, K2, digest);
        bridge.mintFromBurn(bob, 100 ether, burnId, sigs);
        assertEq(token.balanceOf(bob), 100 ether);
        assertEq(token.totalSupply(), 100 ether);
        assertTrue(bridge.minted(burnId));
    }

    function test_revert_replay_same_burnId() public {
        bytes32 digest = bridge.mintDigest(bob, 100 ether, burnId);
        bytes[] memory sigs = _orderedTwo(K1, K2, digest);
        bridge.mintFromBurn(bob, 100 ether, burnId, sigs);
        vm.expectRevert(MORMExportBridge.AlreadyMinted.selector);
        bridge.mintFromBurn(bob, 100 ether, burnId, sigs);
    }

    function test_revert_below_threshold() public {
        bytes32 digest = bridge.mintDigest(bob, 100 ether, burnId);
        bytes[] memory sigs = new bytes[](1);
        sigs[0] = _signEth(K1, digest);
        vm.expectRevert(MORMExportBridge.NotEnoughSignatures.selector);
        bridge.mintFromBurn(bob, 100 ether, burnId, sigs);
    }

    function test_revert_unauthorized_signer() public {
        bytes32 digest = bridge.mintDigest(bob, 100 ether, burnId);
        bytes[] memory sigs = _orderedTwo(K1, 0xDEAD, digest);
        vm.expectRevert(MORMExportBridge.BadSignature.selector);
        bridge.mintFromBurn(bob, 100 ether, burnId, sigs);
    }

    function test_revert_duplicate_signer() public {
        bytes32 digest = bridge.mintDigest(bob, 100 ether, burnId);
        bytes[] memory sigs = new bytes[](2);
        sigs[0] = _signEth(K1, digest);
        sigs[1] = _signEth(K1, digest);
        vm.expectRevert(MORMExportBridge.DuplicateOrUnknownSigner.selector);
        bridge.mintFromBurn(bob, 100 ether, burnId, sigs);
    }

    function test_revert_wrong_amount_signature() public {
        // signers signed for 100, caller claims 200 -> digest mismatch -> bad sig
        bytes32 digest = bridge.mintDigest(bob, 100 ether, burnId);
        bytes[] memory sigs = _orderedTwo(K1, K2, digest);
        vm.expectRevert(MORMExportBridge.BadSignature.selector);
        bridge.mintFromBurn(bob, 200 ether, burnId, sigs);
    }

    function test_rate_limit_and_window_reset() public {
        // first mint just under cap
        _mint(bob, MAXW - 1 ether, keccak256("b1"));
        // next mint that exceeds the remaining window budget reverts
        bytes32 d2 = bridge.mintDigest(bob, 2 ether, keccak256("b2"));
        bytes[] memory sigs2 = _orderedTwo(K1, K2, d2);
        vm.expectRevert(MORMExportBridge.RateLimited.selector);
        bridge.mintFromBurn(bob, 2 ether, keccak256("b2"), sigs2);
        // after the window elapses, the budget resets and it succeeds
        vm.warp(block.timestamp + WINDOW + 1);
        bridge.mintFromBurn(bob, 2 ether, keccak256("b2"), sigs2);
        assertEq(token.balanceOf(bob), MAXW + 1 ether);
    }

    function test_pause_blocks_mint_then_unpause() public {
        vm.prank(guardian);
        bridge.setPaused(true);
        bytes32 digest = bridge.mintDigest(bob, 100 ether, burnId);
        bytes[] memory sigs = _orderedTwo(K1, K2, digest);
        vm.expectRevert(MORMExportBridge.IsPaused.selector);
        bridge.mintFromBurn(bob, 100 ether, burnId, sigs);
        vm.prank(guardian);
        bridge.setPaused(false);
        bridge.mintFromBurn(bob, 100 ether, burnId, sigs);
        assertEq(token.balanceOf(bob), 100 ether);
    }

    function test_only_guardian_can_pause() public {
        vm.prank(alice);
        vm.expectRevert(MORMExportBridge.NotGuardian.selector);
        bridge.setPaused(true);
    }

    function test_exit_burns_and_emits() public {
        _mint(alice, 50 ether, burnId);
        vm.expectEmit(true, true, true, true);
        emit MORMExportBridge.Exit(1, alice, mormAddr, 30 ether);
        vm.prank(alice);
        bridge.exit(30 ether, mormAddr);
        assertEq(token.balanceOf(alice), 20 ether);
        assertEq(token.totalSupply(), 20 ether);
    }

    function test_exit_reverts_without_balance() public {
        vm.prank(alice);
        vm.expectRevert(WMORM.InsufficientBalance.selector);
        bridge.exit(1 ether, mormAddr);
    }

    function test_only_bridge_can_mint() public {
        vm.prank(alice);
        vm.expectRevert(WMORM.NotBridge.selector);
        token.mint(alice, 1 ether);
    }

    // -- helpers ----------------------------------------------------------
    function _mint(address to, uint256 amt, bytes32 id) internal {
        bytes32 d = bridge.mintDigest(to, amt, id);
        bytes[] memory sigs = _orderedTwo(K1, K2, d);
        bridge.mintFromBurn(to, amt, id, sigs);
    }

    function _signEth(uint256 pk, bytes32 digest) internal pure returns (bytes memory) {
        bytes32 ethDigest = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n32", digest));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, ethDigest);
        return abi.encodePacked(r, s, v);
    }

    function _orderedTwo(uint256 ka, uint256 kb, bytes32 digest)
        internal pure returns (bytes[] memory out)
    {
        address aa = vm.addr(ka);
        address bb = vm.addr(kb);
        out = new bytes[](2);
        if (aa < bb) {
            out[0] = _signEth(ka, digest);
            out[1] = _signEth(kb, digest);
        } else {
            out[0] = _signEth(kb, digest);
            out[1] = _signEth(ka, digest);
        }
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
