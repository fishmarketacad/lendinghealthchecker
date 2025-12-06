import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from web3 import Web3
import json
from dotenv import load_dotenv
import asyncio
from typing import Optional, List, Dict
from time import time
import protocols
import rebalancing

# Unique instance identifier to track duplicate instances
import socket
INSTANCE_ID = f"{socket.gethostname()}-{os.getpid()}"

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
        # Morpho Blue Core contract on Monad
        'pool_address': os.environ.get('MORPHO_BLUE_ADDRESS', '0xD5D960E8C380B724a48AC59E2DfF1b2CB4a1eAee'),
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
    },
            # Euler disabled - waiting for subgraph support on Monad
            # 'euler': {
            #     'name': 'Euler',
            #     'chain': 'Monad',
            #     'chain_id': 143,
            #     'rpc_url': os.environ.get('MONAD_NODE_URL', 'https://rpc.monad.xyz'),
            #     # EVC (Euler Vault Controller) address - required for getAccountEnabledVaultsInfo
            #     'pool_address': '0x7a9324E8f270413fa2E458f5831226d99C7477CD',
            #     # accountLens for account-level queries (discovering vaults)
            #     'account_lens_address': '0x960D481229f70c3c1CBCD3fA2d223f55Db9f36Ee',
            #     # vaultLens address (for vault-specific queries if needed)
            #     'vault_lens_address': '0x15d1Cc54fB3f7C0498fc991a23d8Dc00DF3c32A0',
            #     'app_url': 'https://app.euler.finance',
            #     'explorer_url': 'https://monadvision.com',
            #     'health_factor_method': 'getAccountEnabledVaultsInfo',  # Custom method in protocols.py
            #     'health_factor_index': None,  # Will need custom parsing
            #     'health_factor_divisor': 1e18,
            #     'abi': protocols.load_abi('AccountLens')  # Use AccountLens ABI (case-sensitive)
            # }
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
    contract_address = protocol_info['pool_address']
    contract = w3.eth.contract(address=contract_address, abi=protocol_info['abi'])
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
    """
    Migrate old data format to new hierarchical format.
    Preserves new format data, migrates old format if needed.
    """
    if not data:
        return {}
    
    migrated = {}
    for chat_id, user_info in data.items():
        # Check if it's already new format (has 'addresses' key with dict structure)
        if 'addresses' in user_info and isinstance(user_info['addresses'], dict):
            # Already new format - preserve it
            migrated[chat_id] = user_info
        elif 'address' in user_info:
            # Old format: {'threshold': 1.5, 'address': '0x...'}
            # Convert to new format
            threshold = user_info.get('threshold', 1.5)
            address = user_info['address']
            migrated[chat_id] = {
                'addresses': {
                    address: {
                        'default_threshold': threshold,
                        'protocols': {}
                    }
                }
            }
        else:
            # Unknown format - preserve as-is to avoid data loss
            migrated[chat_id] = user_info
    
    return migrated

# Save user data to file
def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)

# Global variable to store user data
user_data = load_user_data()

# Cache for API calls (30 second TTL to balance accuracy vs API calls)
_cache = {}
CACHE_TTL = 30  # seconds

def get_cached_or_fetch(cache_key: str, fetch_func, *args, **kwargs):
    """
    Get from cache if valid, otherwise fetch and cache.
    
    Args:
        cache_key: Unique cache key
        fetch_func: Function to call if cache miss
        *args, **kwargs: Arguments to pass to fetch_func
    
    Returns:
        Cached or freshly fetched value
    """
    if cache_key in _cache:
        value, timestamp = _cache[cache_key]
        if time() - timestamp < CACHE_TTL:
            logger.debug(f"Cache hit for {cache_key}")
            return value
    
    # Fetch fresh data
    logger.debug(f"Cache miss for {cache_key}, fetching fresh data")
    value = fetch_func(*args, **kwargs)
    _cache[cache_key] = (value, time())
    return value

def is_valid_position(health_factor: Optional[float], borrow_amount: Optional[float] = None) -> bool:
    """
    Filter out invalid/closed positions.
    
    Args:
        health_factor: Health factor value
        borrow_amount: Borrowed amount (optional, for filtering supply-only positions)
    
    Returns:
        True if position is valid and active
    """
    # Filter None values
    if health_factor is None:
        return False
    
    # Filter max uint256 values (closed positions return max value)
    # Max uint256 is ~1.15e77, we use 1e10 as a reasonable upper bound
    if health_factor > 1e10:
        logger.debug(f"Filtered invalid position with health_factor: {health_factor}")
        return False
    
    # Filter positions with no debt (supply-only, no liquidation risk)
    if borrow_amount is not None:
        try:
            borrow_float = float(borrow_amount)
            if borrow_float == 0:
                logger.debug("Filtered supply-only position (no debt)")
                return False
        except (ValueError, TypeError):
            pass
    
    return True

def get_threshold_for_position(chat_id: str, address: str, protocol_id: str, market_id: Optional[str] = None) -> float:
    """
    Get threshold for a position using hierarchy:
    Market-specific > Protocol-specific > Global default
    
    Args:
        chat_id: Chat ID
        address: Wallet address
        protocol_id: Protocol identifier
        market_id: Market identifier (optional)
    
    Returns:
        Threshold value (defaults to 1.5 if not found)
    """
    if chat_id not in user_data:
        return 1.5
    
    address_data = user_data[chat_id].get('addresses', {}).get(address, {})
    
    # Check market-specific first
    if market_id:
        market_threshold = address_data.get('protocols', {}).get(protocol_id, {}).get('markets', {}).get(market_id, {}).get('threshold')
        if market_threshold:
            return float(market_threshold)
    
    # Check protocol-specific
    protocol_threshold = address_data.get('protocols', {}).get(protocol_id, {}).get('threshold')
    if protocol_threshold:
        return float(protocol_threshold)
    
    # Fall back to global default
    return float(address_data.get('default_threshold', 1.5))

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
        
        # elif protocol_id == 'euler':
        #     return protocols.check_euler_health_factor(address, contract, conn['w3'])
        
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
        "/add <address> <threshold> - Set global threshold (monitors all protocols)\n"
        "/add <address> <threshold> <protocol> - Set protocol-specific threshold\n"
        "/add <address> <threshold> <protocol> <market> - Set market-specific threshold\n"
        "  Examples:\n"
        "    /add 0x1234... 1.5\n"
        "    /add 0x1234... 1.3 morpho\n"
        "    /add 0x1234... 1.2 morpho 0xMarketID\n"
        "/list - List all addresses you're monitoring\n"
        "/check - Auto-discover and check all positions across all protocols\n"
        "/repay - Get rebalancing suggestions (withdraw from vaults & repay loans)\n"
        "/remove <address> - Remove an address from monitoring\n"
        "/stop - Stop monitoring all addresses\n"
        "/protocols - List all supported protocols\n\n"
        "The bot automatically discovers all your positions across all protocols!\n\n"
        "DISCLAIMER: This bot is not officially affiliated with or endorsed by any protocol. "
        "It is an independent tool created for informational purposes only. "
        "The bot is not guaranteed to be always accurate or available. "
        "Users should not rely solely on this bot for making financial decisions."
    )

# Function to handle /add command (adds an address to monitor)
async def add_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Add address to monitor with hierarchical threshold support:
    - /add <address> <threshold> - Global threshold for all protocols
    - /add <address> <threshold> <protocol> - Protocol-specific threshold
    - /add <address> <threshold> <protocol> <market> - Market-specific threshold
    """
    chat_id = str(update.effective_chat.id)
    
    # Parse arguments
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage:\n"
            "  /add <address> <threshold> - Set global threshold for all protocols\n"
            "  /add <address> <threshold> <protocol> - Set threshold for specific protocol\n"
            "  /add <address> <threshold> <protocol> <market> - Set threshold for specific market\n\n"
            "Examples:\n"
            "  /add 0x1234... 1.5\n"
            "  /add 0x1234... 1.3 morpho\n"
            "  /add 0x1234... 1.2 morpho 0xMarketID\n"
            "  /add 0x1234... 1.4 curvance 0xMarketManager\n\n"
            f"Supported protocols: {', '.join(PROTOCOL_CONFIG.keys())}"
        )
        return
    
    address = context.args[0].lower()
    threshold_str = context.args[1]
    protocol_id = context.args[2].lower() if len(context.args) >= 3 else None
    market_id = context.args[3].lower() if len(context.args) >= 4 else None
    
    # Validate threshold
    try:
        threshold = float(threshold_str)
        if threshold <= 0:
            raise ValueError("Threshold must be positive")
    except ValueError:
        await update.message.reply_text("Invalid threshold. Please enter a positive number (e.g., 1.5).")
        return
    
    # Validate address (use any protocol's Web3 instance)
    if not protocol_connections:
        await update.message.reply_text("Error: No protocol connections available.")
        return
    
    # Use first available protocol to validate address
    first_protocol = list(protocol_connections.values())[0]
    if not first_protocol['w3'].is_address(address):
        await update.message.reply_text("Invalid address format. Please try again.")
        return
    
    # Validate protocol if specified
    if protocol_id and protocol_id not in PROTOCOL_CONFIG:
        await update.message.reply_text(
            f"Unknown protocol: {protocol_id}\n"
            f"Supported protocols: {', '.join(PROTOCOL_CONFIG.keys())}"
        )
        return
    
    # Validate market ID format if provided
    if market_id:
        if protocol_id == 'morpho':
            # Morpho market ID should be bytes32 (66 chars: 0x + 64 hex)
            if not market_id.startswith('0x') or len(market_id) != 66:
                await update.message.reply_text(
                    f"⚠️ Invalid Morpho market ID format: {market_id}\n"
                    "Market ID should be 66 characters (0x + 64 hex chars).\n"
                    "Example: 0x409f2824aee2d8391d4a5924935e13312e157055e262b923b60c9dcb47e6311d"
                )
                return
        elif protocol_id == 'curvance':
            # Curvance MarketManager should be address (42 chars: 0x + 40 hex)
            if not market_id.startswith('0x') or len(market_id) != 42:
                await update.message.reply_text(
                    f"⚠️ Invalid Curvance MarketManager address format: {market_id}\n"
                    "MarketManager address should be 42 characters (0x + 40 hex chars).\n"
                    "Example: 0xd6365555f6a697C7C295bA741100AA644cE28545"
                )
                return
    
    # Initialize user data structure if needed
    if chat_id not in user_data:
        user_data[chat_id] = {'addresses': {}}
    
    if address not in user_data[chat_id]['addresses']:
        user_data[chat_id]['addresses'][address] = {
            'default_threshold': threshold,
            'protocols': {}
        }
    
    address_data = user_data[chat_id]['addresses'][address]
    
    # Set threshold at appropriate level
    if market_id:
        # Market-specific threshold
        if protocol_id not in address_data['protocols']:
            address_data['protocols'][protocol_id] = {'markets': {}}
        elif 'markets' not in address_data['protocols'][protocol_id]:
            address_data['protocols'][protocol_id]['markets'] = {}
        
        address_data['protocols'][protocol_id]['markets'][market_id] = {'threshold': threshold}
        protocol_info = PROTOCOL_CONFIG[protocol_id]
        message = f"✅ Set threshold {threshold} for {address} on {protocol_info['name']} market {market_id[:20]}..."
        
    elif protocol_id:
        # Protocol-specific threshold
        if protocol_id not in address_data['protocols']:
            address_data['protocols'][protocol_id] = {}
        address_data['protocols'][protocol_id]['threshold'] = threshold
        protocol_info = PROTOCOL_CONFIG[protocol_id]
        message = f"✅ Set threshold {threshold} for {address} on {protocol_info['name']} protocol"
        
    else:
        # Global threshold
        address_data['default_threshold'] = threshold
        message = f"✅ Set global threshold {threshold} for {address} (applies to all protocols)"
    
    save_user_data(user_data)
    
    # Automatically check and show positions for this address
    # If protocol was specified, only check that protocol
    checking_msg = await update.message.reply_text("🔍 Checking positions...")
    check_message = await build_check_message(chat_id, [address], filter_protocol=protocol_id)
    
    # Delete the "checking..." message
    try:
        await checking_msg.delete()
    except Exception as e:
        logger.debug(f"Could not delete checking message: {e}")
    
    # Combine confirmation and check results in one message
    combined_message = message
    if check_message:
        combined_message += "\n\n" + check_message
    else:
        protocol_text = f" for {PROTOCOL_CONFIG[protocol_id]['name']} protocol" if protocol_id else ""
        combined_message += f"\n\nNo active positions found for {address}{protocol_text}."
    
    await update.message.reply_text(combined_message, parse_mode='Markdown', disable_web_page_preview=True)

# Function to handle /list command
async def list_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    if chat_id not in user_data or not user_data[chat_id].get('addresses'):
        await update.message.reply_text(
            "You are not currently monitoring any addresses.\n"
            "Use /add <address> <threshold> to start monitoring."
        )
        return

    addresses = user_data[chat_id]['addresses']
    message = f"📋 You are monitoring {len(addresses)} address(es):\n\n"
    
    for idx, (address, address_data) in enumerate(addresses.items(), 1):
        default_threshold = address_data.get('default_threshold', 1.5)
        protocols_data = address_data.get('protocols', {})
        
        message += f"{idx}. {address}\n"
        message += f"   Global threshold: {default_threshold}\n"
        
        if protocols_data:
            message += f"   Protocol-specific thresholds:\n"
            for protocol_id, protocol_data in protocols_data.items():
                protocol_info = PROTOCOL_CONFIG.get(protocol_id, {})
                protocol_name = protocol_info.get('name', protocol_id)
                
                if 'threshold' in protocol_data:
                    message += f"     • {protocol_name}: {protocol_data['threshold']}\n"
                
                if 'markets' in protocol_data:
                    for market_id, market_data in protocol_data['markets'].items():
                        market_threshold = market_data.get('threshold', default_threshold)
                        if protocol_id == 'morpho':
                            message += f"       - Market {market_id[:20]}...: {market_threshold}\n"
                        elif protocol_id == 'curvance':
                            message += f"       - MarketManager {market_id[:20]}...: {market_threshold}\n"
        
        message += "\n"
    
    await update.message.reply_text(message)

# Function to handle /remove command
async def remove_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Remove address from monitoring.
    Supports: /remove <address> [protocol] [market]
    """
    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /remove <address> [protocol] [market]\n"
            "Examples:\n"
            "  /remove 0x1234... - Remove entire address\n"
            "  /remove 0x1234... morpho - Remove Morpho protocol threshold\n"
            "  /remove 0x1234... morpho 0xMarketID - Remove specific market threshold"
        )
        return

    chat_id = str(update.effective_chat.id)
    address = context.args[0].lower()
    protocol_id = context.args[1].lower() if len(context.args) >= 2 else None
    market_id = context.args[2].lower() if len(context.args) >= 3 else None

    if chat_id not in user_data or address not in user_data[chat_id].get('addresses', {}):
        await update.message.reply_text(
            f"Address {address} is not being monitored.\n"
            "Use /list to see all monitored addresses."
        )
        return

    address_data = user_data[chat_id]['addresses'][address]
    
    if market_id:
        # Remove market-specific threshold
        if protocol_id and protocol_id in address_data.get('protocols', {}):
            markets = address_data['protocols'][protocol_id].get('markets', {})
            if market_id in markets:
                del address_data['protocols'][protocol_id]['markets'][market_id]
                # Clean up empty markets dict
                if not address_data['protocols'][protocol_id]['markets']:
                    del address_data['protocols'][protocol_id]['markets']
                save_user_data(user_data)
                await update.message.reply_text(
                    f"✅ Removed market-specific threshold for {address} on {PROTOCOL_CONFIG.get(protocol_id, {}).get('name', protocol_id)} market {market_id[:20]}..."
                )
                return
        await update.message.reply_text("Market threshold not found.")
        
    elif protocol_id:
        # Remove protocol-specific threshold
        if protocol_id in address_data.get('protocols', {}):
            del address_data['protocols'][protocol_id]
            # Clean up empty protocols dict
            if not address_data['protocols']:
                del address_data['protocols']
            save_user_data(user_data)
            await update.message.reply_text(
                f"✅ Removed protocol-specific threshold for {address} on {PROTOCOL_CONFIG.get(protocol_id, {}).get('name', protocol_id)}"
            )
            return
        await update.message.reply_text("Protocol threshold not found.")
        
    else:
        # Remove entire address
        del user_data[chat_id]['addresses'][address]
        
        # If no addresses left, remove user entirely
        if not user_data[chat_id]['addresses']:
            del user_data[chat_id]
        
        save_user_data(user_data)
        await update.message.reply_text(f"✅ Removed {address} from monitoring.")

# Function to auto-discover all positions for an address across all protocols
async def discover_all_positions(address: str, chat_id: str, filter_protocol: Optional[str] = None) -> List[Dict]:
    """
    Auto-discover all active positions for an address across all protocols.
    
    Args:
        address: Wallet address to check
        chat_id: Chat ID for user data lookup
        filter_protocol: Optional protocol ID to filter results (e.g., 'euler', 'morpho')
    
    Returns:
        List of position dicts with: protocol_id, market_id, health_factor, threshold, etc.
    """
    positions = []
    address_data = user_data[chat_id].get('addresses', {}).get(address, {})
    
    # Check Neverland
    if filter_protocol is None or filter_protocol == 'neverland':
        try:
            cache_key = f"neverland_{address}"
            health_factor = get_cached_or_fetch(
                cache_key,
                check_health_factor,
                address,
                'neverland'
            )
            
            if is_valid_position(health_factor):
                threshold = get_threshold_for_position(chat_id, address, 'neverland')
                # Get collateral and debt data
                neverland_info = None
                try:
                    protocol_info = PROTOCOL_CONFIG['neverland']
                    conn = protocol_connections['neverland']
                    cache_key_data = f"neverland_data_{address}"
                    account_data = get_cached_or_fetch(
                        cache_key_data,
                        protocols.get_neverland_account_data,
                        address,
                        conn['contract'],
                        conn['w3']
                    )
                    if account_data:
                        neverland_info = {
                            'collateral_usd': account_data.get('collateral_usd', 0),
                            'debt_usd': account_data.get('debt_usd', 0)
                        }
                except Exception as e:
                    logger.debug(f"Could not get Neverland account data: {e}")
                
                positions.append({
                    'protocol_id': 'neverland',
                    'market_id': None,
                    'health_factor': health_factor,
                    'threshold': threshold,
                    'market_info': neverland_info
                })
        except Exception as e:
            logger.error(f"Error checking Neverland for {address}: {e}")
    
    # Check Morpho - auto-discover all markets
    if filter_protocol is None or filter_protocol == 'morpho':
        try:
            protocol_info = PROTOCOL_CONFIG['morpho']
            cache_key = f"morpho_markets_{address}"
            markets_data = get_cached_or_fetch(
                cache_key,
                get_morpho_user_markets,
                address,
                protocol_info['chain_id']
            )
            
            if markets_data:
                for market in markets_data:
                    hf = market.get('healthFactor')
                    borrow_amount = market.get('borrowAssetsUsd', 0)
                    
                    if is_valid_position(hf, borrow_amount):
                        market_id = market['id'].lower()
                        threshold = get_threshold_for_position(chat_id, address, 'morpho', market_id)
                        positions.append({
                            'protocol_id': 'morpho',
                            'market_id': market_id,
                            'health_factor': float(hf),
                            'threshold': threshold,
                            'market_info': market
                        })
        except Exception as e:
            logger.error(f"Error checking Morpho for {address}: {e}")
    
    # Check Curvance - auto-discover all MarketManagers
    if filter_protocol is None or filter_protocol == 'curvance':
        try:
            protocol_info = PROTOCOL_CONFIG['curvance']
            conn = protocol_connections['curvance']
            
            # Get all MarketManagers from Central Registry
            cache_key = f"curvance_managers"
            market_managers = get_cached_or_fetch(
                cache_key,
                protocols.get_curvance_market_managers,
                conn['w3']
            )
            
            # Check each MarketManager for positions
            for market_manager in market_managers:
                try:
                    cache_key_market = f"curvance_{address}_{market_manager}"
                    health_factor = get_cached_or_fetch(
                        cache_key_market,
                        protocols.check_curvance_health_factor,
                        address,
                        conn['contract'],
                        conn['w3'],
                        market_manager,
                        None
                    )
                    
                    if is_valid_position(health_factor):
                        threshold = get_threshold_for_position(chat_id, address, 'curvance', market_manager)
                        # Get position details (token symbols and amounts)
                        try:
                            cache_key_details = f"curvance_details_{address}_{market_manager}"
                            position_details_list = get_cached_or_fetch(
                                cache_key_details,
                                protocols.get_curvance_position_details,
                                address,
                                conn['contract'],
                                conn['w3'],
                                market_manager,
                                None
                            )
                            # Use first position detail if available
                            curvance_info = position_details_list[0] if position_details_list else None
                        except Exception as e:
                            logger.debug(f"Could not get Curvance position details: {e}")
                            curvance_info = None
                        
                        positions.append({
                            'protocol_id': 'curvance',
                            'market_id': market_manager,
                            'health_factor': health_factor,
                            'threshold': threshold,
                            'market_info': curvance_info
                        })
                except Exception as e:
                    logger.debug(f"Error checking Curvance MarketManager {market_manager} for {address}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error checking Curvance for {address}: {e}")
    
    # Euler disabled - waiting for subgraph support on Monad
    # if filter_protocol is None or filter_protocol == 'euler':
    #     try:
    #         protocol_info = PROTOCOL_CONFIG['euler']
    #         conn = protocol_connections['euler']
    #         
    #         logger.info(f"Checking Euler for {address}...")
    #         
    #         # Get all vaults where user has positions using AccountLens
    #         cache_key = f"euler_vaults_{address}"
    #         vaults_data = get_cached_or_fetch(
    #             cache_key,
    #             protocols.get_euler_user_vaults,
    #             address,
    #             conn['w3'],
    #             protocol_info.get('account_lens_address'),
    #             protocol_info.get('pool_address')  # EVC address
    #         )
    #         
    #         logger.info(f"Euler query returned {len(vaults_data) if vaults_data else 0} vaults for {address}")
    #         
    #         if vaults_data:
    #             for vault in vaults_data:
    #                 hf = vault.get('health_factor')
    #                 debt_usd = vault.get('debt_usd', 0)
    #                 vault_address = vault.get('vault_address', '')
    #                 
    #                 logger.debug(f"Euler vault {vault_address}: hf={hf}, debt=${debt_usd}")
    #                 
    #                 if is_valid_position(hf, debt_usd):
    #                     vault_address_lower = vault_address.lower() if vault_address else ''
    #                     threshold = get_threshold_for_position(chat_id, address, 'euler', vault_address_lower)
    #                     positions.append({
    #                         'protocol_id': 'euler',
    #                         'market_id': vault_address_lower,
    #                         'health_factor': float(hf),
    #                         'threshold': threshold,
    #                         'market_info': vault
    #                     })
    #                     logger.info(f"Added Euler position: {vault_address_lower}, hf={hf:.3f}")
    #                 else:
    #                     logger.debug(f"Filtered Euler vault {vault_address}: hf={hf}, debt=${debt_usd} (invalid position)")
    #         else:
    #             logger.info(f"No Euler vaults found for {address}")
    #     except Exception as e:
    #         logger.error(f"Error checking Euler for {address}: {e}")
    #         import traceback
    #         logger.error(traceback.format_exc())
    
    return positions

# Helper function to build quick check message (health factors only - fast)
async def build_check_message(chat_id: str, addresses: List[str], filter_protocol: Optional[str] = None) -> Optional[str]:
    """
    Build a formatted message showing all positions for given addresses.
    
    Args:
        chat_id: Chat ID
        addresses: List of addresses to check
        filter_protocol: Optional protocol ID to filter by (e.g., 'morpho', 'neverland')
    
    Returns:
        Formatted message string, or None if no addresses to check
    """
    if not addresses:
        return None
    
    messages = []
    
    # Process each address
    for address in addresses:
        try:
            # Auto-discover all positions (only check specified protocol if filter provided)
            positions = await discover_all_positions(address, chat_id, filter_protocol=filter_protocol)
            
            if not positions:
                protocol_text = f" for {PROTOCOL_CONFIG[filter_protocol]['name']} protocol" if filter_protocol else ""
                messages.append(f"For {address}:\n\nNo active positions found{protocol_text}.")
                continue
            
            # Group positions by protocol
            protocol_groups = {}
            for pos in positions:
                protocol_id = pos['protocol_id']
                # Filter by protocol if specified
                if filter_protocol and protocol_id != filter_protocol:
                    continue
                if protocol_id not in protocol_groups:
                    protocol_groups[protocol_id] = []
                protocol_groups[protocol_id].append(pos)
            
            # Skip if no positions after filtering
            if not protocol_groups:
                continue
            
            # Build message
            address_message = f"For {address}:\n"
            
            for protocol_id, protocol_positions in protocol_groups.items():
                protocol_info = PROTOCOL_CONFIG[protocol_id]
                address_message += f"\n{protocol_info['name']} protocol:\n"
                
                # Sort by health factor (worst first)
                protocol_positions.sort(key=lambda x: x['health_factor'])
                
                for pos in protocol_positions:
                    health_factor = pos['health_factor']
                    threshold = pos['threshold']
                    market_id = pos['market_id']
                    market_info = pos.get('market_info')
                    
                    status = "⚠️ " if health_factor < threshold else ""
                    liquidation_drop_pct = (1 - (1 / health_factor)) * 100 if health_factor > 0 else 0
                    threshold_str = f"{threshold:.3f}".rstrip('0').rstrip('.')
                    
                    # Format message - reordered: Current Health first, then threshold
                    if protocol_id == 'morpho' and market_info:
                        market_name = market_info.get('name', 'Unknown').upper()
                        market_url = f"https://app.morpho.org/monad/market/{market_info['id']}/{market_info['name']}?subTab=yourPosition"
                        address_message += f"{status}[{market_name}]({market_url}):\nCurrent Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation), Alert at {threshold_str}\n"
                    elif protocol_id == 'curvance' and market_id:
                        market_url = f"{protocol_info.get('app_url', '')}/market/{market_id}"
                        address_message += f"{status}[Curvance Market]({market_url}):\nCurrent Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation), Alert at {threshold_str}\n"
                    # elif protocol_id == 'euler' and market_id:
                    #     # Euler vault URL format: /positions/{account}/{vault}?network=monad
                    #     # Use the monitored address (not vault address) for the URL
                    #     vault_url = f"{protocol_info.get('app_url', '')}/positions/{address}/{market_id}?network=monad"
                    #     address_message += f"{status}[Euler Vault]({vault_url}):\nCurrent Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation), Alert at {threshold_str}\n"
                    else:
                        # Neverland and other protocols
                        protocol_url = protocol_info.get('app_url', '')
                        if protocol_url:
                            address_message += f"{status}[{protocol_info['name']}]({protocol_url}):\nCurrent Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation), Alert at {threshold_str}\n"
                        else:
                            address_message += f"{status}{protocol_info['name']}:\nCurrent Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation), Alert at {threshold_str}\n"
            
            messages.append(address_message)
            
        except Exception as e:
            logger.error(f"Error processing address {address}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            messages.append(f"For {address}:\n\n⚠️ Error checking positions: {str(e)[:100]}")
    
    if not messages:
        return None
    
    return "\n\n".join(messages)

# Helper function to build full position message with collateral/debt details
async def build_position_message(chat_id: str, addresses: List[str], filter_protocol: Optional[str] = None) -> Optional[str]:
    """
    Build a detailed message showing all positions with collateral and debt values.
    
    Args:
        chat_id: Chat ID
        addresses: List of addresses to check
        filter_protocol: Optional protocol ID to filter results
    
    Returns:
        Formatted message string with full position details, or None if no addresses
    """
    if not addresses:
        return None
    
    messages = []
    
    # Process each address
    for address in addresses:
        try:
            # Auto-discover all positions (only check specified protocol if filter provided)
            positions = await discover_all_positions(address, chat_id, filter_protocol=filter_protocol)
            
            if not positions:
                protocol_text = f" for {PROTOCOL_CONFIG[filter_protocol]['name']} protocol" if filter_protocol else ""
                messages.append(f"For {address}:\n\nNo active positions found{protocol_text}.")
                continue
            
            # Group positions by protocol
            protocol_groups = {}
            for pos in positions:
                protocol_id = pos['protocol_id']
                if protocol_id not in protocol_groups:
                    protocol_groups[protocol_id] = []
                protocol_groups[protocol_id].append(pos)
            
            # Build message
            address_message = f"For {address}:\n"
            
            for protocol_id, protocol_positions in protocol_groups.items():
                protocol_info = PROTOCOL_CONFIG[protocol_id]
                address_message += f"\n{protocol_info['name']} protocol:\n"
                
                # Sort by health factor (worst first)
                protocol_positions.sort(key=lambda x: x['health_factor'])
                
                for pos in protocol_positions:
                    health_factor = pos['health_factor']
                    threshold = pos['threshold']
                    market_id = pos['market_id']
                    market_info = pos.get('market_info')
                    
                    status = "⚠️ " if health_factor < threshold else ""
                    liquidation_drop_pct = (1 - (1 / health_factor)) * 100 if health_factor > 0 else 0
                    threshold_str = f"{threshold:.3f}".rstrip('0').rstrip('.')
                    
                    # Extract collateral and debt values
                    collateral_usd = None
                    debt_usd = None
                    collateral_token = None
                    debt_token = None
                    collateral_amount = None
                    debt_amount = None
                    
                    if protocol_id == 'morpho' and market_info:
                        # Morpho: Health Factor = (Collateral Value × LLTV) / Total Borrowed Amount
                        # So: Collateral Value = (Health Factor × Total Borrowed Amount) / LLTV
                        collateral_usd = market_info.get('supplyAssetsUsd', 0)
                        debt_usd = market_info.get('borrowAssetsUsd', 0)
                        lltv = market_info.get('lltv')  # Liquidation LTV (e.g., 0.86 for 86%) - fetched from contract
                        
                        # If LLTV is still not available, try fetching from contract
                        if lltv is None:
                            market_id = market_info.get('id')
                            if market_id:
                                try:
                                    protocol_info = PROTOCOL_CONFIG['morpho']
                                    conn = protocol_connections['morpho']
                                    lltv = protocols.get_morpho_market_lltv(market_id, conn['contract'], conn['w3'])
                                    if lltv:
                                        market_info['lltv'] = lltv  # Cache it in market_info
                                        logger.debug(f"Fetched LLTV from contract for market {market_id}: {lltv:.4f}")
                                except Exception as e:
                                    logger.debug(f"Could not fetch LLTV from contract: {e}")
                        
                        # Calculate collateral from health factor and LLTV if supplyAssetsUsd is 0
                        if collateral_usd == 0 and debt_usd > 0 and health_factor and lltv:
                            try:
                                lltv_float = float(lltv)
                                if lltv_float > 0:
                                    # Formula: Collateral = (HF × Debt) / LLTV
                                    collateral_usd = (float(debt_usd) * float(health_factor)) / lltv_float
                                    logger.debug(f"Calculated Morpho collateral: (${debt_usd} × {health_factor}) / {lltv_float} = ${collateral_usd:.2f}")
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Error calculating collateral from LLTV: {e}")
                        
                        # Fallback if LLTV not available
                        if collateral_usd == 0 and debt_usd > 0 and health_factor:
                            try:
                                # Use estimated LLTV of 0.80 (80%) as fallback
                                estimated_lltv = 0.80
                                collateral_usd = (float(debt_usd) * float(health_factor)) / estimated_lltv
                                logger.debug(f"Estimated Morpho collateral with default LLTV: (${debt_usd} × {health_factor}) / {estimated_lltv} = ${collateral_usd:.2f}")
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Could not estimate Morpho collateral: {e}")
                                collateral_usd = 0
                        
                        # Store liquidation price if available
                        liquidation_price = market_info.get('liquidationPrice')
                    elif protocol_id == 'neverland' and market_info:
                        collateral_usd = market_info.get('collateral_usd', 0)
                        debt_usd = market_info.get('debt_usd', 0)
                    elif protocol_id == 'curvance' and market_info:
                        # Curvance: use raw amounts with token symbols
                        collateral_token = market_info.get('collateral_token', '?')
                        debt_token = market_info.get('debt_token', '?')
                        collateral_amount = market_info.get('collateral_amount', 0)
                        debt_amount = market_info.get('debt_amount', 0)
                    
                    # Format collateral/debt display
                    tvl_debt_str = ""
                    if protocol_id == 'curvance' and market_info:
                        # Format with 3 sig fig
                        def format_sig_fig(value):
                            if value == 0:
                                return "0"
                            # Convert to scientific notation for sig fig calculation
                            import math
                            if value >= 1:
                                # For values >= 1, round to 3 sig fig
                                magnitude = math.floor(math.log10(value))
                                factor = 10 ** (2 - magnitude)
                                rounded = round(value * factor) / factor
                                # Format nicely
                                if rounded >= 1_000_000:
                                    return f"{rounded/1_000_000:.3g}M"
                                elif rounded >= 1_000:
                                    return f"{rounded/1_000:.3g}K"
                                else:
                                    return f"{rounded:.3g}"
                            else:
                                # For values < 1, show 3 sig fig
                                return f"{value:.3g}"
                        
                        collateral_str = format_sig_fig(collateral_amount) if collateral_amount else "0"
                        debt_str = format_sig_fig(debt_amount) if debt_amount else "0"
                        tvl_debt_str = f"\nCollateral: {collateral_str} {collateral_token} | Debt: {debt_str} {debt_token}"
                    elif collateral_usd is not None and debt_usd is not None:
                        # Format large numbers nicely for USD values
                        def format_currency(value):
                            if value == 0:
                                return "$0.00"
                            if value >= 1_000_000:
                                return f"${value/1_000_000:.2f}M"
                            elif value >= 1_000:
                                return f"${value/1_000:.2f}K"
                            else:
                                return f"${value:.2f}"
                        
                        # For Morpho, use raw borrow amount if available (shows accrual) and add liquidation price
                        if protocol_id == 'morpho' and market_info:
                            borrow_amount_raw = market_info.get('borrowAmountRaw')
                            loan_symbol = market_info.get('loanAsset', '?')
                            liquidation_price = market_info.get('liquidationPrice')
                            
                            if borrow_amount_raw:
                                # Format raw amount nicely
                                if borrow_amount_raw >= 1_000_000:
                                    debt_display = f"{borrow_amount_raw/1_000_000:.2f}M {loan_symbol}"
                                elif borrow_amount_raw >= 1_000:
                                    debt_display = f"{borrow_amount_raw/1_000:.2f}K {loan_symbol}"
                                else:
                                    debt_display = f"{borrow_amount_raw:.2f} {loan_symbol}"
                                
                                # Add liquidation price if available
                                liquidation_str = ""
                                if liquidation_price:
                                    try:
                                        liq_price_float = float(liquidation_price)
                                        collateral_symbol = market_info.get('collateralAsset', '?')
                                        liquidation_str = f" | Liq Price: {liq_price_float:.2f} {loan_symbol}/{collateral_symbol}"
                                    except (ValueError, TypeError):
                                        pass
                                
                                tvl_debt_str = f"\nCollateral: {format_currency(collateral_usd)} | Debt: {debt_display} ({format_currency(debt_usd)}){liquidation_str}"
                            else:
                                # Fallback if raw amount not available
                                liquidation_str = ""
                                if liquidation_price:
                                    try:
                                        liq_price_float = float(liquidation_price)
                                        collateral_symbol = market_info.get('collateralAsset', '?')
                                        loan_symbol = market_info.get('loanAsset', '?')
                                        liquidation_str = f" | Liq Price: {liq_price_float:.2f} {loan_symbol}/{collateral_symbol}"
                                    except (ValueError, TypeError):
                                        pass
                                tvl_debt_str = f"\nCollateral: {format_currency(collateral_usd)} | Debt: {format_currency(debt_usd)}{liquidation_str}"
                        else:
                            tvl_debt_str = f"\nCollateral: {format_currency(collateral_usd)} | Debt: {format_currency(debt_usd)}"
                    
                    # Format message based on protocol
                    if protocol_id == 'morpho' and market_info:
                        market_name = market_info.get('name', 'Unknown').upper()
                        market_url = f"https://app.morpho.org/monad/market/{market_info['id']}/{market_info['name']}?subTab=yourPosition"
                        address_message += f"{status}[{market_name}]({market_url}):\nCurrent Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation), Alert at {threshold_str}{tvl_debt_str}\n"
                    elif protocol_id == 'curvance' and market_id:
                        market_url = f"{protocol_info.get('app_url', '')}/market/{market_id}"
                        address_message += f"{status}[Curvance Market]({market_url}):\nCurrent Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation), Alert at {threshold_str}{tvl_debt_str}\n"
                    # elif protocol_id == 'euler' and market_id:
                    #     # Euler vault URL format: /positions/{account}/{vault}?network=monad
                    #     # Use the monitored address (not vault address) for the URL
                    #     vault_url = f"{protocol_info.get('app_url', '')}/positions/{address}/{market_id}?network=monad"
                    #     # Extract collateral/debt from market_info
                    #     if market_info:
                    #         collateral_usd = market_info.get('collateral_usd', 0)
                    #         debt_usd = market_info.get('debt_usd', 0)
                    #         if collateral_usd is not None and debt_usd is not None:
                    #             def format_currency(value):
                    #                 if value == 0:
                    #                     return "$0.00"
                    #                 if value >= 1_000_000:
                    #                     return f"${value/1_000_000:.2f}M"
                    #                 elif value >= 1_000:
                    #                     return f"${value/1_000:.2f}K"
                    #                 else:
                    #                     return f"${value:.2f}"
                    #             tvl_debt_str = f"\nCollateral: {format_currency(collateral_usd)} | Debt: {format_currency(debt_usd)}"
                    #         else:
                    #             tvl_debt_str = ""
                    #     else:
                    #         tvl_debt_str = ""
                    #     address_message += f"{status}[Euler Vault]({vault_url}):\nCurrent Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation), Alert at {threshold_str}{tvl_debt_str}\n"
                    else:
                        # Neverland and other protocols
                        protocol_url = protocol_info.get('app_url', '')
                        if protocol_url:
                            address_message += f"{status}[{protocol_info['name']}]({protocol_url}):\nCurrent Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation), Alert at {threshold_str}{tvl_debt_str}\n"
                        else:
                            address_message += f"{status}{protocol_info['name']}:\nCurrent Health: {health_factor:.3f} ({liquidation_drop_pct:.1f}% from liquidation), Alert at {threshold_str}{tvl_debt_str}\n"
            
            messages.append(address_message)
            
        except Exception as e:
            logger.error(f"Error processing address {address}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            messages.append(f"For {address}:\n\n⚠️ Error checking positions: {str(e)[:100]}")
    
    if not messages:
        return None
    
    return "\n\n".join(messages)

# Function to handle /check command
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Auto-discover and check positions with optional filters:
    - /check - Check all protocols for all addresses
    - /check <protocol> - Check specific protocol for all addresses
    - /check <address> - Check all protocols for specific address
    """
    chat_id = str(update.effective_chat.id)
    logger.info(f"/check called by chat_id: {chat_id}, args: {context.args}")
    
    if chat_id not in user_data or not user_data[chat_id].get('addresses'):
        logger.info(f"[{INSTANCE_ID}] No addresses found for chat_id {chat_id}, user_data: {user_data.get(chat_id, {})}")
        await update.message.reply_text(
            f"[Instance: {INSTANCE_ID[:8]}]\n"
            "You are not currently monitoring any addresses.\n"
            "Use /add <address> <threshold> to start monitoring."
        )
        return
    
    addresses = list(user_data[chat_id]['addresses'].keys())
    
    if not addresses:
        await update.message.reply_text("No addresses to check.")
        return
    
    # Parse arguments
    filter_protocol = None
    filter_address = None
    
    if context.args and len(context.args) > 0:
        arg = context.args[0].lower()
        
        # Check if it's a protocol ID
        if arg in PROTOCOL_CONFIG:
            filter_protocol = arg
            logger.info(f"Filtering by protocol: {filter_protocol}")
        else:
            # Check if it's a valid address format
            # Use any protocol's Web3 instance to validate
            first_protocol = list(protocol_connections.values())[0]
            if first_protocol['w3'].is_address(arg):
                # Check if this address is being monitored
                if arg in addresses:
                    filter_address = arg
                    logger.info(f"Filtering by address: {filter_address}")
                else:
                    await update.message.reply_text(
                        f"Address {arg} is not being monitored.\n"
                        f"Use /add {arg} <threshold> to start monitoring it."
                    )
                    return
            else:
                await update.message.reply_text(
                    f"Invalid argument: {arg}\n\n"
                    "Usage:\n"
                    "  /check - Check all protocols for all addresses\n"
                    "  /check <protocol> - Check specific protocol (e.g., /check morpho)\n"
                    "  /check <address> - Check specific address\n\n"
                    f"Supported protocols: {', '.join(PROTOCOL_CONFIG.keys())}"
                )
                return
    
    # Send "checking..." message and store it for deletion
    checking_msg = await update.message.reply_text("🔍 Checking positions...")
    
    # Filter addresses if needed
    addresses_to_check = [filter_address] if filter_address else addresses
    
    # Build check message with optional protocol filter
    final_message = await build_check_message(chat_id, addresses_to_check, filter_protocol=filter_protocol)
    
    # Delete the "checking..." message
    try:
        await checking_msg.delete()
    except Exception as e:
        logger.debug(f"Could not delete checking message: {e}")
    
    # Send single consolidated message
    if final_message:
        logger.info(f"Sending /check response from instance {INSTANCE_ID}, chat_id: {chat_id}")
        await update.message.reply_text(final_message, parse_mode='Markdown', disable_web_page_preview=True)
    else:
        filter_msg = ""
        if filter_protocol:
            filter_msg = f" for {PROTOCOL_CONFIG[filter_protocol]['name']}"
        elif filter_address:
            filter_msg = f" for {filter_address}"
        await update.message.reply_text(f"No active positions found{filter_msg}.")

# Function to handle /position command (full details with collateral/debt)
async def position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show full position details including collateral and debt values.
    Supports optional filters:
    - /position: all protocols, all addresses
    - /position <protocol>: specific protocol, all addresses
    - /position <address>: all protocols, specific address
    """
    chat_id = str(update.effective_chat.id)
    logger.info(f"/position called by chat_id: {chat_id}")
    
    if chat_id not in user_data or not user_data[chat_id].get('addresses'):
        await update.message.reply_text(
            "You are not currently monitoring any addresses.\n"
            "Use /add <address> <threshold> to start monitoring."
        )
        return
    
    addresses = list(user_data[chat_id]['addresses'].keys())
    
    if not addresses:
        await update.message.reply_text("No addresses to check.")
        return
    
    # Parse arguments
    filter_protocol = None
    filter_address = None
    
    if context.args and len(context.args) > 0:
        arg = context.args[0].lower()
        
        # Check if it's a protocol ID
        if arg in PROTOCOL_CONFIG:
            filter_protocol = arg
            logger.info(f"Filtering /position by protocol: {filter_protocol}")
        else:
            # Check if it's a valid address format
            first_protocol = list(protocol_connections.values())[0]
            if first_protocol['w3'].is_address(arg):
                # Check if this address is being monitored
                if arg in addresses:
                    filter_address = arg
                    logger.info(f"Filtering /position by address: {filter_address}")
                else:
                    await update.message.reply_text(
                        f"Address {arg} is not being monitored.\n"
                        f"Use /add {arg} <threshold> to start monitoring it."
                    )
                    return
            else:
                await update.message.reply_text(
                    f"Invalid argument: {arg}\n\n"
                    "Usage:\n"
                    "  /position - Show all protocols for all addresses\n"
                    "  /position <protocol> - Show specific protocol (e.g., /position morpho)\n"
                    "  /position <address> - Show specific address\n\n"
                    f"Supported protocols: {', '.join(PROTOCOL_CONFIG.keys())}"
                )
                return
    
    # Send "checking..." message and store it for deletion
    checking_msg = await update.message.reply_text("🔍 Checking positions...")
    
    # Filter addresses if needed
    addresses_to_check = [filter_address] if filter_address else addresses
    
    # Build full position message with optional protocol filter
    final_message = await build_position_message(chat_id, addresses_to_check, filter_protocol=filter_protocol)
    
    # Delete the "checking..." message
    try:
        await checking_msg.delete()
    except Exception as e:
        logger.debug(f"Could not delete checking message: {e}")
    
    # Send single consolidated message
    if final_message:
        logger.info(f"Sending /position response from instance {INSTANCE_ID}, chat_id: {chat_id}")
        await update.message.reply_text(final_message, parse_mode='Markdown', disable_web_page_preview=True)
    else:
        filter_msg = ""
        if filter_protocol:
            filter_msg = f" for {PROTOCOL_CONFIG[filter_protocol]['name']}"
        elif filter_address:
            filter_msg = f" for {filter_address}"
        await update.message.reply_text(f"No active positions found{filter_msg}.")

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
    """Generate rebalancing suggestions for user's positions using auto-discovery."""
    chat_id = str(update.effective_chat.id)
    if chat_id not in user_data or not user_data[chat_id].get('addresses'):
        await update.message.reply_text(
            "You are not currently monitoring any addresses.\n"
            "Use /add <address> <threshold> to start monitoring."
        )
        return
    
    addresses = list(user_data[chat_id]['addresses'].keys())
    messages_sent = 0
    
    # Find worst position across all addresses
    worst_position = None
    worst_hf = float('inf')
    
    for address in addresses:
        try:
            positions = await discover_all_positions(address, chat_id)
            
            for pos in positions:
                health_factor = pos['health_factor']
                threshold = pos['threshold']
                
                # Only consider positions below threshold
                if health_factor < threshold and health_factor < worst_hf:
                    worst_hf = health_factor
                    worst_position = {
                        'address': address,
                        'protocol_id': pos['protocol_id'],
                        'market_id': pos['market_id'],
                        'health_factor': health_factor,
                        'threshold': threshold
                    }
        except Exception as e:
            logger.error(f"Error checking positions for {address} in /repay: {e}")
            continue
    
    # Generate rebalancing message for worst position
    if worst_position:
        protocol_info = PROTOCOL_CONFIG[worst_position['protocol_id']]
        rebalancing_msg = rebalancing.generate_rebalancing_message(
            address=worst_position['address'],
            protocol_id=worst_position['protocol_id'],
            market_id=worst_position['market_id'],
            current_hf=worst_position['health_factor'],
            threshold=worst_position['threshold'],
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
    """
    Auto-discover all positions and send alerts for positions below threshold.
    """
    if chat_id not in user_data or not user_data[chat_id].get('addresses'):
        return

    addresses = list(user_data[chat_id]['addresses'].keys())
    alerts = []

    # Check all addresses using auto-discovery
    for address in addresses:
        try:
            positions = await discover_all_positions(address, chat_id)
            
            for pos in positions:
                health_factor = pos['health_factor']
                threshold = pos['threshold']
                
                if health_factor < threshold:
                    protocol_info = PROTOCOL_CONFIG[pos['protocol_id']]
                    alerts.append({
                        'address': address,
                        'health_factor': health_factor,
                        'threshold': threshold,
                        'protocol': protocol_info,
                        'protocol_id': pos['protocol_id'],
                        'market_id': pos['market_id']
                    })
        except Exception as e:
            logger.error(f"Error checking positions for {address}: {e}")
            continue

    # Send alerts if any
    if alerts:
        for alert in alerts:
            # Generate rebalancing message with vault suggestions
            rebalancing_msg = rebalancing.generate_rebalancing_message(
                address=alert['address'],
                protocol_id=alert['protocol_id'],
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
                    message += f"Market ID: {alert['market_id'][:20]}...\n"
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
    application.add_handler(CommandHandler("position", position))
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

    logger.info(f"Multi-Protocol Lending Health Monitor Bot started. Instance ID: {INSTANCE_ID}")
    logger.info("Polling for updates...")
    for protocol_id, protocol_info in PROTOCOL_CONFIG.items():
        logger.info(f"  - {protocol_info['name']} ({protocol_id}) on {protocol_info['chain']}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()