"""
Example: Auto Rebalancing with Signed Transactions (No Private Keys Stored)

This approach allows users to sign transactions locally and send them to the bot.
The bot never sees or stores private keys.
"""

from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
import json

# Example: How to prepare a transaction for user to sign
def prepare_rebalance_transaction(user_address, pool_contract_address, action_type):
    """
    Prepare transaction data for user to sign.
    This would be called when health factor is low.
    
    action_type: 'repay', 'deposit_collateral', 'withdraw', etc.
    """
    
    # Example: Repay debt transaction
    pool_abi = [
        {
            "inputs": [
                {"name": "asset", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "rateMode", "type": "uint256"},
                {"name": "onBehalfOf", "type": "address"}
            ],
            "name": "repay",
            "type": "function"
        }
    ]
    
    # This is just the function call data - user will sign this
    # In practice, you'd need to determine which asset to repay, how much, etc.
    
    return {
        "to": pool_contract_address,
        "data": "0x...",  # Encoded function call
        "value": 0,
        "gas": 200000,
        "gasPrice": 0,  # Will be set by user's wallet
        "nonce": 0,  # Will be set by user's wallet
        "chainId": 143  # Monad
    }

# Example: How user would sign (this happens on THEIR device, not your bot)
def user_signs_transaction_locally(private_key, transaction_data):
    """
    This function runs on USER'S device (not your bot server).
    User signs transaction with their private key locally.
    """
    account = Account.from_key(private_key)
    signed_txn = account.sign_transaction(transaction_data)
    return signed_txn.rawTransaction.hex()

# Example: Bot receives signed transaction and broadcasts it
def bot_broadcasts_signed_transaction(signed_tx_hex, w3):
    """
    Bot receives signed transaction from user and broadcasts it.
    Bot never sees the private key.
    """
    try:
        tx_hash = w3.eth.send_raw_transaction(signed_tx_hex)
        return tx_hash.hex()
    except Exception as e:
        return f"Error: {e}"

# Example: EIP-712 Structured Signing (More User-Friendly)
def prepare_eip712_message(user_address, action_data):
    """
    Prepare EIP-712 structured message for user to sign.
    This is more user-friendly than raw transaction signing.
    """
    domain = {
        "name": "NeverlandRebalancer",
        "version": "1",
        "chainId": 143,
        "verifyingContract": "0x..."  # Your contract address
    }
    
    message = {
        "user": user_address,
        "action": action_data["action"],
        "amount": action_data["amount"],
        "nonce": action_data["nonce"],
        "deadline": action_data["deadline"]
    }
    
    return domain, message

# User signs EIP-712 message locally, sends signature to bot
# Bot verifies signature and executes action

