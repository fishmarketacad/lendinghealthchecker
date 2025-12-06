# Curvance Protocol Integration

## Required Contract Addresses

To use Curvance health checking, you need the **ProtocolReader** contract address on Monad.

## Current Addresses Available

From Curvance's deployment info:
- `SimpleZapper`: `0x5af9b7cAc0530d3C9e11C23B7A69Cce335B8C395`
- `NativeVaultZapper`: `0x1D60A3F3f84F095b3D6001fbc135F6D42c812269`
- `OracleManager`: `0x32fad39e79fac67f80d1c86cbd1598043e52cdb6`
- `RedstoneClassicAdaptor`: `0x0fa602b3e748438a3f1599206ed6dc497ab3331e`
- `CentralRegistry`: `0x1310f352f1389969ece6741671c4b919523912ff`
- `ProtocolReader`: `0xBF67b967eCcf21f2C196f947b703e874D5dB649d` ✅ **CONFIRMED WORKING**

## How It Works

### Discovery Flow

1. **Query Central Registry** (`0x1310f352f1389969ece6741671c4b919523912ff`)
   - Call `marketManagers()` to get all registered MarketManager addresses
   - Falls back to known MarketManager list if registry query fails

2. **Get User Positions** (`ProtocolReader.getAllDynamicState()`)
   - Returns all user positions with structure: `(cToken, collateral, debt, health, tokenBalance)`
   - Health factor is included in the response (index 3)
   - Multiple positions may exist for the same MarketManager (different cTokens)

3. **Get Accurate Health Factor** (`ProtocolReader.getPositionHealth()`)
   - For each position, try calling `getPositionHealth` with each MarketManager
   - Parameters: `(mm, account, cToken, borrowableCToken=0, isDeposit=false, collateralAssets=0, isRepayment=false, debtAssets=0, bufferTime=0)`
   - If `getPositionHealth` returns max uint256 or fails, fallback to health from `getAllDynamicState`

4. **Deduplication**
   - Multiple positions may map to the same MarketManager
   - We deduplicate by MarketManager address, keeping the position with the worst (lowest) health factor
   - This ensures each MarketManager appears only once in the results

### Key Learnings

- **`getAllDynamicState` is reliable**: Always returns health factors, even if `getPositionHealth` fails
- **`getPositionHealth` can return max uint256**: This indicates an invalid/closed position - filter these out
- **Fallback strategy works**: When `getPositionHealth` fails, using health from `getAllDynamicState` is accurate
- **Deduplication is critical**: `getAllDynamicState` can return multiple positions for the same MarketManager (different cTokens), so we must deduplicate by MarketManager address

## Setup

The ProtocolReader address is already configured in the code:
```bash
CURVANCE_PROTOCOL_READER_ADDRESS=0xBF67b967eCcf21f2C196f947b703e874D5dB649d
```

## Testing

After setting the address, test with:
```bash
/check curvance
/position curvance
```

