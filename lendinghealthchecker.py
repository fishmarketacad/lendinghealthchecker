import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from web3 import Web3
import json
from dotenv import load_dotenv
import asyncio
from typing import Optional, List, Dict
import protocols
import rebalancing

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Protocol configuration - structured for easy multi-chain expansion
PROTOCOL_CONFIG = {
    'neverland': {
        'name': 'Neverland',
        'chain': 'Monad',
        'chain_id': 143,
        'rpc_url': os.environ.get('MONAD_NODE_URL', 'https://rpc.monad.xyz'),
        'pool_address': '0x80F00661b13CC5F6ccd3885bE7b4C9c67545D585',
        'app_url': 'https://app.neverland.money',
        'explorer_url': 'https://monadvision.com',
        'health_factor_method': 'getUserAccountData',  # Method name to call
        'health_factor_index': 5,  # Index in return array (0-indexed)
        'health_factor_divisor': 1e18,  # Divisor to convert to readable format
        'abi': protocols.load_abi('neverland')
    },
    'morpho': {
        'name': 'Morpho',
        'chain': 'Monad',
        'chain_id': 143,  # Morpho Blue deployed on Monad!
        'rpc_url': os.environ.get('MONAD_NODE_URL', 'https://rpc.monad.xyz'),
        # Morpho Blue Core contract on Monad - update with actual Monad address
        'pool_address': os.environ.get('MORPHO_BLUE_ADDRESS', '0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb'),
        'app_url': 'https://app.morpho.org/monad',
        'explorer_url': 'https://monadvision.com',
        'health_factor_method': 'position',  # Morpho uses 'position' method
        'health_factor_index': None,  # Will need custom parsing
        'health_factor_divisor': 1e18,
        'abi': protocols.load_abi('morpho')
    },
    'curvance': {
        'name': 'Curvance',
        'chain': 'Monad',
        'chain_id': 143,
        'rpc_url': os.environ.get('MONAD_NODE_URL', 'https://rpc.monad.xyz'),
        # ProtocolReader contract address on Monad
        'pool_address': os.environ.get('CURVANCE_PROTOCOL_READER_ADDRESS', '0xBF67b967eCcf21f2C196f947b703e874D5dB649d'),
        # MarketManager address - users must provide this in /add command
        # No default - users need to specify their MarketManager address
        'market_manager_address': None,
        'app_url': os.environ.get('CURVANCE_APP_URL', 'https://app.curvance.com'),
        'explorer_url': 'https://monadvision.com',
        'health_factor_method': 'getPositionHealth',  # Use getPositionHealth instead
        'health_factor_index': None,  # Will need custom parsing
        'health_factor_divisor': 1e18,
        'abi': protocols.load_abi('curvance')
    }
    # Future protocols can be added here:
    # 'aave': { ... },
    # 'euler': { ... },
    # etc.
}

# Default protocol
DEFAULT_PROTOCOL = 'neverland'

# Load configuration from environment variables
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
USER_DATA_FILE = os.environ.get('USER_DATA_FILE', 'lendinghealthchatids.json')
CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL', 3600))  # Default to 1 hour

# Initialize Web3 connections for each protocol
protocol_connections = {}
for protocol_id, protocol_info in PROTOCOL_CONFIG.items():
    w3 = Web3(Web3.HTTPProvider(protocol_info['rpc_url']))
    contract = w3.eth.contract(address=protocol_info['pool_address'], abi=protocol_info['abi'])
    protocol_connections[protocol_id] = {
        'w3': w3,
        'contract': contract,
        'protocol': protocol_info
    }

# Debug: Print environment variables
print("TELEGRAM_BOT_TOKEN:", "SET" if TOKEN else "NOT SET")
print("CHECK_INTERVAL:", CHECK_INTERVAL)
print("USER_DATA_FILE:", USER_DATA_FILE)
print("\nSupported Protocols:")
for protocol_id, protocol_info in PROTOCOL_CONFIG.items():
    print(f"  - {protocol_info['name']} ({protocol_id}) on {protocol_info['chain']}")

# Load user data from file
def load_user_data():
    try:
        with open(USER_DATA_FILE, 'r') as f:
            content = f.read().strip()
            if content:
                data = json.loads(content)
                # Migrate old format to new format
                migrated = migrate_user_data(data)
                # Save migrated data if migration occurred
                if migrated != data:
                    with open(USER_DATA_FILE, 'w') as f:
                        json.dump(migrated, f)
                return migrated
            else:
                return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Migrate old data format to new format (supports multiple addresses)
def migrate_user_data(data):
    """Migrate old single-address format to new multi-address format"""
    migrated = {}
    for chat_id, user_info in data.items():
        # Check if it's old format (has 'address' key)
        if 'address' in user_info:
            # Old format: {'threshold': 1.5, 'address': '0x...'}
            threshold = user_info.get('threshold', 1.5)
            address = user_info['address']
            migrated[chat_id] = {
                'default_threshold': threshold,
                'addresses': {
                    address: {'threshold': threshold}
                }
            }
        else:
            # Already new format
            migrated[chat_id] = user_info
    return migrated

# Save user data to file
def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)

# Global variable to store user data
user_data = load_user_data()

# Function to check health factor for a specific protocol
def check_health_factor(address, protocol_id='neverland'):
    """
    Check health factor for an address on a specific protocol.
    
    Args:
        address: User's wallet address
        protocol_id: Protocol identifier ('neverland', 'morpho', etc.)
    
    Returns:
        Health factor as float, or None if error
    """
    if protocol_id not in protocol_connections:
        logger.error(f"Unknown protocol: {protocol_id}")
        return None
    
    conn = protocol_connections[protocol_id]
    protocol_info = conn['protocol']
    contract = conn['contract']
    
    try:
        method_name = protocol_info['health_factor_method']
        
        # Handle different protocol structures
        if protocol_id == 'neverland':
            return protocols.check_neverland_health_factor(address, contract, conn['w3'])
        
        elif protocol_id == 'morpho':
            # Morpho Blue requires market IDs - fetch user positions
            market_id = None
            return protocols.check_morpho_health_factor_all_markets(address, market_id, protocol_info['chain_id'])
        
        elif protocol_id == 'curvance':
            # Pass MarketManager address for getPositionHealth
            # MarketManager should come from user data (stored when /add was called)
            # If not found, will query Central Registry for all MarketManagers
            market_manager = None  # Will be passed from user data in check function
            return protocols.check_curvance_health_factor(address, contract, conn['w3'], market_manager, None)  # None = use Central Registry
        
        else:
            # Generic fallback - try calling the method directly
            method = getattr(contract.functions, method_name)
            result = method(address).call()
            
            # Try to extract health factor based on protocol config
            if protocol_info['health_factor_index'] is not None:
                if isinstance(result, (list, tuple)):
                    health_factor = result[protocol_info['health_factor_index']] / protocol_info['health_factor_divisor']
                else:
                    health_factor = result / protocol_info['health_factor_divisor']
                return health_factor
            else:
                logger.error(f"Protocol {protocol_id} requires custom health factor extraction")
                return None
                
    except Exception as e:
        logger.error(f"Error checking health factor for {address} on {protocol_id}: {e}")
        return None

# Morpho functions are now in protocols.py - import them
get_morpho_user_markets = protocols.get_morpho_user_markets
check_morpho_health_factor_all_markets = protocols.check_morpho_health_factor_all_markets
check_morpho_health_factor_single_market = protocols.check_morpho_health_factor_single_market

# Legacy function for backward compatibility
def check_morpho_health_factor(address, market_id):
    """Legacy function - use check_morpho_health_factor_all_markets instead"""
    if 'morpho' not in protocol_connections:
        return None
    conn = protocol_connections['morpho']
    # Convert address to checksum format
    try:
        address_checksum = conn['w3'].to_checksum_address(address)
    except Exception as e:
        logger.error(f"Invalid address format: {address}, error: {e}")
        return None
    return check_morpho_health_factor_single_market(address_checksum, market_id, conn['contract'], conn['w3'])

# Function to handle the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    protocols_list = "\n".join([f"  • {info['name']} ({pid})" for pid, info in PROTOCOL_CONFIG.items()])
    await update.message.reply_text(
        "Welcome to the Multi-Protocol Lending Health Factor Monitor Bot!\n\n"
        "Supported Protocols:\n" + protocols_list + "\n\n"
        "Here are the available commands:\n"
        "/start - Show this help message\n"
        "/add <protocol> <threshold> <address> [market_id] - Add an address to monitor\n"
        "  Example: /add neverland 1.5 0x1234...\n"
        "  Example: /add morpho 1.5 0x1234...\n"
        "  Example: /add morpho 1.5 0x1234... 0xMarketID (Morpho requires market ID)\n"
        "/list - List all addresses you're monitoring\n"
        "/check - Check health factors for all monitored addresses\n"
        "/repay - Get rebalancing suggestions (withdraw from vaults & repay loans)\n"
        "/remove <address> - Remove an address from monitoring\n"
        "/stop - Stop monitoring all addresses\n"
        "/protocols - List all supported protocols\n\n"
        "You can also simply paste an address to check its health factor (will try all protocols).\n\n"
        "DISCLAIMER: This bot is not officially affiliated with or endorsed by any protocol. "
        "It is an independent tool created for informational purposes only. "
        "The bot is not guaranteed to be always accurate or available. "
        "Users should not rely solely on this bot for making financial decisions."
    )

# Function to handle /add command (adds an address to monitor)
async def add_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Support multiple formats:
    # Old: /add <threshold> <address> (defaults to neverland)
    # New: /add <protocol> <threshold> <address>
    # Morpho: /add morpho <threshold> <address> [market_id] (optional market ID)
    if len(context.args) == 2:
        # Old format: /add <threshold> <address> - default to neverland
        protocol_id = DEFAULT_PROTOCOL
        threshold = context.args[0]
        address = context.args[1]
        market_id = None
    elif len(context.args) == 3:
        # New format: /add <protocol> <threshold> <address>
        protocol_id = context.args[0].lower()
        threshold = context.args[1]
        address = context.args[2]
        market_id = None
    elif len(context.args) == 4:
        # Protocol with optional market/market_manager ID: /add <protocol> <threshold> <address> <market_id>
        protocol_id = context.args[0].lower()
        threshold = context.args[1]
        address = context.args[2]
        if protocol_id == 'morpho':
            market_id = context.args[3]
        elif protocol_id == 'curvance':
            market_id = context.args[3]  # For Curvance, this is market_manager_address (required)
        else:
            market_id = None
    else:
        await update.message.reply_text(
            "Usage: /add <protocol> <threshold> <address> [market_id]\n"
            "Example: /add neverland 1.5 0x1234...\n"
            "Example: /add morpho 1.5 0x1234...\n"
            "Example: /add morpho 1.5 0x1234... 0xMarketID (optional for Morpho)\n"
            "Example: /add curvance 1.5 0x1234... 0xMarketManagerAddress (REQUIRED for Curvance)\n\n"
            f"Supported protocols: {', '.join(PROTOCOL_CONFIG.keys())}"
        )
        return
    
    # For Curvance, MarketManager address is required
    if protocol_id == 'curvance' and len(context.args) < 4:
        await update.message.reply_text(
            "⚠️ Curvance requires a MarketManager address.\n"
            "Usage: /add curvance <threshold> <address> <market_manager_address>\n"
            "Example: /add curvance 1.5 0x1234... 0xd6365555f6a697C7C295bA741100AA644cE28545\n\n"
            "You can find MarketManager addresses in Curvance's documentation."
        )
        return

    # Validate protocol
    if protocol_id not in PROTOCOL_CONFIG:
        await update.message.reply_text(
            f"Unknown protocol: {protocol_id}\n"
            f"Supported protocols: {', '.join(PROTOCOL_CONFIG.keys())}"
        )
        return

    chat_id = str(update.effective_chat.id)
    protocol_info = PROTOCOL_CONFIG[protocol_id]
    
    try:
        threshold = float(threshold)
        address = address.lower()  # Normalize to lowercase
    except ValueError:
        await update.message.reply_text("Invalid threshold. Please enter a number (e.g., 1.5).")
        return

    # Validate address using the protocol's Web3 instance
    conn = protocol_connections[protocol_id]
    if not conn['w3'].is_address(address):
        await update.message.reply_text(f"Invalid {protocol_info['chain']} address. Please try again.")
        return

    # Initialize user data if needed
    if chat_id not in user_data:
        user_data[chat_id] = {
            'default_threshold': threshold,
            'addresses': {}
        }

    # Create unique key: address + protocol (+ market_id for Morpho, + market_manager for Curvance)
    if protocol_id == 'morpho' and market_id:
        address_key = f"{address}:{protocol_id}:{market_id.lower()}"
    elif protocol_id == 'curvance':
        # Curvance requires MarketManager address
        if not market_id:
            await update.message.reply_text(
                "⚠️ Curvance requires a MarketManager address.\n"
                "Usage: /add curvance <threshold> <address> <market_manager_address>\n"
                "Example: /add curvance 1.5 0x1234... 0xd6365555f6a697C7C295bA741100AA644cE28545"
            )
            return
        address_key = f"{address}:{protocol_id}:{market_id.lower()}"
    else:
        address_key = f"{address}:{protocol_id}"
    
    # Add or update address
    if address_key in user_data[chat_id]['addresses']:
        user_data[chat_id]['addresses'][address_key]['threshold'] = threshold
        message = f"✅ Updated threshold for {address} on {protocol_info['name']} to {threshold}"
    else:
        address_data = {
            'threshold': threshold,
            'protocol': protocol_id,
            'address': address
        }
        if protocol_id == 'morpho' and market_id:
            # Validate market ID format (should be bytes32 = 66 chars: 0x + 64 hex)
            market_id_lower = market_id.lower()
            if not market_id_lower.startswith('0x') or len(market_id_lower) != 66:
                await update.message.reply_text(
                    f"⚠️ Invalid market ID format: {market_id}\n"
                    "Market ID should be 66 characters (0x + 64 hex chars).\n"
                    "Example: 0x409f2824aee2d8391d4a5924935e13312e157055e262b923b60c9dcb47e6311d\n\n"
                    "You can find market IDs from Morpho app URLs or use /add without market ID to auto-discover."
                )
                return
            address_data['market_id'] = market_id_lower
        elif protocol_id == 'curvance':
            # Curvance requires MarketManager address
            if not market_id:
                await update.message.reply_text(
                    "⚠️ Curvance requires a MarketManager address.\n"
                    "Usage: /add curvance <threshold> <address> <market_manager_address>\n"
                    "Example: /add curvance 1.5 0x1234... 0xd6365555f6a697C7C295bA741100AA644cE28545"
                )
                return
            # Validate MarketManager address format
            market_manager_lower = market_id.lower()
            if not market_manager_lower.startswith('0x') or len(market_manager_lower) != 42:
                await update.message.reply_text(
                    f"⚠️ Invalid MarketManager address format: {market_id}\n"
                    "MarketManager address should be 42 characters (0x + 40 hex chars).\n"
                    "Example: 0xd6365555f6a697C7C295bA741100AA644cE28545\n\n"
                    "You can find MarketManager addresses in Curvance's documentation."
                )
                return
            address_data['market_manager_address'] = market_manager_lower
        user_data[chat_id]['addresses'][address_key] = address_data
        user_data[chat_id]['default_threshold'] = threshold  # Update default
        message = f"✅ Added {address} on {protocol_info['name']} with threshold {threshold}"
        if protocol_id == 'morpho' and market_id:
            message += f"\nMarket ID: {market_id}"
        elif protocol_id == 'curvance' and market_id:
            message += f"\nMarketManager: {market_id}"

    save_user_data(user_data)
    await update.message.reply_text(message)
    
    # Immediately check and notify (saves user a step!)
    if protocol_id == 'morpho':
        health_factor = check_morpho_health_factor_all_markets(address, market_id, protocol_info['chain_id'])
    else:
        health_factor = check_health_factor(address, protocol_id)
    
    if health_factor is not None:
        status_emoji = "✅" if health_factor >= threshold else "⚠️"
        await update.message.reply_text(
            f"{status_emoji} Current health factor: {health_factor:.4f}\n"
            f"Threshold: {threshold}\n"
            f"View on explorer: {protocol_info['explorer_url']}/address/{address}"
        )
    else:
        if protocol_id == 'morpho' and not market_id:
            await update.message.reply_text(
                "⚠️ Unable to fetch health factor automatically.\n"
                "Morpho requires market ID. If you know your market ID, use:\n"
                f"/add morpho {threshold} {address} <market_id>"
            )
        else:
            await update.message.reply_text(
                "⚠️ Unable to fetch health factor. Please try /check later."
            )

# Function to handle /list command
async def list_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    if chat_id not in user_data or not user_data[chat_id].get('addresses'):
        await update.message.reply_text("You are not currently monitoring any addresses.\nUse /add <protocol> <threshold> <address> to start monitoring.")
        return

    addresses = user_data[chat_id]['addresses']
    message = f"📋 You are monitoring {len(addresses)} address(es):\n\n"
    
    for idx, (address_key, info) in enumerate(addresses.items(), 1):
        threshold = info.get('threshold', user_data[chat_id].get('default_threshold', 1.5))
        protocol_id = info.get('protocol', DEFAULT_PROTOCOL)
        address = info.get('address', address_key.split(':')[0])
        protocol_info = PROTOCOL_CONFIG.get(protocol_id, PROTOCOL_CONFIG[DEFAULT_PROTOCOL])
        
        # For Morpho, check if market_id is stored
        market_id = info.get('market_id') if protocol_id == 'morpho' else None
        
        if protocol_id == 'morpho':
            health_factor = check_morpho_health_factor_all_markets(address, market_id, protocol_info['chain_id'])
        else:
            health_factor = check_health_factor(address, protocol_id)
            
        if health_factor is not None:
            status = "🟢" if health_factor >= threshold else "🔴"
            message += f"{idx}. {status} {address}\n"
            message += f"   Protocol: {protocol_info['name']}\n"
            if protocol_id == 'morpho' and market_id:
                message += f"   Market ID: {market_id}\n"
            message += f"   Threshold: {threshold}, Current: {health_factor:.4f}\n\n"
        else:
            message += f"{idx}. ⚠️ {address}\n"
            message += f"   Protocol: {protocol_info['name']}\n"
            if protocol_id == 'morpho':
                if not market_id:
                    message += f"   Note: Morpho requires market ID. Use /add morpho <threshold> <address> <market_id>\n"
                else:
                    message += f"   Market ID: {market_id}\n"
            message += f"   Threshold: {threshold}, Status: Unable to fetch\n\n"
    
    await update.message.reply_text(message)

# Function to handle /remove command
async def remove_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Support: /remove <address> or /remove <address> <market_id> (for Morpho)
    if len(context.args) < 1 or len(context.args) > 2:
        await update.message.reply_text(
            "Usage: /remove <address> [market_id]\n"
            "Example: /remove 0x1234...\n"
            "Example: /remove 0x1234... 0xMarketID (for Morpho with specific market)"
        )
        return

    chat_id = str(update.effective_chat.id)
    address = context.args[0].lower()
    market_id = context.args[1].lower() if len(context.args) == 2 else None

    if chat_id not in user_data or 'addresses' not in user_data[chat_id]:
        await update.message.reply_text("You are not monitoring any addresses.")
        return

    # Find matching address keys
    found_keys = []
    for key, info in user_data[chat_id]['addresses'].items():
        info_address = info.get('address', key.split(':')[0]).lower()
        if info_address == address:
            # If market_id specified, only match that specific market
            if market_id:
                info_market_id = info.get('market_id', '').lower()
                if info_market_id == market_id:
                    found_keys.append(key)
            else:
                # No market_id specified, match all entries for this address
                found_keys.append(key)
    
    if not found_keys:
        if market_id:
            await update.message.reply_text(
                f"Address {address} with market ID {market_id} is not being monitored.\n"
                "Use /list to see all monitored addresses."
            )
        else:
            await update.message.reply_text(
                f"Address {address} is not being monitored.\n"
                "Use /list to see all monitored addresses."
            )
        return

    # Remove all matching entries
    removed_count = 0
    protocols_removed = set()
    for key in found_keys:
        protocol_id = user_data[chat_id]['addresses'][key].get('protocol', DEFAULT_PROTOCOL)
        protocols_removed.add(protocol_id)
        del user_data[chat_id]['addresses'][key]
        removed_count += 1
    
    # If no addresses left, remove user entirely
    if not user_data[chat_id]['addresses']:
        del user_data[chat_id]
        message = f"✅ Removed {removed_count} address(es). All monitoring stopped."
    else:
        save_user_data(user_data)
        protocol_names = [PROTOCOL_CONFIG.get(p, {}).get('name', p) for p in protocols_removed]
        if market_id:
            message = f"✅ Removed {address} (market: {market_id[:20]}...) from {', '.join(protocol_names)} monitoring."
        else:
            message = f"✅ Removed {removed_count} entry/entries for {address} from {', '.join(protocol_names)} monitoring."

    save_user_data(user_data)
    await update.message.reply_text(message)

# Function to handle /check command
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    if chat_id not in user_data or not user_data[chat_id].get('addresses'):
        await update.message.reply_text("You are not currently monitoring any addresses.\nUse /add <protocol> <threshold> <address> to start monitoring.")
        return

    addresses = user_data[chat_id]['addresses']
    
    # Group entries by address
    address_groups = {}
    for address_key, info in addresses.items():
        address = info.get('address', address_key.split(':')[0])
        if address not in address_groups:
            address_groups[address] = []
        address_groups[address].append((address_key, info))
    
    messages = []
    
    for address, entries in address_groups.items():
        address_message = f"For {address}:\n"
        
        # Group entries by protocol
        protocol_groups = {}
        for address_key, info in entries:
            protocol_id = info.get('protocol', DEFAULT_PROTOCOL)
            if protocol_id not in protocol_groups:
                protocol_groups[protocol_id] = []
            protocol_groups[protocol_id].append((address_key, info))
        
        for protocol_id, protocol_entries in protocol_groups.items():
            try:
                protocol_info = PROTOCOL_CONFIG.get(protocol_id, PROTOCOL_CONFIG[DEFAULT_PROTOCOL])
                address_message += f"\n{protocol_info['name']} protocol:\n"
                
                # For Morpho, get all markets for this address
                if protocol_id == 'morpho':
                    markets_data = get_morpho_user_markets(address, protocol_info['chain_id'])
                    market_map = {m['id'].lower(): m for m in markets_data} if markets_data else {}
                
                # Special handling for Morpho: if no market_id specified, show ALL markets
                if protocol_id == 'morpho' and markets_data:
                    # Check if any entry has a specific market_id
                    has_specific_market = any(info.get('market_id') for _, info in protocol_entries)
                    
                    if not has_specific_market:
                        # No specific market_id - show ALL markets
                        threshold = protocol_entries[0][1].get('threshold', user_data[chat_id].get('default_threshold', 1.5)) if protocol_entries else user_data[chat_id].get('default_threshold', 1.5)
                        threshold_str = f"{threshold:.3f}".rstrip('0').rstrip('.')
                        
                        for market in markets_data:
                            hf = market.get('healthFactor')
                            if hf is not None:
                                try:
                                    health_factor = float(hf)
                                    status = "⚠️ " if health_factor < threshold else ""
                                    liquidation_drop_pct = (1 - (1 / health_factor)) * 100 if health_factor > 0 else 0
                                    market_name = market['name'].upper()
                                    market_url = f"https://app.morpho.org/monad/market/{market['id']}/{market['name']}?subTab=yourPosition"
                                    address_message += f"{status}[{market_name}]({market_url}):\nThreshold: {threshold_str}, Current Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation)\n"
                                except (ValueError, TypeError):
                                    continue
                        # Skip the normal loop for Morpho when showing all markets
                        continue
                
                # Normal processing for other protocols or Morpho with specific market_id
                for address_key, info in protocol_entries:
                    threshold = info.get('threshold', user_data[chat_id].get('default_threshold', 1.5))
                    market_id = info.get('market_id') if protocol_id == 'morpho' else None
                    
                    if protocol_id == 'morpho':
                        health_factor = check_morpho_health_factor_all_markets(address, market_id, protocol_info['chain_id'])
                        # Get market info
                        if market_id and market_id.lower() in market_map:
                            market_info = market_map[market_id.lower()]
                        elif markets_data:
                            # If no market_id specified, use worst (lowest HF) market
                            market_info = min(markets_data, key=lambda x: x.get('healthFactor', float('inf')))
                        else:
                            market_info = None
                    elif protocol_id == 'curvance':
                        market_manager = info.get('market_manager_address')
                        conn = protocol_connections[protocol_id]
                        # Pass None for known_market_managers to use Central Registry
                        health_factor = protocols.check_curvance_health_factor(
                            address,
                            conn['contract'],
                            conn['w3'],
                            market_manager,  # User-specified MarketManager (if provided)
                            None  # None = query Central Registry for all MarketManagers
                        )
                        market_info = None
                    else:
                        health_factor = check_health_factor(address, protocol_id)
                        market_info = None
                
                if health_factor is not None:
                    status = "⚠️ " if health_factor < threshold else ""
                    
                    # Calculate liquidation percentage: if HF = 1.5, collateral can drop by (1 - 1/1.5) = 33.3%
                    liquidation_drop_pct = (1 - (1 / health_factor)) * 100 if health_factor > 0 else 0
                    
                    # Format threshold to preserve user's input format (remove trailing zeros, max 3 decimals)
                    threshold_str = f"{threshold:.3f}".rstrip('0').rstrip('.')
                    
                    # Display health factors consistently across all protocols
                    # All protocols use the same format: health factor where 1.0 = liquidation threshold
                    # Threshold 1.5 means the same thing for all protocols: warn when health drops below 1.5x liquidation threshold
                    if protocol_id == 'morpho' and market_info and market_info.get('name'):
                        market_name = market_info['name'].upper()
                        market_url = f"https://app.morpho.org/monad/market/{market_info['id']}/{market_info['name']}?subTab=yourPosition"
                        address_message += f"{status}[{market_name}]({market_url}):\nThreshold: {threshold_str}, Current Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation)\n"
                    elif protocol_id == 'curvance':
                        # Curvance: same format as other protocols for consistency
                        market_manager_address = info.get('market_manager_address')
                        if market_manager_address:
                            market_url = f"{protocol_info.get('app_url', '')}/market/{market_manager_address}"
                            address_message += f"{status}[Curvance Market]({market_url}):\nThreshold: {threshold_str}, Current Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation)\n"
                        else:
                            protocol_url = protocol_info.get('app_url', '')
                            if protocol_url:
                                address_message += f"{status}[{protocol_info['name']}]({protocol_url}):\nThreshold: {threshold_str}, Current Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation)\n"
                            else:
                                address_message += f"{status}{protocol_info['name']}:\nThreshold: {threshold_str}, Current Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation)\n"
                    else:
                        # Add hyperlink for Neverland and other protocols
                        protocol_url = protocol_info.get('app_url', '')
                        if protocol_url:
                            address_message += f"{status}[{protocol_info['name']}]({protocol_url}):\nThreshold: {threshold_str}, Current Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation)\n"
                        else:
                            address_message += f"{status}{protocol_info['name']}:\nThreshold: {threshold_str}, Current Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation)\n"
                else:
                    if protocol_id == 'morpho':
                        if market_id:
                            address_message += f"⚠️ Market {market_id[:20]}...: Unable to fetch\n"
                        else:
                            address_message += f"⚠️ Unable to fetch\n"
                    else:
                        address_message += f"⚠️ Unable to fetch\n"
            except Exception as e:
                logger.error(f"Error processing protocol {protocol_id} for address {address}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                protocol_info = PROTOCOL_CONFIG.get(protocol_id, PROTOCOL_CONFIG[DEFAULT_PROTOCOL])
                address_message += f"\n{protocol_info['name']} protocol:\n"
                address_message += f"⚠️ Error checking {protocol_info.get('name', protocol_id)}: {str(e)[:100]}\n"
        
        messages.append(address_message)
    
    final_message = "\n".join(messages)
    await update.message.reply_text(final_message, parse_mode='Markdown', disable_web_page_preview=True)

# Function to handle /protocols command
async def list_protocols(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = "📚 Supported Protocols:\n\n"
    for protocol_id, protocol_info in PROTOCOL_CONFIG.items():
        message += f"• {protocol_info['name']} ({protocol_id})\n"
        message += f"  Chain: {protocol_info['chain']}\n"
        message += f"  App: {protocol_info['app_url']}\n\n"
    await update.message.reply_text(message)

# Function to handle /repay command (manual rebalancing suggestions)
async def repay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate rebalancing suggestions for user's positions."""
    chat_id = str(update.effective_chat.id)
    if chat_id not in user_data or not user_data[chat_id].get('addresses'):
        await update.message.reply_text(
            "You are not currently monitoring any addresses.\n"
            "Use /add <protocol> <threshold> <address> to start monitoring."
        )
        return
    
    addresses = user_data[chat_id]['addresses']
    messages_sent = 0
    
    # Group entries by address
    address_groups = {}
    for address_key, info in addresses.items():
        address = info.get('address', address_key.split(':')[0])
        if address not in address_groups:
            address_groups[address] = []
        address_groups[address].append((address_key, info))
    
    for address, entries in address_groups.items():
        # Group by protocol
        protocol_groups = {}
        for address_key, info in entries:
            protocol_id = info.get('protocol', DEFAULT_PROTOCOL)
            if protocol_id not in protocol_groups:
                protocol_groups[protocol_id] = []
            protocol_groups[protocol_id].append((address_key, info))
        
        for protocol_id, protocol_entries in protocol_groups.items():
            protocol_info = PROTOCOL_CONFIG.get(protocol_id, PROTOCOL_CONFIG[DEFAULT_PROTOCOL])
            
            # Find worst HF market
            worst_hf = float('inf')
            worst_market_id = None
            worst_threshold = 1.5
            
            for address_key, info in protocol_entries:
                threshold = info.get('threshold', user_data[chat_id].get('default_threshold', 1.5))
                market_id = info.get('market_id') if protocol_id == 'morpho' else None
                
                if protocol_id == 'morpho':
                    health_factor = check_morpho_health_factor_all_markets(address, market_id, protocol_info['chain_id'])
                else:
                    health_factor = check_health_factor(address, protocol_id)
                
                if health_factor is not None and health_factor < worst_hf:
                    worst_hf = health_factor
                    worst_market_id = market_id
                    worst_threshold = threshold
            
            # Generate rebalancing message for worst position
            if worst_hf < float('inf'):
                rebalancing_msg = rebalancing.generate_rebalancing_message(
                    address=address,
                    protocol_id=protocol_id,
                    market_id=worst_market_id,
                    current_hf=worst_hf,
                    threshold=worst_threshold,
                    chain_id=protocol_info.get('chain_id', 143)
                )
                
                if rebalancing_msg:
                    await update.message.reply_text(
                        rebalancing_msg,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    messages_sent += 1
    
    if messages_sent == 0:
        await update.message.reply_text(
            "No positions found that need rebalancing, or unable to generate suggestions.\n"
            "Use /check to see current health factors."
        )

# Function to handle /stop command
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    if chat_id in user_data:
        del user_data[chat_id]
        save_user_data(user_data)
        await update.message.reply_text("Monitoring stopped.")
    else:
        await update.message.reply_text("You were not monitoring any address.")

# Function to handle direct address input
async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    address = update.message.text.strip()
    
    # Try to validate address on any protocol
    valid_protocols = []
    for protocol_id, conn in protocol_connections.items():
        if conn['w3'].is_address(address):
            valid_protocols.append(protocol_id)
    
    if not valid_protocols:
        await update.message.reply_text("Invalid address format. Please try again.")
        return
    
    # Try to get health factor from all valid protocols
    results = []
    for protocol_id in valid_protocols:
        protocol_info = PROTOCOL_CONFIG[protocol_id]
        health_factor = check_health_factor(address, protocol_id)
        if health_factor is not None:
            results.append({
                'protocol': protocol_info['name'],
                'health_factor': health_factor,
                'explorer': protocol_info['explorer_url']
            })
    
    if results:
        message = f"Health factors for {address}:\n\n"
        for result in results:
            message += f"{result['protocol']}: {result['health_factor']:.4f}\n"
            message += f"Explorer: {result['explorer']}/address/{address}\n\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("Unable to fetch health factor from any protocol. Please try again later.")
    
    logger.info(f"Health factor check requested for address: {address}")

# Function to check health factor and notify user for all addresses
async def check_and_notify(context: ContextTypes.DEFAULT_TYPE, chat_id: str) -> None:
    if chat_id not in user_data or not user_data[chat_id].get('addresses'):
        return

    addresses = user_data[chat_id]['addresses']
    alerts = []

    for address_key, info in addresses.items():
        threshold = info.get('threshold', user_data[chat_id].get('default_threshold', 1.5))
        protocol_id = info.get('protocol', DEFAULT_PROTOCOL)
        address = info.get('address', address_key.split(':')[0])
        protocol_info = PROTOCOL_CONFIG.get(protocol_id, PROTOCOL_CONFIG[DEFAULT_PROTOCOL])
        
        # For Morpho, check if market_id is stored
        market_id = info.get('market_id') if protocol_id == 'morpho' else None
        
        if protocol_id == 'morpho':
            health_factor = check_morpho_health_factor_all_markets(address, market_id, protocol_info['chain_id'])
        else:
            health_factor = check_health_factor(address, protocol_id)

        if health_factor is not None:
            if health_factor < threshold:
                alerts.append({
                    'address': address,
                    'health_factor': health_factor,
                    'threshold': threshold,
                    'protocol': protocol_info,
                    'market_id': market_id if protocol_id == 'morpho' else None
                })
        # Note: We don't send alerts for fetch failures to avoid spam

    # Send alerts if any
    if alerts:
        for alert in alerts:
            # Generate rebalancing message with vault suggestions
            rebalancing_msg = rebalancing.generate_rebalancing_message(
                address=alert['address'],
                protocol_id=alert['protocol'].get('name', '').lower(),
                market_id=alert.get('market_id'),
                current_hf=alert['health_factor'],
                threshold=alert['threshold'],
                chain_id=alert['protocol'].get('chain_id', 143)
            )
            
            if rebalancing_msg:
                # Send rebalancing suggestions
                await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=rebalancing_msg,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                # Fallback to simple alert if rebalancing message generation fails
                message = f"⚠️ Alert: Health factor for {alert['address']} on {alert['protocol']['name']} is {alert['health_factor']:.4f}, which is below your threshold of {alert['threshold']}!\n\n"
                if alert.get('market_id'):
                    message += f"Market ID: {alert['market_id']}\n"
                message += f"Check your position: {alert['protocol']['app_url']}\n"
                message += f"View on explorer: {alert['protocol']['explorer_url']}/address/{alert['address']}"
                await context.bot.send_message(chat_id=int(chat_id), text=message)

# Function to periodically check health factors
async def periodic_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    for chat_id in user_data:
        await check_and_notify(context, chat_id)

def main() -> None:
    if not TOKEN:
        logger.error("No bot token provided. Please set the TELEGRAM_BOT_TOKEN environment variable.")
        return

    # Verify connection to blockchains
    for protocol_id, conn in protocol_connections.items():
        protocol_info = conn['protocol']
        w3 = conn['w3']
        try:
            chain_id = w3.eth.chain_id
            logger.info(f"Connected to {protocol_info['name']} on {protocol_info['chain']} (Chain ID: {chain_id})")
            if chain_id != protocol_info['chain_id']:
                logger.warning(f"{protocol_info['name']}: Expected Chain ID {protocol_info['chain_id']}, but got {chain_id}. Please verify RPC endpoint.")
        except Exception as e:
            logger.error(f"Failed to connect to {protocol_info['name']} blockchain: {e}")
            # Don't return - continue with other protocols

    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_address))
    application.add_handler(CommandHandler("list", list_addresses))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("remove", remove_address))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("protocols", list_protocols))
    application.add_handler(CommandHandler("repay", repay))
    # Keep /monitor for backward compatibility (maps to /add)
    application.add_handler(CommandHandler("monitor", add_address))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address))

    # Set up periodic task
    # Use CHECK_INTERVAL for first run to avoid running immediately on startup
    # This prevents duplicate messages when bot restarts
    job_queue = application.job_queue
    job_queue.run_repeating(periodic_check, interval=CHECK_INTERVAL, first=CHECK_INTERVAL)

    logger.info("Multi-Protocol Lending Health Monitor Bot started. Polling for updates...")
    for protocol_id, protocol_info in PROTOCOL_CONFIG.items():
        logger.info(f"  - {protocol_info['name']} ({protocol_id}) on {protocol_info['chain']}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()