import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("OracleConsumerModule", (m) => {
  // Constructor parameters
  const relayer = m.getParameter("relayer", "0x0000000000000000000000000000000000000000");
  const chainKey = m.getParameter("chainKey", "polygon-amoy-v1");
  const oracleFee = m.getParameter("oracleFee", 10000000000000000n); // 0.01 ETH

  const oracleConsumer = m.contract("OracleConsumer", [relayer, chainKey, oracleFee]);

  return { oracleConsumer };
});