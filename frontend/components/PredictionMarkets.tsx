"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Coins, TrendingUp, Clock } from "lucide-react";
import { useWallet } from "@/lib/genlayer/wallet";
import { useOracleConsumer } from "@/lib/hooks/useOracleConsumer";
import { success, error } from "@/lib/utils/toast";

export function PredictionMarkets() {
  const { address, isConnected } = useWallet();
  const {
    markets,
    isLoading: marketsLoading,
    placeBet,
    claimWinnings,
    refreshMarkets
  } = useOracleConsumer();

  const [selectedMarket, setSelectedMarket] = useState<string>("");
  const [betAmount, setBetAmount] = useState<string>("");
  const [betChoice, setBetChoice] = useState<"yes" | "no" | "">("");

  const handlePlaceBet = async () => {
    if (!selectedMarket || !betChoice || !betAmount) {
      error("Please fill all fields");
      return;
    }

    try {
      await placeBet.mutateAsync({
        marketId: selectedMarket,
        isYes: betChoice === "yes",
        amount: betAmount,
      });
      setBetAmount("");
      setBetChoice("");
      success("Bet placed successfully!");
    } catch (err) {
      console.error("Bet placement failed:", err);
    }
  };

  const handleClaimWinnings = async (marketId: string) => {
    try {
      await claimWinnings.mutateAsync(marketId);
      success("Winnings claimed successfully!");
    } catch (err) {
      console.error("Claim failed:", err);
    }
  };

  const getMarketStatus = (state: number, deadline: number) => {
    const now = Math.floor(Date.now() / 1000);
    if (state === 2) return { text: "Resolved", color: "bg-green-500" };
    if (state === 1) return { text: "Resolving", color: "bg-yellow-500" };
    if (now > deadline) return { text: "Pending Resolution", color: "bg-orange-500" };
    return { text: "Active", color: "bg-blue-500" };
  };

  const getOutcomeText = (outcome: number) => {
    if (outcome === 1) return "YES";
    if (outcome === 2) return "NO";
    if (outcome === 3) return "INVALID";
    return "UNRESOLVED";
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          Prediction Markets
        </CardTitle>
        <CardDescription>
          Place bets on AI-resolved prediction markets
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Markets List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Available Markets</h3>
            <Button
              variant="outline"
              size="sm"
              onClick={refreshMarkets}
              disabled={marketsLoading}
            >
              {marketsLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Refresh"}
            </Button>
          </div>

          {marketsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : markets?.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No markets available. Create one using the Oracle Manager above.
            </p>
          ) : (
            <div className="space-y-3">
              {markets?.map((market) => {
                const status = getMarketStatus(market.state, market.deadline);
                return (
                  <Card key={market.marketId} className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <h4 className="font-semibold mb-1">{market.question}</h4>
                        <p className="text-sm text-muted-foreground mb-2">
                          {market.description}
                        </p>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            Deadline: {new Date(market.deadline * 1000).toLocaleDateString()}
                          </span>
                          <span className="flex items-center gap-1">
                            <Coins className="h-3 w-3" />
                            Pool: {(market.yesPool + market.noPool) / 1e18} ETH
                          </span>
                        </div>
                      </div>
                      <Badge className={status.color}>
                        {status.text}
                      </Badge>
                    </div>

                    {market.state === 2 && (
                      <div className="mb-3 p-2 bg-muted rounded">
                        <p className="text-sm">
                          <strong>Outcome:</strong> {getOutcomeText(market.outcome)}
                          {market.confidence > 0 && (
                            <span className="ml-2">
                              (Confidence: {(market.confidence / 10).toFixed(1)}%)
                            </span>
                          )}
                        </p>
                        {market.reasoning && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {market.reasoning}
                          </p>
                        )}
                      </div>
                    )}

                    {/* Bet Placement */}
                    {market.state === 0 && isConnected && (
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-2">
                          <Button
                            variant={betChoice === "yes" ? "default" : "outline"}
                            size="sm"
                            onClick={() => {
                              setSelectedMarket(market.marketId);
                              setBetChoice("yes");
                            }}
                          >
                            Bet YES ({(market.yesPool / 1e18).toFixed(3)} ETH)
                          </Button>
                          <Button
                            variant={betChoice === "no" ? "default" : "outline"}
                            size="sm"
                            onClick={() => {
                              setSelectedMarket(market.marketId);
                              setBetChoice("no");
                            }}
                          >
                            Bet NO ({(market.noPool / 1e18).toFixed(3)} ETH)
                          </Button>
                        </div>

                        {selectedMarket === market.marketId && betChoice && (
                          <div className="flex gap-2">
                            <Input
                              type="number"
                              step="0.01"
                              placeholder="Amount in ETH"
                              value={betAmount}
                              onChange={(e) => setBetAmount(e.target.value)}
                            />
                            <Button
                              onClick={handlePlaceBet}
                              disabled={placeBet.isPending}
                              size="sm"
                            >
                              {placeBet.isPending ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                "Place Bet"
                              )}
                            </Button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Claim Winnings */}
                    {market.state === 2 && isConnected && (
                      <Button
                        onClick={() => handleClaimWinnings(market.marketId)}
                        disabled={claimWinnings.isPending}
                        size="sm"
                        className="w-full"
                      >
                        {claimWinnings.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          "Claim Winnings"
                        )}
                      </Button>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}