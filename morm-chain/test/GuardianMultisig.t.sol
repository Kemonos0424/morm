// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {GuardianMultisig} from "../src/GuardianMultisig.sol";
import {WMORM} from "../src/WMORM.sol";
import {MORMExportBridge} from "../src/MORMExportBridge.sol";

contract GuardianMultisigTest is Test {
    GuardianMultisig ms;
    // three distinct guardian keys (separation of duties vs bridge signers)
    uint256 gkA = 0xA11CE; uint256 gkB = 0xB0B; uint256 gkC = 0xC0FFEE;
    address a; address b; address c;

    function setUp() public {
        a = vm.addr(gkA); b = vm.addr(gkB); c = vm.addr(gkC);
        address[] memory gs = _sorted3(a, b, c);
        ms = new GuardianMultisig(gs, 2);
    }

    function _sorted3(address x, address y, address z) internal pure returns (address[] memory arr) {
        arr = new address[](3); arr[0]=x; arr[1]=y; arr[2]=z;
        for (uint256 i; i<3; ++i) for (uint256 j=i+1; j<3; ++j)
            if (arr[j] < arr[i]) { address t=arr[i]; arr[i]=arr[j]; arr[j]=t; }
    }

    // sign the exec digest with a private key, EIP-191 prefixed
    function _sign(uint256 pk, address target, bytes memory data, uint256 n) internal view returns (bytes memory) {
        bytes32 d = ms.execDigest(target, data, n);
        bytes32 eth = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", d));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, eth);
        return abi.encodePacked(r, s, v);
    }

    // signatures must be ordered by signer address ascending
    function _two(uint256 pk1, uint256 pk2, address target, bytes memory data, uint256 n)
        internal view returns (bytes[] memory sigs)
    {
        address s1 = vm.addr(pk1); address s2 = vm.addr(pk2);
        sigs = new bytes[](2);
        if (s1 < s2) { sigs[0]=_sign(pk1,target,data,n); sigs[1]=_sign(pk2,target,data,n); }
        else         { sigs[0]=_sign(pk2,target,data,n); sigs[1]=_sign(pk1,target,data,n); }
    }

    function test_executes_with_quorum() public {
        Counter cnt = new Counter();
        bytes memory data = abi.encodeWithSelector(Counter.inc.selector);
        ms.execute(address(cnt), data, _two(gkA, gkB, address(cnt), data, 0));
        assertEq(cnt.n(), 1);
        assertEq(ms.nonce(), 1);
    }

    function test_reverts_below_threshold() public {
        Counter cnt = new Counter();
        bytes memory data = abi.encodeWithSelector(Counter.inc.selector);
        bytes[] memory one = new bytes[](1);
        one[0] = _sign(gkA, address(cnt), data, 0);
        vm.expectRevert(GuardianMultisig.NotEnoughSignatures.selector);
        ms.execute(address(cnt), data, one);
    }

    function test_replay_rejected_after_nonce_bump() public {
        Counter cnt = new Counter();
        bytes memory data = abi.encodeWithSelector(Counter.inc.selector);
        bytes[] memory sigs = _two(gkA, gkB, address(cnt), data, 0);
        ms.execute(address(cnt), data, sigs);            // consumes nonce 0
        vm.expectRevert(GuardianMultisig.BadSignature.selector); // same sigs now hash to nonce 1
        ms.execute(address(cnt), data, sigs);
    }

    function test_non_signer_rejected() public {
        Counter cnt = new Counter();
        bytes memory data = abi.encodeWithSelector(Counter.inc.selector);
        bytes[] memory sigs = _two(gkA, uint256(0xDEAD), address(cnt), data, 0); // 0xDEAD not a signer
        vm.expectRevert();
        ms.execute(address(cnt), data, sigs);
    }

    // end-to-end: multisig acts as the bridge guardian and can pause/unpause
    function test_multisig_as_bridge_guardian() public {
        WMORM w = new WMORM();
        address[] memory bs = _sorted3(vm.addr(1), vm.addr(2), vm.addr(3)); // bridge signers: distinct keys
        MORMExportBridge bridge = new MORMExportBridge(
            address(w), bs, 2, address(ms), 1 days, 1e24, 1e26, 0);
        w.setBridge(address(bridge));

        // multisig pauses the bridge
        bytes memory pauseData = abi.encodeWithSelector(MORMExportBridge.setPaused.selector, true);
        ms.execute(address(bridge), pauseData, _two(gkA, gkB, address(bridge), pauseData, 0));
        assertTrue(bridge.paused());

        // multisig unpauses
        bytes memory unpauseData = abi.encodeWithSelector(MORMExportBridge.setPaused.selector, false);
        ms.execute(address(bridge), unpauseData, _two(gkA, gkC, address(bridge), unpauseData, 1));
        assertFalse(bridge.paused());
    }
}

contract Counter {
    uint256 public n;
    function inc() external { n += 1; }
}
