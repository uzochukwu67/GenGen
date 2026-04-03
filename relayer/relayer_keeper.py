"""
relayer_keeper.py  —  GenLayer Oracle Hub Keeper/Relayer
=========================================================

WHAT THIS DOES:
  1. Watches the GenLayer Oracle Hub for pending markets past their deadline
  2. Calls trigger_resolution() on GenLayer to start the AI jury
  3. Polls for resolved verdicts
  4. Posts verdicts back to EVM chains via OracleConsumer.receiveVerdict()
  5. Calls confirm_callback() on GenLayer to mark delivery complete

This is the "bridge" between GenLayer and EVM chains.
For production: replace with LayerZero/Axelar for trustless delivery.
For hackathon demo: this script + a testnet wallet is all you need.

SETUP:
  pip install genlayer web3 python-dotenv

ENV VARS (.env):
  GENLAYER_RPC=https://testnet.genlayer.com
  HUB_ADDRESS=0x...  (GenLayer hub contract address)
  EVM_RPC_ETH=https://mainnet.infura.io/v3/...
  EVM_RPC_POLYGON=https://polygon-rpc.com
  RELAYER_PRIVATE_KEY=0x...
  POLL_INTERVAL_SECONDS=30
"""

import os
import time
import json
import logging
from typing import Optional
from dataclasses import dataclass

# GenLayer SDK - Try different import methods
try:
    from genlayer import Client as GenLayerClient
    print("✅ Using: from genlayer import Client")
except ImportError:
    try:
        from genlayer.client import Client as GenLayerClient
        print("✅ Using: from genlayer.client import Client")
    except ImportError:
        try:
            from genlayer import GenLayerClient
            print("✅ Using: from genlayer import GenLayerClient")
        except ImportError:
            try:
                import genlayer as gl
                GenLayerClient = gl.Client
                print("✅ Using: genlayer.Client")
            except AttributeError:
                try:
                    GenLayerClient = gl.GenLayerClient
                    print("✅ Using: genlayer.GenLayerClient")
                except AttributeError:
                    print("❌ Available in genlayer package:")
                    print([x for x in dir(gl) if not x.startswith('_')])
                    raise ImportError("Could not find GenLayer client class")

# Web3 for EVM callbacks
from web3 import Web3
from web3.middleware import geth_poa_middleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("relayer")


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

GENLAYER_RPC   = os.getenv("GENLAYER_RPC", "https://studio.genlayer.com")
HUB_ADDRESS    = os.getenv("HUB_ADDRESS", os.getenv("ORACLE_HUB_CONTRACT_ADDRESS", ""))
PRIVATE_KEY    = os.getenv("RELAYER_PRIVATE_KEY", "")
POLL_INTERVAL  = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

# EVM chain configs: chain_key → {rpc, consumer_address}
EVM_CHAINS = {
    "polygon-amoy-v1": {
        "rpc": os.getenv("EVM_RPC_POLYGON_AMOY", "https://rpc-amoy.polygon.technology"),
        "consumer": os.getenv("CONSUMER_POLYGON", ""),
        "chain_id": 80002,
        "poa": False,
    },
    "ethereum-mainnet": {
        "rpc": os.getenv("EVM_RPC_ETH", ""),
        "consumer": os.getenv("CONSUMER_ETH", ""),
        "chain_id": 1,
        "poa": False,
    },
    "base-mainnet": {
        "rpc": os.getenv("EVM_RPC_BASE", ""),
        "consumer": os.getenv("CONSUMER_BASE", ""),
        "chain_id": 8453,
        "poa": False,
    },
}

# OracleConsumer ABI (just the functions we need)
CONSUMER_ABI = [
    {
        "inputs": [
            {"name": "marketId",  "type": "string"},
            {"name": "outcome",   "type": "uint8"},
            {"name": "confidence","type": "uint256"},
            {"name": "reasoning", "type": "string"},
        ],
        "name": "receiveVerdict",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "marketId","type": "string"}],
        "name": "getMarket",
        "outputs": [
            {"name": "question",         "type": "string"},
            {"name": "state",            "type": "uint8"},
            {"name": "outcome",          "type": "uint8"},
            {"name": "yesPool",          "type": "uint256"},
            {"name": "noPool",           "type": "uint256"},
            {"name": "deadline",         "type": "uint256"},
            {"name": "confidence",       "type": "uint256"},
            {"name": "verdictReceived",  "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


# ─────────────────────────────────────────────
# Core keeper logic
# ─────────────────────────────────────────────

class OracleKeeper:
    """
    Watches GenLayer Hub and delivers verdicts to source chains.
    """

    def __init__(self):
        self.gl     = GenLayerClient(endpoint=GENLAYER_RPC)
        self.w3s    = {}  # chain_key → Web3 instance
        self.processed: set = set()  # market_ids already delivered

        # Bootstrap Web3 connections for each known EVM chain
        for chain_key, cfg in EVM_CHAINS.items():
            if not cfg["rpc"] or not cfg["consumer"]:
                continue
            w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
            if cfg["poa"]:
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            self.w3s[chain_key] = w3
            log.info(f"Connected to {chain_key}: {w3.is_connected()}")

    def run(self):
        log.info("Relayer keeper started.")
        while True:
            try:
                self._tick()
            except Exception as e:
                log.error(f"Tick error: {e}")
            time.sleep(POLL_INTERVAL)

    def _tick(self):
        # 1. Get all registered chains from the hub
        hub_stats = self._hub_call("get_hub_stats")
        log.info(f"Hub: {hub_stats.get('total_chains')} chains, "
                 f"{hub_stats.get('total_markets')} markets, "
                 f"{hub_stats.get('total_resolved')} resolved")

        # 2. For each chain, check pending markets
        for chain_key in EVM_CHAINS.keys():
            self._process_chain(chain_key)

    def _process_chain(self, chain_key: str):
        markets = self._hub_call("get_markets_for_chain", chain_key=chain_key)
        if not markets:
            return

        for m in markets:
            mid   = m["market_id"]
            state = m["state"]

            if mid in self.processed:
                continue

            if state == "PENDING":
                # Try to trigger resolution (hub will reject if deadline not met)
                try:
                    result = self._hub_write("trigger_resolution", market_id=mid)
                    log.info(f"Triggered resolution for {mid}: {result}")
                except Exception as e:
                    log.debug(f"Cannot trigger {mid} yet: {e}")

            elif state == "RESOLVED":
                # Read verdict and post to source chain
                verdict = self._hub_call("get_verdict", market_id=mid)
                if verdict and not verdict.get("callback_posted"):
                    self._deliver_verdict(chain_key, verdict)

    def _deliver_verdict(self, chain_key: str, verdict: dict):
        mid        = verdict["market_id"]
        external_id = verdict["external_id"]
        outcome_int = verdict["outcome_int"]  # 1=YES, 2=NO, 3=INVALID
        confidence  = int(verdict["confidence"] * 1000)  # scale to 0-1000
        reasoning   = verdict["reasoning"][:500]

        log.info(f"Delivering verdict for {mid}: outcome={verdict['outcome']} conf={confidence}")

        # Post to EVM chain
        delivered = self._post_to_evm(chain_key, mid, outcome_int, confidence, reasoning)

        if delivered:
            # Confirm delivery on GenLayer
            try:
                self._hub_write("confirm_callback", market_id=mid)
                self.processed.add(mid)
                log.info(f"Verdict delivered and confirmed: {mid}")
            except Exception as e:
                log.error(f"Failed to confirm callback for {mid}: {e}")
        else:
            log.warning(f"Failed to deliver verdict for {mid} to {chain_key}")

    def _post_to_evm(self, chain_key: str, market_id: str,
                     outcome: int, confidence: int, reasoning: str) -> bool:
        if chain_key not in self.w3s:
            log.warning(f"No Web3 connection for {chain_key}")
            return self._post_via_http_callback(chain_key, market_id, outcome, confidence, reasoning)

        cfg = EVM_CHAINS[chain_key]
        w3  = self.w3s[chain_key]

        try:
            consumer = w3.eth.contract(
                address=Web3.to_checksum_address(cfg["consumer"]),
                abi=CONSUMER_ABI
            )

            account  = w3.eth.account.from_key(PRIVATE_KEY)
            nonce    = w3.eth.get_transaction_count(account.address)
            gas_price = w3.eth.gas_price

            tx = consumer.functions.receiveVerdict(
                market_id, outcome, confidence, reasoning
            ).build_transaction({
                "from":     account.address,
                "nonce":    nonce,
                "gas":      200000,
                "gasPrice": gas_price,
                "chainId":  cfg["chain_id"],
            })

            signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                log.info(f"EVM callback tx: {tx_hash.hex()} on {chain_key}")
                return True
            else:
                log.error(f"EVM tx failed: {tx_hash.hex()}")
                return False

        except Exception as e:
            log.error(f"EVM post error for {chain_key}: {e}")
            return False

    def _post_via_http_callback(self, chain_key: str, market_id: str,
                                 outcome: int, confidence: int, reasoning: str) -> bool:
        """
        Fallback for RELAYER adapter type: POST verdict to callback_url.
        The receiving server is responsible for posting to the chain.
        """
        try:
            import urllib.request
            chain = self._hub_call("get_chain", chain_key=chain_key)
            if not chain or not chain.get("callback_url"):
                return False

            payload = json.dumps({
                "market_id":  market_id,
                "outcome":    outcome,
                "confidence": confidence,
                "reasoning":  reasoning,
            }).encode("utf-8")

            req = urllib.request.Request(
                chain["callback_url"],
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status == 200
        except Exception as e:
            log.error(f"HTTP callback error: {e}")
            return False

    # ── GenLayer SDK helpers ──────────────────────────────────────────

    def _hub_call(self, method: str, **kwargs) -> dict:
        """Read-only call to GenLayer Hub."""
        return self.gl.call(HUB_ADDRESS, method, kwargs)

    def _hub_write(self, method: str, **kwargs) -> dict:
        """State-changing call to GenLayer Hub."""
        return self.gl.send_transaction(
            HUB_ADDRESS, method, kwargs,
            private_key=PRIVATE_KEY,
        )


# ─────────────────────────────────────────────
# Example: how a chain registers and creates a market
# (run this once to set up; keeper handles the rest)
# ─────────────────────────────────────────────

EXAMPLE_REGISTRATION = """
Example — register Polygon Amoy with the hub:

gl = GenLayerClient(endpoint=GENLAYER_RPC)

# 1. Register
gl.send_transaction(HUB_ADDRESS, "register_chain", {
    "chain_key":       "polygon-amoy-v1",
    "chain_type":      0,           # EVM
    "adapter_type":    3,           # RELAYER (keeper script)
    "adapter_address": "0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79",
    "callback_url":    "https://your-keeper.example.com/verdict",
    "metadata": json.dumps({
        "chain_id": 80002,
        "rpc_url": "https://rpc-amoy.polygon.technology",
        "contract": "0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79",
        "market_api_url": "https://testnet.gamma-api.polymarket.com/markets",
    }),
    "fee_bps": 0,  # use global rate
}, private_key=YOUR_KEY, value=MIN_STAKE)

# 2. Create a market
gl.send_transaction(HUB_ADDRESS, "create_market", {
    "chain_key":           "polygon-amoy-v1",
    "external_id":         "0xabc123",      # Test market ID
    "question":            "Will ETH exceed $5000 by end of 2024?",
    "description":         "Binary prediction market on Ethereum price",
    "resolution_criteria": "YES if Coinbase spot ETH/USD ≥ $5,000 at any point before deadline. NO otherwise.",
    "evidence_urls": [
        "https://api.coinbase.com/v2/prices/ETH-USD/spot",
        "https://testnet.gamma-api.polymarket.com/markets?condition_id=0xabc123",
    ],
    "deadline":          1735689600,  # unix timestamp
    "prize_pool_proxy":  10000,       # $10k test pool
}, private_key=YOUR_KEY, value=ORACLE_FEE)

# Keeper picks it up and does the rest automatically.
"""

if __name__ == "__main__":
    keeper = OracleKeeper()
    keeper.run()