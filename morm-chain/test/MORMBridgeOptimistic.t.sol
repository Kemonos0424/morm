// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {MORMBridgeOptimistic} from "../src/MORMBridgeOptimistic.sol";

contract MORMBridgeOptimisticTest is Test {
    MORMBridgeOptimistic bridge;
    address treasury  = makeAddr("treasury");
    address alice     = makeAddr("alice");
    address bob       = makeAddr("bob");
    address watchdog  = makeAddr("watchdog");
    bytes20 mormAddr  = bytes20(keccak256("morm"));
    bytes32 burnId    = keccak256("burn");
    uint256 constant PERIOD = 1 hours;

    function setUp() public {
        bridge = new MORMBridgeOptimistic(treasury, PERIOD);
        vm.deal(alice, 10 ether);
    }

    function _seedLock() internal {
        vm.prank(alice);
        bridge.lock{value: 1 ether}(mormAddr);
    }

    function test_propose_then_finalize_after_window() public {
        _seedLock();
        vm.prank(treasury);
        bridge.proposeUnlock(bob, 1 ether, burnId);
        // before window — must revert
        vm.expectRevert(MORMBridgeOptimistic.TooEarly.selector);
        bridge.finalizeUnlock(burnId);
        skip(PERIOD + 1);
        bridge.finalizeUnlock(burnId);
        assertEq(bob.balance, 1 ether);
        assertTrue(bridge.unlocked(burnId));
    }

    function test_challenge_blocks_finalize() public {
        _seedLock();
        vm.prank(treasury);
        bridge.proposeUnlock(bob, 1 ether, burnId);
        vm.prank(watchdog);
        bridge.challengeUnlock(burnId);
        skip(PERIOD + 1);
        vm.expectRevert(MORMBridgeOptimistic.AlreadyChallenged.selector);
        bridge.finalizeUnlock(burnId);
        // funds still locked, bob received nothing
        assertEq(bob.balance, 0);
    }

    function test_revert_challenge_after_window() public {
        _seedLock();
        vm.prank(treasury);
        bridge.proposeUnlock(bob, 1 ether, burnId);
        skip(PERIOD + 1);
        vm.prank(watchdog);
        vm.expectRevert(MORMBridgeOptimistic.TooEarly.selector);
        bridge.challengeUnlock(burnId);
    }

    function test_revert_propose_by_non_treasury() public {
        _seedLock();
        vm.prank(alice);
        vm.expectRevert(MORMBridgeOptimistic.NotTreasury.selector);
        bridge.proposeUnlock(bob, 1 ether, burnId);
    }

    function test_revert_double_propose() public {
        _seedLock();
        vm.prank(treasury);
        bridge.proposeUnlock(bob, 1 ether, burnId);
        vm.prank(treasury);
        vm.expectRevert(MORMBridgeOptimistic.AlreadyUnlocked.selector);
        bridge.proposeUnlock(bob, 1 ether, burnId);
    }
}
