# How to Find Your Controller Vault in Euler V2

## The Problem

Your Euler UI shows:
- Health Score: 1.14
- Debt: $1.60
- Position: "Isolated shMON-WMON-AUSD"

But the script can't find where the debt is stored.

## Why This Happens

In Euler V2:
- **Collateral** is stored in one vault (where you deposit)
- **Debt** is stored in a different vault (the controller vault, where you borrow from)
- Health score is calculated from the **controller vault**, not the collateral vault

## How to Find It

### Method 1: Check Euler's Frontend (Easiest)

1. Go to https://app.euler.finance/ (on Monad network)
2. Connect your wallet
3. Look at your position details
4. Find which vault shows:
   - Your borrow amount
   - The health score
   - "Controller" or "Borrow" label

That vault address is your controller vault!

### Method 2: Check Transaction History

1. Go to your wallet (MetaMask, etc.)
2. Find the transaction where you borrowed
3. Look at the contract address you interacted with
4. That's likely your controller vault

### Method 3: Check All Known Vaults

The script now checks these vaults:
- `0x28bD4F19C812CBF9e33A206f87125f14E65dc8aA` (eWMON-5) - has 64.27 tokens
- `0xb6A4db1FeF7831F65827d9aF2Cb1e69F764eC123` (eshMON-2) - has 25.06 tokens
- `0x7B4BcAEAC5Eb67ae947903F24BBa660eE06A5231` - has 64.27 tokens
- `0x5792753b66Eb5213E416755546abBcC1AEF1008A` - no tokens

But none show debt yet. We need to find more vaults to check.

### Method 4: Query All Vaults (Advanced)

If you know all vault addresses on Monad, we can check them all. But that requires:
- A list of all Euler vault addresses on Monad
- Or querying a registry/governance contract

## About "Enabling" Vaults

**You don't need to manually enable vaults in settings!**

In Euler V2:
- Enabling happens **automatically** when you interact with a vault
- Or it happens when you explicitly call the EVC `enableController` or `enableCollateral` functions
- There's no "settings" page for this - it's done via transactions

**If a vault isn't enabled:**
- It won't appear in `getAccountEnabledVaultsInfo`
- But you can still query it with `getAccountInfo(account, vault)`
- Liquidity queries might fail (which is what we're seeing)

## What to Do Next

1. **Check Euler's frontend** - Find the vault address that shows your debt
2. **Share that address** - I'll add it to the script
3. **Or check transaction history** - Find where you borrowed from

Once we have the controller vault address, the script will be able to show your health score!

## Current Status

✅ Script checks multiple vaults
✅ Script shows vault info and recognized collaterals  
✅ Script automatically checks recognized collateral vaults
❌ Still haven't found the controller vault with debt

The debt exists (UI shows it), but we need the correct vault address to query it.

