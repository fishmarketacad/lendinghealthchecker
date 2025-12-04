# Security Guide: Auto Rebalancing Without Private Keys

## ⚠️ CRITICAL: Never Store Private Keys

**Even if encrypted, storing private keys is dangerous:**
- If encrypted, you need the decryption key to use it → defeats the purpose
- Encryption can be broken
- Your server could be compromised
- You become a single point of failure
- Users lose control of their funds

## ✅ Recommended Approaches (No Private Keys Needed)

### Option 1: Signed Transactions (Recommended for Telegram)

**How it works:**
1. Bot detects health factor is low
2. Bot prepares transaction data (what to do)
3. Bot sends transaction data to user via Telegram
4. User signs transaction locally (using MetaMask, etc.)
5. User sends signed transaction back to bot
6. Bot broadcasts signed transaction to blockchain

**Pros:**
- ✅ Private key never leaves user's device
- ✅ User approves every transaction
- ✅ Works with Telegram bot
- ✅ User maintains full control

**Cons:**
- ⚠️ Requires user to be online to sign
- ⚠️ Not fully automated (needs user approval)

### Option 2: WalletConnect Integration

**How it works:**
1. Bot provides a WalletConnect link
2. User connects wallet via web interface
3. Bot requests transaction signatures
4. User approves in their wallet
5. Bot executes transactions

**Pros:**
- ✅ Industry standard
- ✅ Works with all major wallets
- ✅ Secure and user-friendly

**Cons:**
- ⚠️ Requires web interface
- ⚠️ More complex to implement

### Option 3: EIP-712 Structured Signatures

**How it works:**
1. Bot prepares structured message (EIP-712)
2. User signs message with their wallet
3. Bot verifies signature
4. Bot executes transaction (if signature valid)

**Pros:**
- ✅ Very secure
- ✅ User-friendly signing experience
- ✅ Can be automated with user consent

**Cons:**
- ⚠️ Requires smart contract support or relayer
- ⚠️ More complex implementation

## 🚫 If You MUST Store Private Keys (NOT RECOMMENDED)

**Only consider this if:**
- Users explicitly understand the risks
- You implement maximum security
- You have insurance/legal protection
- You're a regulated entity

**Security measures:**
1. **Client-side encryption**: User encrypts with password only they know
2. **Hardware Security Modules (HSM)**: Use AWS KMS, Azure Key Vault, etc.
3. **Multi-signature wallets**: Require multiple approvals
4. **Time-limited access**: Keys expire after set time
5. **Audit logging**: Log all key access
6. **Insurance**: Get coverage for potential losses

**Still risky because:**
- You're a target for hackers
- Legal liability if funds are stolen
- Users may blame you even if it's their fault
- Regulatory issues in many jurisdictions

## 💡 Recommended Implementation: Signed Transactions

See `signed_transaction_example.py` for implementation details.

