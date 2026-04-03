# GenLayer Oracle Hub — Universal Cross-Chain Prediction Market Oracle
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/license/mit/)
[![Discord](https://img.shields.io/badge/Discord-Join%20us-5865F2?logo=discord&logoColor=white)](https://discord.gg/8Jm4v89VAu)
[![Telegram](https://img.shields.io/badge/Telegram--T.svg?style=social&logo=telegram)](https://t.me/genlayer)
[![Twitter](https://img.shields.io/twitter/url/https/twitter.com/yeagerai.svg?style=social&label=Follow%20%40GenLayer)](https://x.com/GenLayer)
[![GitHub star chart](https://img.shields.io/github/stars/yeagerai/genlayer-project-boilerplate?style=social)](https://star-history.com/#yeagerai/genlayer-js)

## 🎯 Vision: B2B Infrastructure for Prediction Markets

**The Oracle Hub is not competing with prediction markets — it's becoming their universal resolution layer.**

Instead of building another prediction market, we've created the infrastructure that ALL prediction markets can use. Any blockchain app can register with the hub and get instant access to:
- AI-powered resolution using Optimistic Democracy
- Cross-chain verdict delivery via adapters/relayers
- Governance-protected fee structures
- Precedent-based learning for improved accuracy

## 🏗️ Architecture Overview

### Core Components
1. **Chain Registry** — Any blockchain app registers with stake
2. **Market Factory** — Registered chains create markets for AI resolution
3. **AI Resolution Engine** — Optimistic Democracy with precedent memory
4. **Governance DAO** — GLN token holders control parameters
5. **Cross-Chain Adapters** — Verdict delivery to source chains

### Key Features
- **Multi-Chain Support**: EVM, Solana, Cosmos, and custom chains
- **AI Consensus**: Equivalence Principle validation with precedent learning
- **Governance**: Timelocked proposals for fee rates, chain approvals, parameters
- **Economic Model**: Fee-based revenue from prize pools
- **Security**: Staking, slashing, and dispute resolution

## 📦 What's Included

### Contracts
- `contracts/oracle_hub.py` — Complete Oracle Hub implementation
- `contracts/football.py` — Multi-market decentralized oracle (hackathon entry)
- `contracts/football_bets.py` — Reference template

### Tests
- `test/test_oracle_hub.py` — Comprehensive Oracle Hub test suite
- `test/test_decentralized_oracle.py` — Multi-market functionality tests

### Frontend
- Next.js 15 app with TypeScript, TanStack Query, Radix UI
- Wallet integration (MetaMask)
- Contract interaction hooks

## 🛠️ Requirements
- GenLayer Studio running (local or [hosted](https://studio.genlayer.com/))
- [GenLayer CLI](https://github.com/genlayerlabs/genlayer-cli) installed
- Node.js 18+ and Python 3.8+

## 🚀 Quick Start

### 1. Deploy Oracle Hub Contract
```bash
genlayer network  # Select network (studionet/localnet/testnet)
genlayer deploy   # Deploys oracle_hub.py
```

### 2. Register Your Chain
Any prediction market can register:
```python
# Example: Polymarket registers
contract.register_chain(
    chain_key="polygon-polymarket-v2",
    chain_type=0,  # EVM
    adapter_type=3,  # RELAYER
    adapter_address="0x...",
    callback_url="https://api.polymarket.com/callback",
    metadata='{"chain_id": 137, "contract": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"}',
    fee_bps=200,  # 2% fee
    value=10**19  # 10 ETH stake
)
```

### 3. Create Markets
```python
contract.create_market(
    chain_key="polygon-polymarket-v2",
    external_id="bitcoin-100k-2024",
    question="Will Bitcoin reach $100,000 by end of 2024?",
    description="Bitcoin price prediction",
    resolution_criteria="YES if BTC > $100k on Dec 31, 2024 UTC",
    evidence_urls=["https://coinmarketcap.com/currencies/bitcoin/"],
    deadline=1735689600,  # Dec 31, 2024
    prize_pool_proxy=10**21  # $1000 worth
)
```

### 4. AI Resolution
The hub automatically:
1. Waits for deadline
2. Dispatches AI jury using Optimistic Democracy
3. Validates consensus with Equivalence Principle
4. Stores precedent for future learning
5. Delivers verdict via relayer to source chain

### 5. Setup Frontend
```bash
cd frontend
cp .env.example .env
# Add NEXT_PUBLIC_CONTRACT_ADDRESS from deployment
bun install && bun dev
```

### 6. Run the Relayer (Node.js)
```bash
cd relayer
cp .env.example .env
# Configure your RPC URLs and private key
npm install && npm start
```

## 🎮 How It Works

### For Prediction Market Operators
1. **Register Once** — Stake GLN tokens, configure adapter
2. **Create Markets** — Call `create_market()` for each prediction
3. **Get Verdicts** — Hub resolves via AI and delivers results
4. **Pay Fees** — Only when markets resolve (percentage of prize pool)

### For Users
- Bet on any market that uses Oracle Hub
- Resolution happens automatically via AI
- No need to trust centralized oracles

### For Governance Participants
- Hold GLN tokens to vote on:
  - Fee rates per chain
  - New chain approvals
  - Parameter changes (quorum, timelock)
  - Emergency pauses

## 🔧 Technical Details

### AI Resolution Process
1. **Leader Function**: GPT-4 analyzes evidence + precedents
2. **Validator Function**: Independent verification
3. **Consensus Check**: Equivalence Principle validation
4. **Extended Validation**: For ambiguous cases
5. **Precedent Storage**: Vector embeddings for semantic search

### Storage Architecture
- **Flattened Design**: Separate TreeMaps for scalability
- **Precedent Memory**: VectorStore for semantic similarity
- **Governance State**: Proposal tracking with timelocks

### Cross-Chain Integration
- **Adapters**: LayerZero, Wormhole, Axelar, or custom relayers
- **Callbacks**: HTTP endpoints or smart contract calls
- **Live Data**: Fetches market sentiment during resolution

### Relayer Implementation
The Node.js relayer (`relayer/relayer-keeper.js`) provides:
- **Monitoring**: Polls GenLayer Hub for pending markets
- **Triggering**: Initiates AI resolution when deadlines are met
- **Delivery**: Posts verdicts to EVM chains via OracleConsumer contracts
- **Confirmation**: Marks delivery complete on GenLayer
- **Fallback**: HTTP callback support for non-EVM chains

## 🧪 Testing

Run the test suite:
```bash
gltest test/test_oracle_hub.py
```

Test coverage includes:
- Chain registration and staking
- Market creation with fee calculation
- AI resolution with consensus validation
- Governance proposals and voting
- Precedent learning and search

## 📊 Business Model

### Revenue Streams
- **Resolution Fees**: 0.5-2% of prize pools
- **Staking Rewards**: Redistribute slashed stakes
- **Governance Fees**: Optional proposal deposits

### Value Proposition
- **For Markets**: Cheaper than maintaining custom oracles
- **For Users**: Trust-minimized, AI-powered resolution
- **For Ecosystem**: Universal standard for prediction markets

## 🎯 Hackathon Strategy

This implementation addresses the GenLayer Bradbury hackathon by:
- **AI-Native**: Core functionality uses LLM consensus
- **Cross-Chain**: Supports multiple blockchain ecosystems
- **Decentralized**: Governance-controlled parameters
- **Scalable**: Flattened storage for unlimited markets
- **Production-Ready**: Complete test suite and documentation

## 🤝 Contributing

The Oracle Hub is designed to be the foundation for the entire prediction market ecosystem. Future enhancements:
- Additional chain adapters
- Advanced precedent weighting
- Multi-round dispute resolution
- Integration with major prediction markets

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Built with ❤️ for the GenLayer ecosystem**

   The terminal should display a link to access your frontend app (usually at <http://localhost:3000/>).
   For more information on the code see [GenLayerJS](https://github.com/yeagerai/genlayer-js).
   
### 5. Test contracts
1. Install the Python packages listed in the `requirements.txt` file in a virtual environment.
2. Make sure your GenLayer Studio is running. Then execute the following command in your terminal:
   ```shell
   gltest
   ```

## 🧠 How the Decentralized Oracle Contract Works

The Decentralized Oracle contract implements an AI-powered prediction market with advanced consensus mechanisms. Here's a breakdown of its main functionalities:

1. **Multi-Market Support**:
   - Single contract can host multiple independent prediction markets
   - Each market has its own state, bets, and resolution process
   - Markets are identified by unique string IDs

2. **Market Creation**:
   - Deployers can create prediction markets with questions, evidence URLs, and economic parameters
   - Supports both native markets and cross-chain resolution requests

3. **AI-Powered Resolution**:
   - Uses Equivalence Principle for robust consensus validation
   - Multiple LLM validators ensure outcome reliability
   - Simple precedent database for learning from past resolutions

4. **Betting & Economics**:
   - Users can place YES/NO bets with configurable minimum stakes
   - Winner-takes-all payout system with proportional distribution
   - Oracle fees fund cross-chain resolution services

5. **Cross-Chain Integration**:
   - Supports Polymarket, Azuro, and custom chain resolution requests
   - Relayers can submit external market verdicts for GenLayer validation

6. **Advanced Features**:
   - Resolver reputation system tracks validator accuracy
   - Web evidence caching with retry logic and screenshot fallbacks
   - Precedent database for learning from past resolutions
   - Users can check their total points or the points of any player.

## 🧪 Tests

This project includes integration tests that interact with the contract deployed in the Studio. These tests cover the main functionalities of the Football Bets contract:

1. Creating a bet
2. Resolving a bet
3. Querying bets for a player
4. Querying points for a player

The tests simulate real-world interactions with the contract, ensuring that it behaves correctly under various scenarios. They use the GenLayer Studio to deploy and interact with the contract, providing a comprehensive check of the contract's functionality in a controlled environment.

To run the tests, use the `gltest` command as mentioned in the "Steps to run this example" section.


## 💬 Community
Connect with the GenLayer community to discuss, collaborate, and share insights:
- **[Discord Channel](https://discord.gg/8Jm4v89VAu)**: Our primary hub for discussions, support, and announcements.
- **[Telegram Group](https://t.me/genlayer)**: For more informal chats and quick updates.

Your continuous feedback drives better product development. Please engage with us regularly to test, discuss, and improve GenLayer.

## 📖 Documentation
For detailed information on how to use GenLayerJS SDK, please refer to our [documentation](https://docs.genlayer.com/).

## 📜 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
