"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createClient } from "genlayer-js";
import { useWallet } from "@/lib/genlayer/wallet";
import { error, success } from "@/lib/utils/toast";

// GenLayer client
const glClient = createClient({
  endpoint: process.env.NEXT_PUBLIC_GENLAYER_RPC_URL || "https://studio.genlayer.com",
});

const HUB_ADDRESS = process.env.NEXT_PUBLIC_HUB_ADDRESS || "0x5286D78605d6D255A2FfF4911cC57ef35692e461";

// Types
export interface ChainInfo {
  chain_key: string;
  chain_type: number;
  adapter_type: number;
  adapter_address: string;
  callback_url: string;
  metadata: string;
  fee_bps: number;
  active: boolean;
  markets_resolved: number;
  total_stake: string;
}

export interface MarketInfo {
  market_id: string;
  chain_key: string;
  external_id: string;
  question: string;
  description: string;
  resolution_criteria: string;
  evidence_urls: string[];
  deadline: number;
  prize_pool_proxy: number;
  state: number;
  outcome: number;
  confidence: number;
  resolved_at: number;
  created_at: number;
}

/**
 * Hook to get hub statistics
 */
export function useHubStats() {
  return useQuery({
    queryKey: ["hub-stats"],
    queryFn: async () => {
      const result = await glClient.call(HUB_ADDRESS, "get_hub_stats", {});
      return result;
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });
}

/**
 * Hook to get all registered chains
 * NOTE: get_all_chains method doesn't exist in contract, using placeholder
 */
export function useChains() {
  return useQuery({
    queryKey: ["chains"],
    queryFn: async () => {
      // TODO: Implement proper chain enumeration or remove this hook
      // For now, return known chains
      return [
        {
          chain_key: "polygon-amoy-v1",
          chain_type: 0,
          adapter_type: 3,
          adapter_address: "0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79",
          owner: "",
          fee_bps: 0,
          stake: "0",
          active: true,
          markets_created: 0,
          markets_resolved: 0,
          registered_at: Date.now(),
          callback_url: "",
          metadata: "{}",
        }
      ] as ChainInfo[];
    },
    refetchInterval: 30000,
  });
}

/**
 * Hook to get markets for a specific chain
 */
export function useMarkets(chainKey?: string) {
  return useQuery({
    queryKey: ["markets", chainKey],
    queryFn: async () => {
      if (!chainKey) return [];
      const result = await glClient.call(HUB_ADDRESS, "get_markets_for_chain", {
        chain_key: chainKey,
      });
      return result as MarketInfo[];
    },
    enabled: !!chainKey,
    refetchInterval: 10000, // Refetch every 10 seconds
  });
}

/**
 * Hook to register a new chain
 */
export function useRegisterChain() {
  const queryClient = useQueryClient();
  const { address } = useWallet();

  return useMutation({
    mutationFn: async (params: {
      chainKey: string;
      chainType: number;
      adapterType: number;
      adapterAddress: string;
      callbackUrl: string;
      metadata: any;
      feeBps: number;
      stakeAmount: string;
    }) => {
      if (!address) throw new Error("Wallet not connected");

      const result = await glClient.sendTransaction(
        HUB_ADDRESS,
        "register_chain",
        {
          chain_key: params.chainKey,
          chain_type: params.chainType,
          adapter_type: params.adapterType,
          adapter_address: params.adapterAddress,
          callback_url: params.callbackUrl,
          metadata: JSON.stringify(params.metadata),
          fee_bps: params.feeBps,
        },
        {
          privateKey: process.env.NEXT_PUBLIC_RELAYER_PRIVATE_KEY || "",
          value: params.stakeAmount,
        }
      );

      return result;
    },
    onSuccess: () => {
      success("Chain registered successfully!");
      queryClient.invalidateQueries({ queryKey: ["chains"] });
    },
    onError: (error) => {
      console.error("Failed to register chain:", error);
      error("Failed to register chain");
    },
  });
}

/**
 * Hook to create a new market
 */
export function useCreateMarket() {
  const queryClient = useQueryClient();
  const { address } = useWallet();

  return useMutation({
    mutationFn: async (params: {
      chainKey: string;
      externalId: string;
      question: string;
      description: string;
      resolutionCriteria: string;
      evidenceUrls: string[];
      deadline: number;
      prizePoolProxy: number;
      oracleFee: string;
    }) => {
      if (!address) throw new Error("Wallet not connected");

      const result = await glClient.sendTransaction(
        HUB_ADDRESS,
        "create_market",
        {
          chain_key: params.chainKey,
          external_id: params.externalId,
          question: params.question,
          description: params.description,
          resolution_criteria: params.resolutionCriteria,
          evidence_urls: params.evidenceUrls,
          deadline: params.deadline,
          prize_pool_proxy: params.prizePoolProxy,
        },
        {
          privateKey: process.env.NEXT_PUBLIC_RELAYER_PRIVATE_KEY || "",
          value: params.oracleFee,
        }
      );

      return result;
    },
    onSuccess: (_, variables) => {
      success("Market created successfully!");
      queryClient.invalidateQueries({ queryKey: ["markets", variables.chainKey] });
      queryClient.invalidateQueries({ queryKey: ["hub-stats"] });
    },
    onError: (error) => {
      console.error("Failed to create market:", error);
      error("Failed to create market");
    },
  });
}

/**
 * Hook to trigger resolution for a market
 */
export function useTriggerResolution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (marketId: string) => {
      const result = await glClient.sendTransaction(
        HUB_ADDRESS,
        "trigger_resolution",
        { market_id: marketId },
        {
          privateKey: process.env.NEXT_PUBLIC_RELAYER_PRIVATE_KEY || "",
        }
      );
      return result;
    },
    onSuccess: () => {
      success("Resolution triggered!");
      queryClient.invalidateQueries({ queryKey: ["markets"] });
    },
    onError: (error) => {
      console.error("Failed to trigger resolution:", error);
      error("Failed to trigger resolution");
    },
  });
}

/**
 * Hook to get verdict for a resolved market
 */
export function useVerdict(marketId?: string) {
  return useQuery({
    queryKey: ["verdict", marketId],
    queryFn: async () => {
      if (!marketId) return null;
      const result = await glClient.call(HUB_ADDRESS, "get_verdict", {
        market_id: marketId,
      });
      return result;
    },
    enabled: !!marketId,
    refetchInterval: 5000, // Refetch every 5 seconds
  });
}