// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title WMORM — Wrapped MORM, the EVM-side tradable representation of L1 MORM.
/// @notice Minimal, dependency-free ERC-20. Mint/burn are restricted to the
///         bridge, so total wMORM supply on this chain mirrors the amount of
///         MORM burned-for-export on the L1 (1:1 in base units — the relayer
///         fixes the scaling). This token is what a Uniswap wMORM/USDC pool
///         quotes, so DexScreener/GeckoTerminal give a real MORM/USD chart.
///
///         Testnet-first note: hand-rolled to match this repo's zero-dependency
///         style and stay auditable. Before mainnet, swap for an audited
///         OpenZeppelin ERC-20 (+ ERC-2612 permit) and run a full audit.
contract WMORM {
    string public constant name = "Wrapped MORM";
    string public constant symbol = "wMORM";
    uint8 public constant decimals = 18;

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    address public bridge;             // only minter/burner (set once, post-deploy)
    address public immutable deployer; // may wire the bridge exactly once

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event BridgeSet(address indexed bridge);

    error NotBridge();
    error NotDeployer();
    error BridgeAlreadySet();
    error ZeroAddress();
    error InsufficientBalance();
    error InsufficientAllowance();

    modifier onlyBridge() {
        if (msg.sender != bridge) revert NotBridge();
        _;
    }

    constructor() {
        deployer = msg.sender;
    }

    /// @notice Wire the bridge exactly once (deploy WMORM, deploy bridge with
    ///         this token's address, then call setBridge(bridge)). After this
    ///         the deployer has no minting power — only the bridge does.
    function setBridge(address _bridge) external {
        if (msg.sender != deployer) revert NotDeployer();
        if (bridge != address(0)) revert BridgeAlreadySet();
        if (_bridge == address(0)) revert ZeroAddress();
        bridge = _bridge;
        emit BridgeSet(_bridge);
    }

    // --- ERC-20 ---
    function transfer(address to, uint256 value) external returns (bool) {
        return _transfer(msg.sender, to, value);
    }

    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        if (a < value) revert InsufficientAllowance();
        if (a != type(uint256).max) allowance[from][msg.sender] = a - value;
        return _transfer(from, to, value);
    }

    function _transfer(address from, address to, uint256 value) internal returns (bool) {
        if (to == address(0)) revert ZeroAddress();
        uint256 b = balanceOf[from];
        if (b < value) revert InsufficientBalance();
        unchecked {
            balanceOf[from] = b - value;
            balanceOf[to] += value;
        }
        emit Transfer(from, to, value);
        return true;
    }

    // --- bridge-only mint/burn (supply == L1 exported MORM) ---
    function mint(address to, uint256 value) external onlyBridge {
        if (to == address(0)) revert ZeroAddress();
        totalSupply += value;
        unchecked { balanceOf[to] += value; }
        emit Transfer(address(0), to, value);
    }

    /// @notice Burn `value` from `from`. Only the bridge calls this, and only
    ///         from exit() where `from == the exiting user`, so no third party
    ///         can burn someone else's balance.
    function burn(address from, uint256 value) external onlyBridge {
        uint256 b = balanceOf[from];
        if (b < value) revert InsufficientBalance();
        unchecked {
            balanceOf[from] = b - value;
            totalSupply -= value;
        }
        emit Transfer(from, address(0), value);
    }
}
