# Oracle Consumer & Relayer Keeper Setup

This guide explains how to deploy and configure the Oracle Consumer contracts and Relayer Keeper for the GenLayer Oracle Hub.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Prediction     │    │  GenLayer Hub   │    │  Relayer        │
│  Markets        │◄──►│  (AI Oracle)    │◄──►│  Keeper         │
│  (EVM Chains)   │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲                       │
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────┐
                    │  Oracle Consumer│
                    │  Contracts      │
                    └─────────────────┘
```

## 1. Deploy Oracle Hub

The Oracle Hub is already deployed at: `0x5286D78605d6D255A2FfF4911cC57ef35692e461`

## 2. Deploy Oracle Consumer Contracts

### Prerequisites
```bash
npm install ethers dotenv
```

### Deploy to Polygon (Example)
```bash
# Set your private key in .env
echo "RELAYER_PRIVATE_KEY=0xyour_private_key_here" >> .env

# Deploy Oracle Consumer to Polygon
node deploy/deploy-consumer.js \
  --network polygon \
  --relayer 0xYourRelayerAddress \
  --chain-key polygon-polymarket-v1 \
  --oracle-fee 10000000000000000  # 0.01 ETH
```

### Deploy to Other Networks
```bash
# Ethereum Mainnet
node deploy/deploy-consumer.js \
  --network ethereum \
  --relayer 0xYourRelayerAddress \
  --chain-key ethereum-uniswap-v1 \
  --oracle-fee 100000000000000000  # 0.1 ETH

# Base
node deploy/deploy-consumer.js \
  --network base \
  --relayer 0xYourRelayerAddress \
  --chain-key base-perp-v1 \
  --oracle-fee 10000000000000000   # 0.01 ETH
```

### Update .env with Deployed Addresses
After deployment, update your `.env` file:
```bash
CONSUMER_POLYGON=0xDeployedAddressHere
CONSUMER_ETH=0xDeployedAddressHere
CONSUMER_BASE=0xDeployedAddressHere
```

## 3. Register Chains with Oracle Hub

Before prediction markets can use the oracle, they need to register with the hub:

```python
from genlayer import Client as GenLayerClient
import json

gl = GenLayerClient(endpoint="https://studio.genlayer.com")

# Register Polygon Polymarket
gl.send_transaction("0x5286D78605d6D255A2FfF4911cC57ef35692e461", "register_chain", {
    "chain_key": "polygon-polymarket-v1",
    "chain_type": 0,  # EVM
    "adapter_type": 3,  # RELAYER
    "adapter_address": "0xYourConsumerContractAddress",
    "callback_url": "https://your-relayer.example.com/callback",
    "metadata": json.dumps({
        "chain_id": 137,
        "rpc_url": "https://polygon-rpc.com",
        "contract": "0xYourConsumerContractAddress",
        "market_api_url": "https://gamma-api.polymarket.com/markets"
    }),
    "fee_bps": 0  # Use global rate
}, private_key="YOUR_PRIVATE_KEY", value=10**18)  # 1 GLN stake
```

## 4. Configure and Run Relayer Keeper

### Install Dependencies
```bash
pip install genlayer web3 python-dotenv
```

### Configure Environment
Update your `.env` file with:
```bash
# GenLayer
GENLAYER_RPC=https://studio.genlayer.com
HUB_ADDRESS=0x5286D78605d6D255A2FfF4911cC57ef35692e461
RELAYER_PRIVATE_KEY=0xyour_private_key_here

# EVM RPCs
EVM_RPC_POLYGON=https://polygon-rpc.com
EVM_RPC_ETH=https://mainnet.infura.io/v3/YOUR_INFURA_KEY
EVM_RPC_BASE=https://mainnet.base.org

# Consumer Contracts
CONSUMER_POLYGON=0xDeployedConsumerAddress
CONSUMER_ETH=0xDeployedConsumerAddress
CONSUMER_BASE=0xDeployedConsumerAddress

# Polling interval
POLL_INTERVAL_SECONDS=30
```

### Test the Relayer
```bash
cd /workspaces/GenGen
python test/test_relayer.py
```

### Run the Relayer
```bash
python contracts/relayer_keeper.py
```

The relayer will:
1. Monitor the Oracle Hub for pending markets
2. Trigger AI resolution when deadlines are reached
3. Deliver verdicts back to EVM chains
4. Confirm delivery on GenLayer

## 5. Integration with Prediction Markets

### For Polymarket Integration
```solidity
// In your prediction market contract
import "./OracleConsumer.sol";

contract PolymarketOracle is OracleConsumer {
    // Your market logic here

    function resolveMarket(string memory marketId) external {
        // Call createMarket on OracleConsumer
        // Relayer handles the rest automatically
    }
}
```

### Manual Market Creation
```javascript
// Using ethers.js
const consumer = new ethers.Contract(consumerAddress, consumerABI, signer);

await consumer.createMarket(
    "Will ETH exceed $5000 by Dec 31?",
    "YES if ETH/USD >= 5000 on Coinbase. NO otherwise.",
    Math.floor(Date.now() / 1000) + 86400 * 30, // 30 days
    { value: ethers.parseEther("0.01") } // Oracle fee
);
```

## 6. Monitoring and Maintenance

### Check Relayer Logs
The relayer outputs structured logs. Monitor for:
- Market creation events
- Resolution triggers
- Verdict deliveries
- Transaction failures

### Health Checks
```bash
# Check if relayer is running
ps aux | grep relayer_keeper

# Check hub stats
curl -X POST https://studio.genlayer.com/call \
  -H "Content-Type: application/json" \
  -d '{"address": "0x5286D78605d6D255A2FfF4911cC57ef35692e461", "method": "get_hub_stats"}'
```

### Troubleshooting

**Relayer not delivering verdicts:**
- Check EVM RPC connectivity
- Verify consumer contract addresses
- Ensure sufficient gas balance

**Markets not resolving:**
- Check market deadlines
- Verify chain registration
- Monitor relayer logs

**Transaction failures:**
- Check private key balance
- Verify network configurations
- Review gas limits

## 7. Production Deployment

For production:
1. Use dedicated relayer infrastructure (AWS Lambda, Railway, etc.)
2. Implement monitoring and alerting
3. Set up multiple relayer instances for redundancy
4. Use hardware security modules for private keys
5. Implement rate limiting and error handling

## Support

- Oracle Hub Address: `0x5286D78605d6D255A2FfF4911cC57ef35692e461`
- Test on GenLayer Studio: https://studio.genlayer.com
- Documentation: Check CLAUDE.md for detailed API reference