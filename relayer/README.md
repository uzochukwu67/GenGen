# GenLayer Oracle Relayer (Node.js)

A Node.js implementation of the GenLayer Oracle Hub keeper/relayer that bridges AI-powered predictions between GenLayer and EVM chains.

## What It Does

1. **Monitors** the GenLayer Oracle Hub for pending markets past their deadline
2. **Triggers** resolution on GenLayer to start the AI jury process
3. **Polls** for resolved verdicts from the AI jury
4. **Delivers** verdicts back to EVM chains via OracleConsumer contracts
5. **Confirms** delivery completion on GenLayer

## Setup

### 1. Install Dependencies

```bash
cd relayer
npm install
```

### 2. Environment Variables

Create a `.env` file in the relayer directory:

```env
# GenLayer Configuration
GENLAYER_RPC=https://studio.genlayer.com
HUB_ADDRESS=0x5286D78605d6D255A2FfF4911cC57ef35692e461

# EVM Chain RPCs
EVM_RPC_POLYGON_AMOY=https://rpc-amoy.polygon.technology

# Relayer Wallet (must have gas on target chains)
RELAYER_PRIVATE_KEY=0x...

# Consumer Contract Addresses
CONSUMER_POLYGON=0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79

# Polling Configuration
POLL_INTERVAL_SECONDS=30
```

### 3. Register Chains

Before running the relayer, register the chains you want to monitor:

```bash
# Check current registrations
npm run check

# Register Polygon Amoy
npm run register
```

### 4. Run the Relayer

```bash
cd relayer
npm start
```

## Architecture

```
GenLayer Hub ──► Relayer ──► EVM Chains
     │              │            │
     ├─ Markets     ├─ Monitor   ├─ OracleConsumer
     ├─ Verdicts    ├─ Trigger   ├─ receiveVerdict()
     └─ Callbacks   └─ Deliver   └─ confirm_callback()
```

## Chain Registration Example

Before running the relayer, you need to register your EVM chains with the GenLayer Hub:

```javascript
const { GenLayerClient } = require('genlayer-js');

const gl = new GenLayerClient({
  endpoint: process.env.GENLAYER_RPC
});

// Register Polygon Amoy
await gl.sendTransaction(
  process.env.HUB_ADDRESS,
  'register_chain',
  {
    chain_key: 'polygon-amoy-v1',
    chain_type: 0,           // EVM
    adapter_type: 3,         // RELAYER
    adapter_address: process.env.CONSUMER_POLYGON,
    callback_url: 'https://your-keeper.example.com/verdict',
    metadata: JSON.stringify({
      chain_id: 80002,
      rpc_url: 'https://rpc-amoy.polygon.technology',
      contract: process.env.CONSUMER_POLYGON,
    }),
    fee_bps: 0,
  },
  { privateKey: process.env.RELAYER_PRIVATE_KEY, value: MIN_STAKE }
);
```

## Market Creation Example

Once chains are registered, create prediction markets:

```javascript
await gl.sendTransaction(
  process.env.HUB_ADDRESS,
  'create_market',
  {
    chain_key: 'polygon-amoy-v1',
    external_id: 'market-123',
    question: 'Will ETH exceed $5000 by end of 2024?',
    description: 'Binary prediction market on Ethereum price',
    resolution_criteria: 'YES if Coinbase spot ETH/USD ≥ $5,000 before deadline',
    evidence_urls: [
      'https://api.coinbase.com/v2/prices/ETH-USD/spot',
    ],
    deadline: 1735689600,  // Unix timestamp
    prize_pool_proxy: 10000,
  },
  { privateKey: process.env.RELAYER_PRIVATE_KEY, value: ORACLE_FEE }
);
```

## Production Considerations

- **Trustless Delivery**: Replace with LayerZero/Axelar for production
- **Monitoring**: Add health checks and alerting
- **Security**: Use hardware security modules for private keys
- **Scaling**: Run multiple relayer instances with leader election
- **Gas Management**: Implement gas price monitoring and optimization

## Troubleshooting

### Common Issues

1. **"Cannot find module 'genlayer-js'"**
   ```bash
   cd relayer
   npm install
   ```

2. **"Invalid private key"**
   - Ensure your private key starts with `0x`
   - Verify it has sufficient funds on target chains

3. **"Chain not connected"**
   - Check RPC URLs in `.env`
   - Verify network connectivity

4. **"Transaction reverted"**
   - Check contract addresses
   - Ensure relayer wallet has required permissions

### Logs

The relayer provides detailed console logging:
- `🚀` - Startup messages
- `📊` - Hub statistics
- `🎯` - Resolution triggers
- `📤` - Verdict deliveries
- `✅` - Successful operations
- `❌` - Errors
- `⚠️` - Warnings

## API Reference

### GenLayerClient Methods

- `call(contractAddress, method, params)` - Read-only calls
- `sendTransaction(contractAddress, method, params, options)` - State-changing calls

### Key Hub Methods

- `get_hub_stats()` - Get overall statistics
- `get_markets_for_chain(chain_key)` - Get markets for a chain
- `get_verdict(market_id)` - Get resolved verdict
- `trigger_resolution(market_id)` - Start AI resolution
- `confirm_callback(market_id)` - Confirm delivery

## License

MIT