// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {OracleConsumer} from "./OracleConsumer.sol";
import {Test} from "forge-std/Test.sol";

contract OracleConsumerTest is Test {
    OracleConsumer consumer;
    address owner = address(0x123);
    address relayer = address(0x456);

    function setUp() public {
        vm.prank(owner);
        consumer = new OracleConsumer(
            relayer,
            "polygon-amoy-v1",
            0.01 ether
        );
    }

    function test_Deployment() public view {
        assertEq(consumer.owner(), owner);
        assertEq(consumer.relayer(), relayer);
        assertEq(consumer.chainKey(), "polygon-amoy-v1");
        assertEq(consumer.oracleFee(), 0.01 ether);
    }

    function test_CreateMarket() public {
        string memory marketId = "test-market-1";
        string memory question = "Will ETH reach $5000 by end of 2024?";
        uint256 deadline = block.timestamp + 30 days;

        consumer.createMarket(marketId, question, deadline);

        (
            string memory q,
            uint8 state,
            uint8 outcome,
            uint256 yesPool,
            uint256 noPool,
            uint256 dl,
            uint256 confidence,
            bool verdictReceived
        ) = consumer.getMarket(marketId);

        require(keccak256(bytes(q)) == keccak256(bytes(question)), "Question should match");
        require(state == 0, "State should be PENDING");
        require(dl == deadline, "Deadline should match");
    }
}