"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Loader2, Plus, Settings, BarChart3, Clock, CheckCircle, XCircle } from "lucide-react";
import { useHubStats, useChains, useMarkets, useRegisterChain, useCreateMarket, useTriggerResolution, useVerdict } from "@/lib/hooks/useOracle";
import { useWallet } from "@/lib/genlayer/wallet";
import { error } from "@/lib/utils/toast";

export function OracleManager() {
  const { address, isConnected } = useWallet();
  const { data: hubStats, isLoading: statsLoading } = useHubStats();
  const { data: chains, isLoading: chainsLoading } = useChains();
  const [selectedChain, setSelectedChain] = useState<string>("");
  const { data: markets } = useMarkets(selectedChain);

  const registerChain = useRegisterChain();
  const createMarket = useCreateMarket();
  const triggerResolution = useTriggerResolution();

  // Form states
  const [chainForm, setChainForm] = useState({
    chainKey: "polygon-amoy-v1",
    adapterAddress: "0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79",
    callbackUrl: "",
    stakeAmount: "1000000000000000000", // 1 ETH
  });

  const [marketForm, setMarketForm] = useState({
    externalId: "",
    question: "",
    description: "",
    resolutionCriteria: "",
    evidenceUrls: "",
    deadline: "",
    prizePoolProxy: "",
    oracleFee: "10000000000000000", // 0.01 ETH
  });

  const handleRegisterChain = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isConnected) {
      error("Please connect your wallet first");
      return;
    }

    try {
      await registerChain.mutateAsync({
        chainKey: chainForm.chainKey,
        chainType: 0, // EVM
        adapterType: 3, // RELAYER
        adapterAddress: chainForm.adapterAddress,
        callbackUrl: chainForm.callbackUrl,
        metadata: {
          chain_id: 80002,
          rpc_url: "https://rpc-amoy.polygon.technology",
          contract: chainForm.adapterAddress,
        },
        feeBps: 0,
        stakeAmount: chainForm.stakeAmount,
      });
    } catch (err) {
      console.error("Registration failed:", err);
    }
  };

  const handleCreateMarket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedChain) {
      error("Please select a chain first");
      return;
    }

    try {
      await createMarket.mutateAsync({
        chainKey: selectedChain,
        externalId: marketForm.externalId,
        question: marketForm.question,
        description: marketForm.description,
        resolutionCriteria: marketForm.resolutionCriteria,
        evidenceUrls: marketForm.evidenceUrls.split(",").map(url => url.trim()),
        deadline: Math.floor(new Date(marketForm.deadline).getTime() / 1000),
        prizePoolProxy: parseInt(marketForm.prizePoolProxy),
        oracleFee: marketForm.oracleFee,
      });
    } catch (err) {
      console.error("Market creation failed:", err);
    }
  };

  const handleTriggerResolution = async (marketId: string) => {
    try {
      await triggerResolution.mutateAsync(marketId);
    } catch (err) {
      console.error("Resolution trigger failed:", err);
    }
  };

  const getStateBadge = (state: number) => {
    switch (state) {
      case 0: return <Badge variant="secondary"><Clock className="w-3 h-3 mr-1" />Pending</Badge>;
      case 1: return <Badge variant="outline"><Settings className="w-3 h-3 mr-1" />Resolving</Badge>;
      case 2: return <Badge variant="default"><CheckCircle className="w-3 h-3 mr-1" />Resolved</Badge>;
      default: return <Badge variant="destructive">Unknown</Badge>;
    }
  };

  const getOutcomeText = (outcome: number) => {
    switch (outcome) {
      case 0: return "Unresolved";
      case 1: return "YES";
      case 2: return "NO";
      case 3: return "INVALID";
      default: return "Unknown";
    }
  };

  return (
    <div className="space-y-6">
      {/* Hub Stats */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Oracle Hub Statistics
          </CardTitle>
        </CardHeader>
        <CardContent>
          {statsLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-accent">{(hubStats as any)?.total_chains || 0}</div>
                <div className="text-sm text-muted-foreground">Chains</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-accent">{(hubStats as any)?.total_markets || 0}</div>
                <div className="text-sm text-muted-foreground">Markets</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-accent">{(hubStats as any)?.total_resolved || 0}</div>
                <div className="text-sm text-muted-foreground">Resolved</div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Tabs defaultValue="chains" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="chains">Chains</TabsTrigger>
          <TabsTrigger value="markets">Markets</TabsTrigger>
          <TabsTrigger value="create">Create</TabsTrigger>
        </TabsList>

        {/* Chains Tab */}
        <TabsContent value="chains" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Registered Chains</CardTitle>
              <CardDescription>Chains registered with the Oracle Hub</CardDescription>
            </CardHeader>
            <CardContent>
              {chainsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin" />
                </div>
              ) : (
                <div className="space-y-4">
                  {chains?.map((chain) => (
                    <div
                      key={chain.chain_key}
                      className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                        selectedChain === chain.chain_key ? "border-accent bg-accent/5" : "hover:bg-muted/50"
                      }`}
                      onClick={() => setSelectedChain(chain.chain_key)}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-semibold">{chain.chain_key}</h3>
                          <p className="text-sm text-muted-foreground">
                            Adapter: {chain.adapter_address.slice(0, 6)}...{chain.adapter_address.slice(-4)}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={chain.active ? "default" : "secondary"}>
                            {chain.active ? "Active" : "Inactive"}
                          </Badge>
                          <span className="text-sm text-muted-foreground">
                            {chain.markets_resolved} resolved
                          </span>
                        </div>
                      </div>
                    </div>
                  )) || (
                    <div className="text-center py-8 text-muted-foreground">
                      No chains registered yet
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Markets Tab */}
        <TabsContent value="markets" className="space-y-4">
          {!selectedChain ? (
            <Card>
              <CardContent className="py-8">
                <div className="text-center text-muted-foreground">
                  Select a chain to view markets
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Markets for {selectedChain}</CardTitle>
                <CardDescription>Prediction markets on this chain</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {markets?.map((market) => (
                    <div key={market.market_id} className="p-4 border rounded-lg">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h3 className="font-semibold">{market.question}</h3>
                          <p className="text-sm text-muted-foreground mt-1">
                            {market.description}
                          </p>
                          <div className="flex items-center gap-4 mt-2">
                            {getStateBadge(market.state)}
                            {market.state === 2 && (
                              <span className="text-sm">
                                Outcome: <strong>{getOutcomeText(market.outcome)}</strong>
                                {market.confidence > 0 && ` (${market.confidence}% confidence)`}
                              </span>
                            )}
                            <span className="text-sm text-muted-foreground">
                              Deadline: {new Date(market.deadline * 1000).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                        {market.state === 0 && new Date(market.deadline * 1000) < new Date() && (
                          <Button
                            size="sm"
                            onClick={() => handleTriggerResolution(market.market_id)}
                            disabled={triggerResolution.isPending}
                          >
                            {triggerResolution.isPending ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              "Resolve"
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  )) || (
                    <div className="text-center py-8 text-muted-foreground">
                      No markets found for this chain
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Create Tab */}
        <TabsContent value="create" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Register Chain */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Plus className="w-5 h-5" />
                  Register Chain
                </CardTitle>
                <CardDescription>Register a new blockchain with the Oracle Hub</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleRegisterChain} className="space-y-4">
                  <div>
                    <Label htmlFor="chainKey">Chain Key</Label>
                    <Input
                      id="chainKey"
                      value={chainForm.chainKey}
                      onChange={(e) => setChainForm(prev => ({ ...prev, chainKey: e.target.value }))}
                      placeholder="polygon-amoy-v1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="adapterAddress">Adapter Address</Label>
                    <Input
                      id="adapterAddress"
                      value={chainForm.adapterAddress}
                      onChange={(e) => setChainForm(prev => ({ ...prev, adapterAddress: e.target.value }))}
                      placeholder="0x..."
                    />
                  </div>
                  <div>
                    <Label htmlFor="callbackUrl">Callback URL (optional)</Label>
                    <Input
                      id="callbackUrl"
                      value={chainForm.callbackUrl}
                      onChange={(e) => setChainForm(prev => ({ ...prev, callbackUrl: e.target.value }))}
                      placeholder="https://..."
                    />
                  </div>
                  <div>
                    <Label htmlFor="stakeAmount">Stake Amount (wei)</Label>
                    <Input
                      id="stakeAmount"
                      value={chainForm.stakeAmount}
                      onChange={(e) => setChainForm(prev => ({ ...prev, stakeAmount: e.target.value }))}
                      placeholder="1000000000000000000"
                    />
                  </div>
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={registerChain.isPending || !isConnected}
                  >
                    {registerChain.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : null}
                    Register Chain
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Create Market */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Plus className="w-5 h-5" />
                  Create Market
                </CardTitle>
                <CardDescription>Create a new prediction market</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleCreateMarket} className="space-y-4">
                  <div>
                    <Label htmlFor="externalId">External ID</Label>
                    <Input
                      id="externalId"
                      value={marketForm.externalId}
                      onChange={(e) => setMarketForm(prev => ({ ...prev, externalId: e.target.value }))}
                      placeholder="test-market-001"
                    />
                  </div>
                  <div>
                    <Label htmlFor="question">Question</Label>
                    <Input
                      id="question"
                      value={marketForm.question}
                      onChange={(e) => setMarketForm(prev => ({ ...prev, question: e.target.value }))}
                      placeholder="Will ETH exceed $3000 by June 2025?"
                    />
                  </div>
                  <div>
                    <Label htmlFor="description">Description</Label>
                    <Textarea
                      id="description"
                      value={marketForm.description}
                      onChange={(e) => setMarketForm(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Test market for GenLayer Oracle"
                    />
                  </div>
                  <div>
                    <Label htmlFor="resolutionCriteria">Resolution Criteria</Label>
                    <Textarea
                      id="resolutionCriteria"
                      value={marketForm.resolutionCriteria}
                      onChange={(e) => setMarketForm(prev => ({ ...prev, resolutionCriteria: e.target.value }))}
                      placeholder="YES if ETH/USD >= $3000 on Coinbase. NO otherwise."
                    />
                  </div>
                  <div>
                    <Label htmlFor="evidenceUrls">Evidence URLs (comma-separated)</Label>
                    <Input
                      id="evidenceUrls"
                      value={marketForm.evidenceUrls}
                      onChange={(e) => setMarketForm(prev => ({ ...prev, evidenceUrls: e.target.value }))}
                      placeholder="https://api.coinbase.com/v2/prices/ETH-USD/spot"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="deadline">Deadline</Label>
                      <Input
                        id="deadline"
                        type="datetime-local"
                        value={marketForm.deadline}
                        onChange={(e) => setMarketForm(prev => ({ ...prev, deadline: e.target.value }))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="prizePoolProxy">Prize Pool Proxy ($)</Label>
                      <Input
                        id="prizePoolProxy"
                        type="number"
                        value={marketForm.prizePoolProxy}
                        onChange={(e) => setMarketForm(prev => ({ ...prev, prizePoolProxy: e.target.value }))}
                        placeholder="1000"
                      />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="oracleFee">Oracle Fee (wei)</Label>
                    <Input
                      id="oracleFee"
                      value={marketForm.oracleFee}
                      onChange={(e) => setMarketForm(prev => ({ ...prev, oracleFee: e.target.value }))}
                      placeholder="10000000000000000"
                    />
                  </div>
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={createMarket.isPending || !selectedChain || !isConnected}
                  >
                    {createMarket.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : null}
                    Create Market
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}