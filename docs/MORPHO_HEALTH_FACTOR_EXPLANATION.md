# Morpho Health Factor vs Aave Health Factor

## Aave Health Factor (What You Know)

**Formula:**
```
Health Factor = (Total Collateral Value × Liquidation Threshold) / Total Debt Value
```

**Example with ETH collateral and USDC debt:**
- You have: 2 ETH ($4000) as collateral, $2000 USDC debt
- Liquidation Threshold: 80% (0.8)
- Health Factor = ($4000 × 0.8) / $2000 = $3200 / $2000 = **1.6**

**What it means:**
- Health Factor of **1.5** means: Your collateral can drop by **1/1.5 = 66.7%** before liquidation
- In other words: ETH price can drop from $2000 to $666.67 before you're liquidated
- Health Factor < 1.0 = **Liquidatable**
- Health Factor = 1.0 = **Exactly at liquidation threshold**
- Health Factor > 1.0 = **Safe** (higher is safer)

## Morpho Health Factor (Different!)

**Formula:**
```
Health Factor = (Collateral Value in Loan Token × LLTV) / Borrowed Amount
```

**Key Differences:**

### 1. **LLTV vs Liquidation Threshold**
- **Aave**: Uses "Liquidation Threshold" (e.g., 80% = 0.8)
- **Morpho**: Uses "LLTV" (Liquidation Loan-to-Value) - similar concept but calculated differently
- Both represent: "Maximum LTV before liquidation"

### 2. **Collateral Value Calculation**
- **Aave**: Collateral value in USD (or base currency)
- **Morpho**: Collateral value **converted to loan token units**
  - If you borrow USDC with ETH collateral:
  - Morpho converts ETH value → USDC equivalent
  - Then calculates: (ETH_as_USDC × LLTV) / USDC_debt

### 3. **Market-Based**
- **Aave**: One health factor for entire account (all positions combined)
- **Morpho**: **One health factor per market** (each market is separate)
  - Each market = specific pair (e.g., ETH/USDC market)
  - You can have multiple positions in different markets
  - Each has its own health factor

## Example: Morpho Health Factor

**Market: ETH/USDC**
- You supply: 1 ETH ($2000) as collateral
- You borrow: 1000 USDC
- LLTV: 75% (0.75)
- Oracle price: 1 ETH = 2000 USDC

**Calculation:**
1. Collateral value in loan token (USDC): 1 ETH × 2000 = **2000 USDC**
2. Health Factor = (2000 × 0.75) / 1000 = 1500 / 1000 = **1.5**

**What it means:**
- Health Factor of **1.5** means: Your collateral can drop by **1/1.5 = 66.7%** before liquidation
- ETH price can drop from $2000 to $666.67 before liquidation
- **Same interpretation as Aave!**

## Key Takeaway

**Both use the same concept:**
- Health Factor = How much your collateral can drop before liquidation
- Health Factor 1.5 = Collateral can drop by 33.3% before liquidation
- Health Factor 2.0 = Collateral can drop by 50% before liquidation
- Health Factor < 1.0 = Liquidatable

**The difference is in calculation:**
- Aave: Uses USD/base currency, combines all positions
- Morpho: Uses loan token units, per-market basis

## Finding Market IDs

### Method 1: GraphQL API (Best!)
Use Morpho's GraphQL API at `https://api.morpho.org/g`:

```graphql
query GetUserMarkets($userAddress: String!) {
  userByAddress(address: $userAddress) {
    marketPositions {
      market {
        id
      }
      healthFactor
    }
  }
}
```

### Method 2: Morpho App
1. Go to https://app.morpho.org
2. Connect wallet
3. View your positions
4. Market ID is shown in position details

### Method 3: Contract Events
Query Morpho Blue contract events for user's positions

