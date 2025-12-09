# Euler V2 Explained - Beginner's Guide

## Overview

Euler V2 is a lending protocol where you can:
- **Supply** assets to earn interest
- **Borrow** assets using your supplied assets as collateral
- **Track** your health factor to avoid liquidation

## Key Concepts

### 1. **EVC (Euler Vault Controller)**

Think of EVC as the "manager" that coordinates all your positions across different vaults.

- **EVC-enabled vaults**: Vaults that you've explicitly "enabled" in the EVC
- **Isolated vaults**: Vaults that exist but aren't enabled in EVC

**Why enable vaults?**
- When you enable a vault as a **controller**, you can borrow from it
- When you enable a vault as **collateral**, you can use assets in that vault as collateral for borrowing

### 2. **Controller Vault vs Collateral Vault**

In Euler V2, borrowing works differently than simple protocols:

**Traditional Lending:**
```
You deposit ETH → You borrow USDC against ETH
(Everything in one place)
```

**Euler V2:**
```
You deposit assets in Vault A (collateral vault)
You borrow assets from Vault B (controller vault)
```

**Example:**
- You have `shMON` tokens in vault `0x28bD4F19C812CBF9e33A206f87125f14E65dc8aA` (collateral)
- You borrow `AUSD` from vault `0x6E06ce28...` (controller)
- The **controller vault** is where you borrowed from
- The **collateral vault** is where your collateral is

### 3. **Health Score (Health Factor)**

Health Score = `collateralValueLiquidation / liabilityValueLiquidation`

- **> 1.0**: Safe (you have more collateral than debt)
- **< 1.0**: At risk of liquidation
- **= 1.0**: Exactly at liquidation threshold

**Important**: According to Euler docs, health score is calculated from the **controller vault** (where you borrowed), not the collateral vault.

## Your Current Situation

Based on the test results:

```
Vault: 0x28bD4F19C812CBF9e33A206f87125f14E65dc8aA (eWMON-5)
- Has collateral: 64.27 tokens
- Has NO debt in this vault (borrowed = 0)
- isController = False
- isCollateral = False
```

**What this means:**
- You have assets deposited in this vault
- But you're NOT borrowing from this vault
- You're NOT using this vault as collateral (it's not enabled in EVC)
- The debt must be in a different vault (the controller vault)

## How to Find Your Controller Vault

### Method 1: Check All Vaults Where You Have Debt

The script already tries to do this, but here's what to look for:

```python
# For each vault, check:
account_info = account_lens.getAccountInfo(your_address, vault_address)
vault_info = account_info[1]  # VaultAccountInfo

if vault_info[7] > 0:  # borrowed > 0
    if vault_info[13] == True:  # isController == True
        # This is your controller vault!
        # Health score should be here
```

### Method 2: Check Recognized Collaterals

Your vault (`eWMON-5`) recognizes these as collaterals:
- `eshMON-1` (0x6661a2b4...)
- `eAUSD-6` (0x6E06ce28...)

**Try this**: Query each of these vaults to see if you have debt there:

```python
# Check eshMON-1 vault
account_info = account_lens.getAccountInfo(your_address, "0x6661a2b4...")
# Check if borrowed > 0 or isController == True

# Check eAUSD-6 vault  
account_info = account_lens.getAccountInfo(your_address, "0x6E06ce28...")
# Check if borrowed > 0 or isController == True
```

### Method 3: Enable Vaults in EVC

If you haven't enabled any vaults in EVC, that might be why the liquidity query fails.

**To enable a vault:**
1. Go to Euler's frontend/app
2. Find the vault you want to use
3. Click "Enable as Controller" or "Enable as Collateral"
4. Sign the transaction

**After enabling:**
- The vault will appear in `getAccountEnabledVaultsInfo`
- Liquidity queries should work
- Health score should be accessible

## What Information Can Help Me?

To help debug this, you could provide:

1. **From Euler's frontend/app:**
   - Which vault shows your debt? (the controller vault)
   - Which vault shows your collateral? (the collateral vault)
   - What's the health score shown in the UI?
   - Are any vaults "enabled" in your account settings?

2. **From blockchain:**
   - Transaction hashes of when you:
     - Deposited collateral
     - Borrowed assets
     - Enabled any vaults

3. **From the UI screenshot:**
   - The position shows "Isolated shMON-WMON-AUSD"
   - Health score: 1.14
   - Debt: $1.60
   - This suggests there IS a controller vault somewhere

## Updated Script Features

The `eulertest.py` script now:

1. ✅ Checks EVC-enabled vaults (via `getAccountEnabledVaultsInfo`)
2. ✅ Checks isolated vaults (via `getAccountInfo`)
3. ✅ Shows vault information (name, symbol)
4. ✅ Shows recognized collaterals for each vault
5. ✅ Attempts to find controller vaults
6. ✅ Shows EVC account info (enabled controllers/collaterals)

## Next Steps

1. **Run the script** to see what it finds:
   ```bash
   python eulertest.py 0xf79c108fe2103f52c21c4063153605e351cb3d4d
   ```

2. **Check Euler's frontend** to see:
   - Which vault is listed as your "controller"
   - Which vaults are "enabled"

3. **If you find the controller vault address**, add it to `KNOWN_EULER_ISOLATED_VAULTS` in the script

4. **If vaults need to be enabled**, do that first, then the script should work

## Common Questions

**Q: Why does liquidity query fail?**
A: Likely because:
- The vault isn't enabled in EVC
- We're querying the wrong vault (should query controller, not collateral)
- Isolated vaults work differently

**Q: What's the difference between EVC-enabled and isolated?**
A: 
- **EVC-enabled**: You've explicitly enabled it → appears in `getAccountEnabledVaultsInfo`
- **Isolated**: Exists but not enabled → must query individually with `getAccountInfo`

**Q: Why is borrowed=0 in the collateral vault?**
A: That's normal! You deposit collateral in one vault, but borrow from a different vault (the controller).

**Q: How do I know which vault is the controller?**
A: Look for:
- `borrowed > 0` AND `isController == True`
- Or check Euler's frontend - it should show which vault you borrowed from

