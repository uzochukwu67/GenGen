"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ethers } from "ethers";
import { useWallet } from "@/lib/genlayer/wallet";
import { success, error } from "@/lib/utils/toast";

// OracleConsumer ABI
const ORACLE_CONSUMER_ABI = [
  {
    "inputs": [
      {"name": "marketId", "type": "string"},
      {"name": "outcome", "type": "uint8"},
      {"name": "confidence", "type": "uint256"},
      {"name": "reasoning", "type": "string"}
    ],
    "name": "receiveVerdict",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [{"name": "marketId", "type": "string"}],
    "name": "getMarket",
    "outputs": [
      {"name": "question", "type": "string"},
      {"name": "state", "type": "uint8"},
      {"name": "outcome", "type": "uint8"},
      {"name": "yesPool", "type": "uint256"},
      {"name": "noPool", "type": "uint256"},
      {"name": "deadline", "type": "uint256"},
      {"name": "confidence", "type": "uint256"},
      {"name": "verdictReceived", "type": "bool"}
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "getAllMarkets",
    "outputs": [{"name": "", "type": "string[]"}],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{"name": "marketId", "type": "string"}, {"name": "isYes", "type": "bool"}],
    "name": "placeBet",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function"
  },
  {
    "inputs": [{"name": "marketId", "type": "string"}],
    "name": "claimWinnings",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
];

const CONTRACT_ADDRESS = process.env.NEXT_PUBLIC_CONSUMER_POLYGON || "0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79";
const RPC_URL = "https://rpc-amoy.polygon.technology";

export interface MarketInfo {
  marketId: string;
  question: string;
  state: number;
  outcome: number;
  yesPool: string;
  noPool: string;
  deadline: number;
  confidence: number;
  verdictReceived: boolean;
}

/**
 * Hook to interact with OracleConsumer contract
 */
export function useOracleConsumer() {
  const { address, isConnected } = useWallet();
  const queryClient = useQueryClient();

  // Get all market IDs
  const { data: marketIds, isLoading: marketIdsLoading } = useQuery({
    queryKey: ["oracle-consumer-markets"],
    queryFn: async () => {
      const provider = new ethers.JsonRpcProvider(RPC_URL);
      const contract = new ethers.Contract(CONTRACT_ADDRESS, ORACLE_CONSUMER_ABI, provider);
      return await contract.getAllMarkets();
    },
    refetchInterval: 10000,
  });

  // Get market details for each market ID
  const { data: markets, isLoading: marketsLoading } = useQuery({
    queryKey: ["oracle-consumer-market-details", marketIds],
    queryFn: async () => {
      if (!marketIds || marketIds.length === 0) return [];

      const provider = new ethers.JsonRpcProvider(RPC_URL);
      const contract = new ethers.Contract(CONTRACT_ADDRESS, ORACLE_CONSUMER_ABI, provider);

      const marketPromises = marketIds.map(async (marketId: string) => {
        const details = await contract.getMarket(marketId);
        return {
          marketId,
          question: details[0],
          state: details[1],
          outcome: details[2],
          yesPool: details[3].toString(),
          noPool: details[4].toString(),
          deadline: Number(details[5]),
          confidence: Number(details[6]),
          verdictReceived: details[7],
        } as MarketInfo;
      });

      return await Promise.all(marketPromises);
    },
    enabled: !!marketIds,
    refetchInterval: 5000,
  });

  // Place bet mutation
  const placeBet = useMutation({
    mutationFn: async (params: { marketId: string; isYes: boolean; amount: string }) => {
      if (!address || !isConnected) throw new Error("Wallet not connected");

      const provider = new ethers.BrowserProvider(window.ethereum!);
      const signer = await provider.getSigner();
      const contract = new ethers.Contract(CONTRACT_ADDRESS, ORACLE_CONSUMER_ABI, signer);

      const tx = await contract.placeBet(params.marketId, params.isYes, {
        value: ethers.parseEther(params.amount),
      });

      return await tx.wait();
    },
    onSuccess: () => {
      success("Bet placed successfully!");
      queryClient.invalidateQueries({ queryKey: ["oracle-consumer-market-details"] });
    },
    onError: (error) => {
      console.error("Failed to place bet:", error);
      error("Failed to place bet");
    },
  });

  // Claim winnings mutation
  const claimWinnings = useMutation({
    mutationFn: async (marketId: string) => {
      if (!address || !isConnected) throw new Error("Wallet not connected");

      const provider = new ethers.BrowserProvider(window.ethereum!);
      const signer = await provider.getSigner();
      const contract = new ethers.Contract(CONTRACT_ADDRESS, ORACLE_CONSUMER_ABI, signer);

      const tx = await contract.claimWinnings(marketId);
      return await tx.wait();
    },
    onSuccess: () => {
      success("Winnings claimed successfully!");
      queryClient.invalidateQueries({ queryKey: ["oracle-consumer-market-details"] });
    },
    onError: (error) => {
      console.error("Failed to claim winnings:", error);
      error("Failed to claim winnings");
    },
  });

  const refreshMarkets = () => {
    queryClient.invalidateQueries({ queryKey: ["oracle-consumer-markets"] });
    queryClient.invalidateQueries({ queryKey: ["oracle-consumer-market-details"] });
  };

  return {
    markets,
    isLoading: marketIdsLoading || marketsLoading,
    placeBet,
    claimWinnings,
    refreshMarkets,
  };
}