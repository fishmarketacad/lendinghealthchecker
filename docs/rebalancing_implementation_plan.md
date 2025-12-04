# Implementation Plan: Auto Rebalancing Feature

## Phase 1: Alert with Action Suggestions (Safest)

**What it does:**
- Bot detects low health factor
- Bot suggests specific actions (e.g., "Repay 100 USDC")
- Bot provides transaction data
- User signs transaction in their wallet
- User sends signed transaction back to bot
- Bot broadcasts transaction

**Implementation:**
1. Add `/enable_rebalancing` command
2. When health factor drops, send alert with:
   - Suggested action
   - Transaction data (ready to sign)
   - Instructions on how to sign
3. Add `/sign_transaction <signed_tx>` command
4. Bot broadcasts signed transaction

**Pros:**
- ✅ No private keys stored
- ✅ User maintains control
- ✅ Can be semi-automated

## Phase 2: Web Interface with WalletConnect

**What it does:**
- Bot provides link to web interface
- User connects wallet via WalletConnect
- Web interface shows rebalancing options
- User approves transactions in wallet
- Bot executes approved transactions

**Implementation:**
1. Create simple web page
2. Integrate WalletConnect
3. Bot sends link: "Click here to rebalance: https://..."
4. User connects wallet and approves
5. Web interface calls bot API to execute

**Pros:**
- ✅ Industry standard
- ✅ User-friendly
- ✅ Secure

## Phase 3: Smart Contract with EIP-712 Signatures (Advanced)

**What it does:**
- Deploy smart contract that executes rebalancing
- Users sign EIP-712 messages approving actions
- Bot verifies signatures and executes via contract
- Can be fully automated with user consent

**Implementation:**
1. Deploy rebalancing contract
2. Users sign approval messages
3. Bot monitors health factors
4. Bot executes approved actions via contract

**Pros:**
- ✅ Fully automated (with consent)
- ✅ Very secure
- ✅ Transparent on-chain

**Cons:**
- ⚠️ Requires smart contract deployment
- ⚠️ More complex

## Recommended: Start with Phase 1

This gives users control while making rebalancing easier. No private keys needed!

