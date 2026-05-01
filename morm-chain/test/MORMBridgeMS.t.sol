// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {MORMBridgeMS} from "../src/MORMBridgeMS.sol";

contract MORMBridgeMSTest is Test {
    MORMBridgeMS bridge;
    uint256 constant K1 = 0xA11CE;
    uint256 constant K2 = 0xB0B;
    uint256 constant K3 = 0xC0C;
    uint256 constant K4 = 0xD0D;
    address s1; address s2; address s3; address s4; address s_unauth;

    address alice = makeAddr("alice");
    address bob   = makeAddr("bob");
    bytes20 mormAddr = bytes20(keccak256("morm"));
    bytes32 burnId   = keccak256("burn");

    function setUp() public {
        s1 = vm.addr(K1); s2 = vm.addr(K2); s3 = vm.addr(K3); s4 = vm.addr(K4);
        s_unauth = vm.addr(0xDEAD);

        // register K1/K2/K3 as signers (sorted ascending for the constructor's
        // duplicate check, which doubles as ordering)
        address[] memory three = _sortAsc3(s1, s2, s3);
        bridge = new MORMBridgeMS(three, 2);   // 2-of-3
        vm.deal(alice, 10 ether);
    }

    function test_unlock_with_quorum_succeeds() public {
        vm.prank(alice);
        bridge.lock{value: 1 ether}(mormAddr);

        bytes32 digest = bridge.unlockDigest(bob, 1 ether, burnId);
        bytes memory sig1 = _signEth(K1, digest);
        bytes memory sig2 = _signEth(K2, digest);

        // ascending order required — pick the two whose addresses sort lowest
        bytes[] memory sigs = _orderedTwo(K1, K2, digest);

        vm.prank(alice);
        bridge.unlock(bob, 1 ether, burnId, sigs);
        assertEq(bob.balance, 1 ether);
        assertTrue(bridge.unlocked(burnId));
    }

    function test_revert_below_threshold() public {
        vm.prank(alice);
        bridge.lock{value: 1 ether}(mormAddr);

        bytes32 digest = bridge.unlockDigest(bob, 1 ether, burnId);
        bytes[] memory sigs = new bytes[](1);
        sigs[0] = _signEth(K1, digest);
        vm.prank(alice);
        vm.expectRevert(MORMBridgeMS.NotEnoughSignatures.selector);
        bridge.unlock(bob, 1 ether, burnId, sigs);
    }

    function test_revert_unauthorized_signer() public {
        vm.prank(alice);
        bridge.lock{value: 1 ether}(mormAddr);

        bytes32 digest = bridge.unlockDigest(bob, 1 ether, burnId);
        bytes[] memory sigs = _orderedTwo(K1, 0xDEAD, digest);
        vm.prank(alice);
        vm.expectRevert(MORMBridgeMS.BadSignature.selector);
        bridge.unlock(bob, 1 ether, burnId, sigs);
    }

    function test_revert_replay_same_signers() public {
        vm.prank(alice);
        bridge.lock{value: 1 ether}(mormAddr);

        bytes32 digest = bridge.unlockDigest(bob, 1 ether, burnId);
        bytes[] memory sigs = _orderedTwo(K1, K2, digest);
        vm.prank(alice);
        bridge.unlock(bob, 1 ether, burnId, sigs);
        vm.prank(alice);
        vm.expectRevert(MORMBridgeMS.AlreadyUnlocked.selector);
        bridge.unlock(bob, 1 ether, burnId, sigs);
    }

    function test_revert_duplicate_signer() public {
        vm.prank(alice);
        bridge.lock{value: 1 ether}(mormAddr);

        bytes32 digest = bridge.unlockDigest(bob, 1 ether, burnId);
        bytes[] memory sigs = new bytes[](2);
        sigs[0] = _signEth(K1, digest);
        sigs[1] = _signEth(K1, digest);     // duplicate
        vm.prank(alice);
        vm.expectRevert(MORMBridgeMS.DuplicateOrUnknownSigner.selector);
        bridge.unlock(bob, 1 ether, burnId, sigs);
    }

    // -- helpers ----------------------------------------------------------

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
