// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title MockUSDC — minimal ERC-20 for the bridge tests (6 decimals like USDC)
contract MockUSDC {
    string public constant name = "Mock USDC";
    string public constant symbol = "USDC";
    uint8  public constant decimals = 6;
    uint256 public totalSupply;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    error InsufficientBalance();
    error InsufficientAllowance();

    function mint(address to, uint256 amt) external {
        // PoC: anyone can mint — test fixture only
        balanceOf[to] += amt;
        totalSupply   += amt;
        emit Transfer(address(0), to, amt);
    }

    function transfer(address to, uint256 amt) external returns (bool) {
        _move(msg.sender, to, amt);
        return true;
    }

    function approve(address spender, uint256 amt) external returns (bool) {
        allowance[msg.sender][spender] = amt;
        emit Approval(msg.sender, spender, amt);
        return true;
    }

    function transferFrom(address from, address to, uint256 amt) external returns (bool) {
        uint256 cur = allowance[from][msg.sender];
        if (cur < amt) revert InsufficientAllowance();
        if (cur != type(uint256).max) allowance[from][msg.sender] = cur - amt;
        _move(from, to, amt);
        return true;
    }

    function _move(address from, address to, uint256 amt) internal {
        if (balanceOf[from] < amt) revert InsufficientBalance();
        unchecked { balanceOf[from] -= amt; }
        balanceOf[to] += amt;
        emit Transfer(from, to, amt);
    }
}
