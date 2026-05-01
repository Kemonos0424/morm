// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {MORMBridge} from "../src/MORMBridge.sol";

contract MORMBridgeTest is Test {
    MORMBridge bridge;
    address treasury = makeAddr("treasury");
    address alice    = makeAddr("alice");
    address bob      = makeAddr("bob");
    bytes20 mormAddr = bytes20(keccak256("morm-addr"));
    bytes32 burnId   = keccak256("burn-1");

    function setUp() public {
        bridge = new MORMBridge(treasury);
        vm.deal(alice, 10 ether);
        vm.deal(treasury, 10 ether);
    }

    function test_lock_emits_event_and_holds_eth() public {
        vm.expectEmit(true, true, true, true);
        emit MORMBridge.Locked(1, alice, mormAddr, 1 ether);
        vm.prank(alice);
        bridge.lock{value: 1 ether}(mormAddr);
        assertEq(address(bridge).balance, 1 ether);
        assertEq(bridge.lockNonce(), 1);
    }

    function test_unlock_releases_eth_to_recipient() public {
        vm.prank(alice);
        bridge.lock{value: 1 ether}(mormAddr);

        uint256 before = bob.balance;
        vm.prank(treasury);
        bridge.unlock(bob, 1 ether, burnId);
        assertEq(bob.balance - before, 1 ether);
        assertTrue(bridge.unlocked(burnId));
        assertEq(bridge.unlockNonce(), 1);
    }

    function test_revert_unlock_replay() public {
        vm.prank(alice);
        bridge.lock{value: 2 ether}(mormAddr);
        vm.prank(treasury);
        bridge.unlock(bob, 1 ether, burnId);
        vm.prank(treasury);
        vm.expectRevert(MORMBridge.AlreadyUnlocked.selector);
        bridge.unlock(bob, 1 ether, burnId);
    }

    function test_revert_unlock_by_non_treasury() public {
        vm.prank(alice);
        bridge.lock{value: 1 ether}(mormAddr);
        vm.prank(alice);
        vm.expectRevert(MORMBridge.NotTreasury.selector);
        bridge.unlock(bob, 1 ether, burnId);
    }

    function test_revert_lock_zero_amount() public {
        vm.prank(alice);
        vm.expectRevert(MORMBridge.ZeroAmount.selector);
        bridge.lock{value: 0}(mormAddr);
    }

    function test_revert_lock_zero_address() public {
        vm.prank(alice);
        vm.expectRevert(MORMBridge.ZeroAddress.selector);
        bridge.lock{value: 1 ether}(bytes20(0));
    }

    function test_revert_direct_send_rejected() public {
        vm.prank(alice);
        (bool ok, ) = address(bridge).call{value: 1 ether}("");
        assertFalse(ok);
    }
}
