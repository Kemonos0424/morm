// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {MORMEscrow} from "../src/MORMEscrow.sol";

contract MORMEscrowTest is Test {
    MORMEscrow esc;
    address treasury = makeAddr("treasury");
    address creator  = makeAddr("creator");
    address buyer    = makeAddr("buyer");
    address seller   = makeAddr("seller");
    address attacker = makeAddr("attacker");

    bytes32 constant CID  = keccak256("content-1");
    bytes32 constant RH   = keccak256("root-hash-1");
    bytes32 constant GID  = keccak256("gen-id-1");
    bytes32 constant ORD  = keccak256("order-1");
    bytes32 constant PACK = keccak256("packing-evidence");
    bytes32 constant OPEN = keccak256("opening-evidence");

    function setUp() public {
        esc = new MORMEscrow(treasury);
        vm.deal(buyer, 100 ether);
        vm.deal(seller, 10 ether);
        vm.deal(attacker, 10 ether);
    }

    // -- Registry ---------------------------------------------------------

    function test_register_content() public {
        vm.prank(creator);
        esc.registerContent(CID, RH, GID);
        (bytes32 rh, bytes32 gid, address c, ) = esc.contents(CID);
        assertEq(rh, RH);
        assertEq(gid, GID);
        assertEq(c, creator);
        assertEq(esc.generationIds(GID), CID);
    }

    function test_revert_double_register() public {
        vm.startPrank(creator);
        esc.registerContent(CID, RH, GID);
        vm.expectRevert(MORMEscrow.AlreadyRegistered.selector);
        esc.registerContent(CID, RH, GID);
        vm.stopPrank();
    }

    function test_revert_generation_id_collision() public {
        vm.prank(creator);
        esc.registerContent(CID, RH, GID);
        bytes32 cid2 = keccak256("content-2");
        vm.prank(attacker);
        vm.expectRevert(MORMEscrow.GenerationCollision.selector);
        esc.registerContent(cid2, RH, GID);
    }

    // -- Order happy path -------------------------------------------------

    function test_order_fee_split_99_1() public {
        _registerOK();

        uint256 amount = 1 ether;
        uint256 treasuryBefore = treasury.balance;

        vm.prank(buyer);
        esc.createOrder{value: amount}(ORD, CID, seller);

        // 1% fee → treasury immediately
        assertEq(treasury.balance - treasuryBefore, amount / 100);
        // 99% locked in escrow contract
        assertEq(address(esc).balance, amount * 99 / 100);
    }

    function test_full_finalize_releases_to_seller() public {
        _registerOK();

        vm.prank(buyer);
        esc.createOrder{value: 1 ether}(ORD, CID, seller);

        vm.prank(seller);
        esc.submitPackingProof(ORD, PACK);

        vm.prank(buyer);
        esc.submitOpeningProof(ORD, OPEN);

        uint256 sellerBefore = seller.balance;
        vm.prank(treasury);
        esc.finalize(ORD, true);
        // seller receives 99% of order
        assertEq(seller.balance - sellerBefore, 1 ether * 99 / 100);
    }

    // -- Order fraud path -------------------------------------------------

    function test_invalid_finalize_refunds_buyer_and_locks_seller() public {
        _registerOK();

        // seller stakes 0.5 ETH — slashable on bad finalize
        vm.prank(seller);
        esc.stakeNode{value: 0.5 ether}();

        vm.prank(buyer);
        esc.createOrder{value: 1 ether}(ORD, CID, seller);

        vm.prank(seller);
        esc.submitPackingProof(ORD, PACK);

        vm.prank(buyer);
        esc.submitOpeningProof(ORD, OPEN);

        uint256 buyerBefore = buyer.balance;
        uint256 treasuryBefore = treasury.balance;

        vm.prank(treasury);
        esc.finalize(ORD, false);

        // buyer refunded 99%
        assertEq(buyer.balance - buyerBefore, 1 ether * 99 / 100);
        // seller's stake slashed → went to treasury
        assertEq(treasury.balance - treasuryBefore, 0.5 ether);
        // seller permanently locked
        assertTrue(esc.nodeLocked(seller));
        assertEq(esc.stakeOf(seller), 0);
    }

    function test_locked_node_cannot_create_orders() public {
        _registerOK();
        vm.prank(seller);
        esc.stakeNode{value: 0.1 ether}();

        // run a fraud finalize to lock seller
        bytes32 ord1 = keccak256("o1");
        vm.prank(buyer);
        esc.createOrder{value: 1 ether}(ord1, CID, seller);
        vm.prank(seller);
        esc.submitPackingProof(ord1, PACK);
        vm.prank(buyer);
        esc.submitOpeningProof(ord1, OPEN);
        vm.prank(treasury);
        esc.finalize(ord1, false);

        assertTrue(esc.nodeLocked(seller));

        // a different buyer tries to use locked seller
        bytes32 ord2 = keccak256("o2");
        vm.prank(attacker);
        vm.expectRevert(MORMEscrow.NodeIsLocked.selector);
        esc.createOrder{value: 1 ether}(ord2, CID, seller);
    }

    function test_locked_node_cannot_register_content() public {
        // make seller locked first
        _registerOK();
        vm.prank(seller);
        esc.stakeNode{value: 0.1 ether}();
        bytes32 ord1 = keccak256("o1");
        vm.prank(buyer);
        esc.createOrder{value: 1 ether}(ord1, CID, seller);
        vm.prank(seller);
        esc.submitPackingProof(ord1, PACK);
        vm.prank(buyer);
        esc.submitOpeningProof(ord1, OPEN);
        vm.prank(treasury);
        esc.finalize(ord1, false);

        vm.prank(seller);
        vm.expectRevert(MORMEscrow.NodeIsLocked.selector);
        esc.registerContent(keccak256("c2"), RH, bytes32(0));
    }

    // -- Authorization ----------------------------------------------------

    function test_revert_finalize_by_non_treasury() public {
        _registerOK();
        vm.prank(buyer);
        esc.createOrder{value: 1 ether}(ORD, CID, seller);
        vm.prank(seller);
        esc.submitPackingProof(ORD, PACK);
        vm.prank(buyer);
        esc.submitOpeningProof(ORD, OPEN);

        vm.prank(attacker);
        vm.expectRevert(MORMEscrow.NotTreasury.selector);
        esc.finalize(ORD, true);
    }

    function test_revert_pack_by_non_seller() public {
        _registerOK();
        vm.prank(buyer);
        esc.createOrder{value: 1 ether}(ORD, CID, seller);
        vm.prank(attacker);
        vm.expectRevert(MORMEscrow.NotSeller.selector);
        esc.submitPackingProof(ORD, PACK);
    }

    function test_revert_open_before_pack() public {
        _registerOK();
        vm.prank(buyer);
        esc.createOrder{value: 1 ether}(ORD, CID, seller);
        vm.prank(buyer);
        vm.expectRevert(MORMEscrow.WrongStatus.selector);
        esc.submitOpeningProof(ORD, OPEN);
    }

    // -- Helpers ----------------------------------------------------------

    function _registerOK() internal {
        vm.prank(creator);
        esc.registerContent(CID, RH, GID);
    }
}
