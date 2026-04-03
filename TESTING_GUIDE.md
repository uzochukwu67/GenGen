# GenLayer AI Prediction Markets - Testing Guide

This guide shows how to test the complete AI-powered prediction market system using the frontend and relayer.

## 🏗️ System Architecture

```
Frontend (Next.js) → GenLayer Hub → AI Resolution → Relayer → EVM Consumer → Users
```

## 🚀 Quick Start

### 1. Start Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000

### 2. Start Relayer
```bash
cd relayer
python relayer_keeper.py
```

## 🧪 Testing Flow

### Step 1: Register Chain (Frontend)
1. Open http://localhost:3000
2. Connect MetaMask wallet
3. In "Oracle Manager" section:
   - Chain Key: `polygon-amoy-v1` (pre-filled)
   - Adapter Address: `0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79` (pre-filled)
   - Click "Register Chain"
4. Confirm transaction in MetaMask

### Step 2: Create Test Market (Frontend)
1. In "Oracle Manager" → "Create Market" tab:
   - External ID: `test-market-001`
   - Question: `Will ETH exceed $3000 by June 2025?`
   - Description: `Test market for AI resolution`
   - Resolution Criteria: `YES if ETH/USD >= $3000 on Coinbase`
   - Evidence URLs: `https://api.coinbase.com/v2/prices/ETH-USD/spot`
   - Deadline: Select future date (e.g., tomorrow)
   - Prize Pool Proxy: `1000`
   - Click "Create Market"

### Step 3: Place Bets (Frontend)
1. In "Prediction Markets" section:
   - Select a market
   - Click "Bet YES" or "Bet NO"
   - Enter bet amount (e.g., 0.01 ETH)
   - Click "Place Bet"
   - Confirm in MetaMask

### Step 4: Wait for Resolution
- Markets auto-resolve when deadline passes
- Relayer monitors and triggers AI resolution
- AI analyzes evidence and determines outcome

### Step 5: Claim Winnings
- After resolution, winners can claim proportional payouts
- Click "Claim Winnings" on resolved markets

## 🔍 Monitoring

### Frontend Dashboard
- **Hub Stats**: Total chains, markets, resolutions
- **Chains**: Registered blockchains and status
- **Markets**: Active markets with real-time status
- **Prediction Markets**: Place bets and claim winnings

### Relayer Logs
The relayer outputs:
```
INFO: Connected to polygon-amoy-v1: True
INFO: Hub: 1 chains, 2 markets, 0 resolved
INFO: Triggered resolution for test-market-001
INFO: Delivered verdict for test-market-001: outcome=YES conf=850
```

## 🧪 Test Scenarios

### Scenario 1: Simple YES/NO Market
- Create market: "Will it rain tomorrow in New York?"
- Evidence: Weather API
- AI analyzes weather data and decides

### Scenario 2: Numeric Threshold
- Create market: "Will BTC exceed $100k by year end?"
- Evidence: Price feeds
- AI checks final price vs threshold

### Scenario 3: Multiple Evidence Sources
- Create market: "Will election result be X?"
- Evidence: Multiple news APIs, official sources
- AI cross-references sources for consensus

## 🔧 Configuration

### Environment Variables (.env)
```bash
# GenLayer
NEXT_PUBLIC_GENLAYER_RPC_URL=https://studio.genlayer.com
NEXT_PUBLIC_HUB_ADDRESS=0x5286D78605d6D255A2FfF4911cC57ef35692e461

# Relayer
RELAYER_PRIVATE_KEY=your_private_key
EVM_RPC_POLYGON_AMOY=https://rpc-amoy.polygon.technology

# Consumer Contract
NEXT_PUBLIC_CONSUMER_POLYGON=0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79
```

### Chain Configuration
- **Network**: Polygon Amoy (Testnet)
- **Chain ID**: 80002
- **RPC**: https://rpc-amoy.polygon.technology
- **Contract**: 0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79

## 🐛 Troubleshooting

### Relayer Issues
- Check private key has Amoy testnet funds
- Verify .env variables are loaded
- Check GenLayer Studio connection

### Frontend Issues
- Clear browser cache
- Reconnect MetaMask
- Check MetaMask is on Polygon Amoy network

### Contract Issues
- Verify contract address is correct
- Check contract is deployed on Amoy
- Ensure sufficient gas for transactions

## 📊 Expected Results

After successful testing:
1. ✅ Chain registered on GenLayer Hub
2. ✅ Market created and visible in frontend
3. ✅ Bets placed successfully
4. ✅ AI resolution triggered automatically
5. ✅ Verdict delivered to EVM contract
6. ✅ Winners can claim proportional payouts

## 🎯 Next Steps

1. **Test on Mainnet**: Deploy to Polygon mainnet
2. **Add More Chains**: Register Ethereum, Base, etc.
3. **Real Markets**: Create actual prediction markets
4. **UI Improvements**: Enhanced market discovery and betting UX
5. **Analytics**: Market performance tracking

---

**Happy Testing! 🎉**

The system demonstrates how AI can power decentralized prediction markets with trustless resolution and automatic execution across multiple blockchains.