# Questions for Euler Team - Isolated Vault Health Score Query

## Context

I'm building a health checker bot for Euler V2 on Monad testnet. I can see my position in the UI with health score 1.14 and debt $1.60, but I'm unable to query it programmatically using AccountLens.

## My Position Details

- **Account**: `0xf79c108fe2103f52c21c4063153605e351cb3d4d`
- **Controller Vault** (where I borrow from): `0x28bD4F19C812CBF9e33A206f87125f14E65dc8aA` (eWMON-5)
- **Collateral Vaults**: 
  - `0x6661a2b4008b70f22Ff84c2134ac6F51534E162d` (eshMON-1) - 25.06 tokens
  - `0x28bD4F19C812CBF9e33A206f87125f14E65dc8aA` (eWMON-5) - 64.27 tokens
- **UI Shows**: Health Score 1.14, Debt $1.60
- **Market**: "Isolated shMON-WMON-AUSD"

## The Problem

When I try to query health score using AccountLens:

```python
account_lens.getAccountInfo(account, vault_address)
# or
account_lens.getAccountLiquidityInfo(account, vault_address)
```

I get:
- `queryFailure: True`
- `queryFailureReason: 43855d0f` (hex error code)
- All liquidity values return 0

## What I've Tried

1. ✅ Using `getAccountInfo(account, vault)` - returns account info but liquidity query fails
2. ✅ Using `getAccountLiquidityInfo(account, vault)` directly - same error
3. ✅ Using `getAccountEnabledVaultsInfo(evc, account)` - returns 0 vaults (none enabled)
4. ✅ Checking EVC account info - shows no enabled controllers/collaterals

## Questions for Euler Team

### 1. Error Code `43855d0f`
**Question**: What does error code `43855d0f` mean? Is this a specific revert reason?

**Why**: This error appears when querying liquidity info for isolated vaults that aren't enabled in EVC.

### 2. Enabling Isolated Vaults in EVC
**Question**: How do I enable an isolated vault as a controller in EVC? I don't see an "Enable" option in the UI.

**Why**: The vault shows `isController=False` and `isCollateral=False`, and there are no enabled controllers/collaterals in my EVC account. But I have an active position with debt.

**Follow-up**: 
- Is enabling required for isolated vaults?
- Does enabling happen automatically when you borrow?
- If I already have a position, why isn't it enabled?

### 3. Querying Health Score for Isolated Vaults
**Question**: What's the correct way to query health score for isolated vault positions that aren't enabled in EVC?

**Why**: The UI shows health score 1.14, but AccountLens can't query it. Is there:
- A different lens contract I should use?
- A different function/method?
- Do I need to enable the vault first?

### 4. Difference Between UI and AccountLens
**Question**: How does the Euler UI calculate/display health score for isolated vaults? Does it use AccountLens or a different method?

**Why**: The UI shows health score, but AccountLens queries fail. This suggests the UI might be using a different approach.

### 5. Isolated Vault Architecture
**Question**: For isolated vaults, is the health score stored/calculated differently than EVC-enabled vaults?

**Why**: According to the docs, health score should be queried from the controller vault. But for isolated vaults, this query fails.

### 6. Alternative Query Methods
**Question**: Are there alternative ways to query health score for isolated vaults?
- Direct vault contract calls?
- Different lens contracts?
- Off-chain calculation methods?

### 7. EVC Enablement for Existing Positions
**Question**: If I already have a position in an isolated vault, do I need to enable it in EVC to query health score? If so, how?

**Why**: I have an active position but can't query it programmatically.

## Technical Details

- **Network**: Monad Testnet
- **AccountLens**: `0x960D481229f70c3c1CBCD3fA2d223f55Db9f36Ee`
- **VaultLens**: `0x15d1Cc54fB3f7C0498fc991a23d8Dc00DF3c32A0`
- **EVC**: `0x7a9324E8f270413fa2E458f5831226d99C7477CD`
- **RPC**: `https://rpc.monad.xyz`

## What I'm Trying to Build

A health checker bot that:
1. Monitors user positions across multiple protocols
2. Queries health scores programmatically
3. Sends alerts when health scores drop below thresholds

This works for other protocols (Curvance, Morpho) but not for Euler isolated vaults.

## Code Example

Here's what I'm trying to do:

```python
from web3 import Web3
from abis.AccountLens import abi as account_lens_abi

w3 = Web3(Web3.HTTPProvider('https://rpc.monad.xyz'))
account_lens = w3.eth.contract(
    address='0x960D481229f70c3c1CBCD3fA2d223f55Db9f36Ee',
    abi=account_lens_abi
)

account = '0xf79c108fe2103f52c21c4063153605e351cb3d4d'
vault = '0x28bD4F19C812CBF9e33A206f87125f14E65dc8aA'  # Controller vault

# This fails with queryFailure=True, error 43855d0f
liquidity_info = account_lens.functions.getAccountLiquidityInfo(
    account, vault
).call()

# I need to get:
# - Health score (collateralValueLiquidation / liabilityValueLiquidation)
# - Debt value
# - Collateral value
```

## Expected Behavior

I expect to be able to query:
- Health score: 1.14 (as shown in UI)
- Debt value: $1.60 (as shown in UI)
- Collateral value: calculated from collateral vaults

## Additional Context

- The position is active and visible in the UI
- I can see my collateral in multiple vaults
- The controller vault is `0x28bD4F19C812CBF9e33A206f87125f14E65dc8aA`
- All vaults show `isController=False` and `isCollateral=False`
- No vaults are enabled in EVC (`getEVCAccountInfo` shows empty arrays)

Thank you for your help!

