#!/usr/bin/env python3

"""
test_relayer.py — Test the Oracle Relayer/Keeper
===============================================

Tests the relayer keeper functionality without actually sending transactions.

Usage:
  python test_relayer.py

Requirements:
  pip install genlayer python-dotenv
"""

import os
import json
import logging
from unittest.mock import Mock, patch
from relayer_keeper import OracleKeeper

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("test_relayer")

def test_relayer_initialization():
    """Test that the relayer initializes correctly."""
    print("🧪 Testing relayer initialization...")

    # Mock the GenLayer client
    with patch('relayer_keeper.GenLayerClient') as mock_client:
        mock_gl = Mock()
        mock_client.return_value = mock_gl

        # Mock Web3 connections
        with patch('relayer_keeper.Web3') as mock_web3:
            mock_w3 = Mock()
            mock_w3.is_connected.return_value = True
            mock_web3.return_value = mock_w3

            relayer = OracleKeeper()

            # Check that GenLayer client was created
            mock_client.assert_called_once()
            assert relayer.gl == mock_gl
            print("✅ Relayer initialization successful")

def test_hub_call():
    """Test calling hub methods."""
    print("🧪 Testing hub calls...")

    with patch('relayer_keeper.GenLayerClient') as mock_client:
        mock_gl = Mock()
        mock_gl.call.return_value = {"total_chains": 1, "total_markets": 5}
        mock_client.return_value = mock_gl

        with patch('relayer_keeper.Web3'):
            relayer = OracleKeeper()

            result = relayer._hub_call("get_hub_stats")
            assert result["total_chains"] == 1
            assert result["total_markets"] == 5

            mock_gl.call.assert_called_with(
                os.getenv("HUB_ADDRESS", ""),
                "get_hub_stats",
                {}
            )
            print("✅ Hub calls working")

def test_process_chain():
    """Test processing a chain for pending markets."""
    print("🧪 Testing chain processing...")

    with patch('relayer_keeper.GenLayerClient') as mock_client:
        mock_gl = Mock()
        mock_gl.call.side_effect = [
            # get_markets_for_chain response
            [
                {
                    "market_id": "polygon-test-1",
                    "state": "PENDING",
                    "external_id": "0x123",
                    "question": "Test question?",
                    "outcome": "UNRESOLVED"
                }
            ],
            # get_verdict response (when resolved)
            {
                "market_id": "polygon-test-1",
                "outcome": "YES",
                "outcome_int": 1,
                "confidence": 0.95,
                "reasoning": "Test reasoning",
                "callback_posted": False
            }
        ]
        mock_client.return_value = mock_gl

        with patch('relayer_keeper.Web3'):
            relayer = OracleKeeper()

            # Test with pending market
            relayer._process_chain("polygon-polymarket-v1")

            # Should have called get_markets_for_chain
            assert mock_gl.call.call_count >= 1
            print("✅ Chain processing working")

def test_verdict_delivery():
    """Test delivering verdicts to EVM chains."""
    print("🧪 Testing verdict delivery...")

    with patch('relayer_keeper.GenLayerClient') as mock_client:
        mock_gl = Mock()
        mock_client.return_value = mock_gl

        with patch('relayer_keeper.Web3') as mock_web3:
            mock_w3 = Mock()
            mock_w3.is_connected.return_value = True
            mock_w3.eth.contract.return_value.functions.receiveVerdict.return_value.build_transaction.return_value = {
                "from": "0x123",
                "nonce": 1,
                "gas": 200000,
                "gasPrice": 20000000000,
                "chainId": 137
            }
            mock_w3.eth.account.from_key.return_value.address = "0x123"
            mock_w3.eth.get_transaction_count.return_value = 1
            mock_w3.eth.gas_price = 20000000000
            mock_w3.eth.send_raw_transaction.return_value = b"0x" + b"00" * 32
            mock_w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}

            mock_web3.return_value = mock_w3

            relayer = OracleKeeper()

            verdict = {
                "market_id": "polygon-test-1",
                "outcome": "YES",
                "outcome_int": 1,
                "confidence": 0.95,
                "reasoning": "Test reasoning"
            }

            # Test EVM delivery
            result = relayer._post_to_evm("polygon-polymarket-v1", "polygon-test-1", 1, 950, "Test")
            assert result == True
            print("✅ EVM verdict delivery working")

def run_all_tests():
    """Run all tests."""
    print("🚀 Running Oracle Relayer Tests\n")

    try:
        test_relayer_initialization()
        test_hub_call()
        test_process_chain()
        test_verdict_delivery()

        print("\n✅ All tests passed! Relayer is ready for deployment.")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False

    return True

if __name__ == "__main__":
    run_all_tests()