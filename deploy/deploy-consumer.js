#!/usr/bin/env node

/**
 * deploy-consumer.js — Deploy OracleConsumer to EVM chains
 *
 * Usage:
 *   node deploy-consumer.js --network polygon --relayer 0x... --chain-key polygon-polymarket-v1 --oracle-fee 10000000000000000
 *
 * Requirements:
 *   npm install ethers dotenv
 */

const ethers = require('ethers');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

// Network configurations
const NETWORKS = {
  polygon: {
    rpcUrl: process.env.EVM_RPC_POLYGON || 'https://polygon-rpc.com',
    chainId: 137,
  },
  ethereum: {
    rpcUrl: process.env.EVM_RPC_ETH || 'https://mainnet.infura.io/v3/YOUR_KEY',
    chainId: 1,
  },
  base: {
    rpcUrl: process.env.EVM_RPC_BASE || 'https://mainnet.base.org',
    chainId: 8453,
  },
};

async function main() {
  const args = process.argv.slice(2);
  const network = args.find(arg => arg.startsWith('--network='))?.split('=')[1];
  const relayer = args.find(arg => arg.startsWith('--relayer='))?.split('=')[1];
  const chainKey = args.find(arg => arg.startsWith('--chain-key='))?.split('=')[1];
  const oracleFee = args.find(arg => arg.startsWith('--oracle-fee='))?.split('=')[1];

  if (!network || !relayer || !chainKey || !oracleFee) {
    console.error('Usage: node deploy-consumer.js --network <network> --relayer <address> --chain-key <key> --oracle-fee <wei>');
    console.error('Example: node deploy-consumer.js --network polygon --relayer 0x123... --chain-key polygon-polymarket-v1 --oracle-fee 10000000000000000');
    process.exit(1);
  }

  const networkConfig = NETWORKS[network];
  if (!networkConfig) {
    console.error(`Unknown network: ${network}. Available: ${Object.keys(NETWORKS).join(', ')}`);
    process.exit(1);
  }

  const privateKey = process.env.RELAYER_PRIVATE_KEY;
  if (!privateKey) {
    console.error('RELAYER_PRIVATE_KEY not set in .env');
    process.exit(1);
  }

  // Connect to network
  const provider = new ethers.JsonRpcProvider(networkConfig.rpcUrl);
  const wallet = new ethers.Wallet(privateKey, provider);

  console.log(`Deploying OracleConsumer to ${network}...`);
  console.log(`Relayer: ${relayer}`);
  console.log(`Chain Key: ${chainKey}`);
  console.log(`Oracle Fee: ${oracleFee} wei`);
  console.log(`Deployer: ${wallet.address}`);

  // Load contract bytecode and ABI
  const contractPath = path.join(__dirname, '..', 'contracts', 'OracleConsumer.sol');
  const contractSource = fs.readFileSync(contractPath, 'utf8');

  // For simplicity, we'll use a pre-compiled contract
  // In production, you'd compile with solc or hardhat
  const contractBytecode = '0x' + getContractBytecode(); // You'd need to compile this
  const contractABI = getContractABI();

  const factory = new ethers.ContractFactory(contractABI, contractBytecode, wallet);

  try {
    const contract = await factory.deploy(relayer, chainKey, oracleFee);
    await contract.waitForDeployment();

    const address = await contract.getAddress();
    console.log(`✅ OracleConsumer deployed at: ${address}`);
    console.log(`Update your .env file:`);
    console.log(`CONSUMER_${network.toUpperCase()}=${address}`);

  } catch (error) {
    console.error('❌ Deployment failed:', error);
    process.exit(1);
  }
}

// Placeholder functions - you'd need to compile the contract
function getContractBytecode() {
  // Return the compiled bytecode
  return '608060405234801561001057600080fd5b50d3801561001d57600080fd5b50d2801561002a57600080fd5b50604051610c...'; // Truncated
}

function getContractABI() {
  return [
    {
      "inputs": [
        {"name": "_relayer", "type": "address"},
        {"name": "_chainKey", "type": "string"},
        {"name": "_oracleFee", "type": "uint256"}
      ],
      "stateMutability": "nonpayable",
      "type": "constructor"
    }
  ];
}

main().catch(console.error);