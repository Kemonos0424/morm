// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {MORMBridgeERC20} from "../src/MORMBridgeERC20.sol";
import {MockUSDC} from "../src/MockUSDC.sol";

contract MORMBridgeERC20Test is Test {
    MORMBridgeERC20 bridge;
    MockUSDC usdc;
    address treasury = makeAddr("treasury");
    address alice    = makeAddr("alice");
    address bob      = makeAddr("bob");
    bytes20 mormAddr = bytes20(keccak256("morm-addr"));
    bytes32 burnId   = keccak256("burn-1");

    function setUp() public {
        usdc   = new MockUSDC();
        bridge = new MORMBridgeERC20(treasury);
        usdc.mint(alice, 1_000 * 1e6);
    }

    function test_lock_pulls_tokens_emits_event() public {
        vm.prank(alice); usdc.approve(address(bridge), 100 * 1e6);
        vm.expectEmit(true, true, true, true);
        emit MORMBridgeERC20.TokenLocked(1, alice, address(usdc), mormAddr, 100 * 1e6);
        vm.prank(alice);
        bridge.lockToken(address(usdc), 100 * 1e6, mormAddr);
        assertEq(usdc.balanceOf(address(bridge)), 100 * 1e6);
        assertEq(usdc.balanceOf(alice),            900 * 1e6);
    }

    function test_unlock_releases_tokens_to_recipient() public {
        vm.prank(alice); usdc.approve(address(bridge), 100 * 1e6);
        vm.prank(alice); bridge.lockToken(address(usdc), 100 * 1e6, mormAddr);
        vm.prank(treasury);
        bridge.unlockToken(address(usdc), bob, 60 * 1e6, burnId);
        assertEq(usdc.balanceOf(bob),               60 * 1e6);
        assertEq(usdc.balanceOf(address(bridge)),   40 * 1e6);
        assertTrue(bridge.unlocked(burnId));
    }

    function test_revert_unlock_replay() public {
        vm.prank(alice); usdc.approve(address(bridge), 100 * 1e6);
        vm.prank(alice); bridge.lockToken(address(usdc), 100 * 1e6, mormAddr);
        vm.prank(treasury);
        bridge.unlockToken(address(usdc), bob, 50 * 1e6, burnId);
        vm.prank(treasury);
        vm.expectRevert(MORMBridgeERC20.AlreadyUnlocked.selector);
        bridge.unlockToken(address(usdc), bob, 50 * 1e6, burnId);
    }

    function test_revert_lock_without_approval() public {
        vm.prank(alice);
        vm.expectRevert(MockUSDC.InsufficientAllowance.selector);
        bridge.lockToken(address(usdc), 1 * 1e6, mormAddr);
    }
}
