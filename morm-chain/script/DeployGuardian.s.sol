// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import {GuardianMultisig} from "../src/GuardianMultisig.sol";
import {MORMExportBridge} from "../src/MORMExportBridge.sol";

/// Deploy a 2-of-3 GuardianMultisig (keys distinct from the bridge signer set),
/// hand the bridge's guardian role to it, then PROVE control by pausing and
/// unpausing the live bridge through the multisig (off-chain sigs, deployer relays).
contract DeployGuardian is Script {
    function _order2(uint256 pk1, uint256 pk2, bytes memory a, bytes memory b)
        internal pure returns (bytes[] memory out)
    {
        out = new bytes[](2);
        (out[0], out[1]) = vm.addr(pk1) < vm.addr(pk2) ? (a, b) : (b, a);
    }

    function _sign(GuardianMultisig ms, uint256 pk, address target, bytes memory data, uint256 n)
        internal view returns (bytes memory)
    {
        bytes32 d = ms.execDigest(target, data, n);
        bytes32 eth = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", d));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, eth);
        return abi.encodePacked(r, s, v);
    }

    function _twoSigs(GuardianMultisig ms, uint256 p1, uint256 p2, address target, bytes memory data, uint256 n)
        internal view returns (bytes[] memory)
    {
        return _order2(p1, p2,
            _sign(ms, p1, target, data, n),
            _sign(ms, p2, target, data, n));
    }

    function run() external {
        uint256 deployerPk = vm.envUint("DEPLOYER_PK");
        address bridge = vm.envAddress("BRIDGE_ADDR");
        uint256 gA = vm.envUint("GUARDIAN_A_PK");
        uint256 gB = vm.envUint("GUARDIAN_B_PK");
        uint256 gC = vm.envUint("GUARDIAN_C_PK");

        address[] memory gs = new address[](3);
        gs[0] = vm.addr(gA); gs[1] = vm.addr(gB); gs[2] = vm.addr(gC);

        // 1) deploy multisig + hand over guardian
        vm.startBroadcast(deployerPk);
        GuardianMultisig ms = new GuardianMultisig(gs, 2);
        MORMExportBridge(bridge).setGuardian(address(ms));
        vm.stopBroadcast();
        require(MORMExportBridge(bridge).guardian() == address(ms), "guardian not set");

        // 2) prove control: pause via multisig (nonce 0)
        bytes memory pauseData = abi.encodeWithSelector(MORMExportBridge.setPaused.selector, true);
        bytes[] memory s0 = _twoSigs(ms, gA, gB, bridge, pauseData, 0);
        vm.startBroadcast(deployerPk);
        ms.execute(bridge, pauseData, s0);
        vm.stopBroadcast();
        require(MORMExportBridge(bridge).paused(), "pause failed");

        // 3) unpause via multisig (nonce 1)
        bytes memory unpauseData = abi.encodeWithSelector(MORMExportBridge.setPaused.selector, false);
        bytes[] memory s1 = _twoSigs(ms, gA, gC, bridge, unpauseData, 1);
        vm.startBroadcast(deployerPk);
        ms.execute(bridge, unpauseData, s1);
        vm.stopBroadcast();
        require(!MORMExportBridge(bridge).paused(), "unpause failed");

        console2.log("GuardianMultisig:", address(ms));
        console2.log("bridge.guardian :", MORMExportBridge(bridge).guardian());
        console2.log("proved pause+unpause via multisig OK");
    }
}
