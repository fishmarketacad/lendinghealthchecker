"""
Protocol-specific health factor checking logic.
Separated from main bot file for better organization.
"""
import json
import os
import logging
import requests
from typing import Optional, List, Dict
from web3 import Web3

logger = logging.getLogger(__name__)

# Morpho GraphQL API endpoint
MORPHO_GRAPHQL_URL = "https://api.morpho.org/graphql"


def load_abi(protocol_id: str) -> List[Dict]:
    """Load ABI from JSON file."""
    abi_path = os.path.join('abis', f'{protocol_id}.json')
    try:
        with open(abi_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"ABI file not found: {abi_path}")
        return []


# Curvance Central Registry address on Monad
CURVANCE_CENTRAL_REGISTRY = '0x1310f352f1389969Ece6741671c4B919523912fF'

# Known Curvance MarketManager addresses on Monad (fallback if Central Registry unavailable)
KNOWN_CURVANCE_MARKET_MANAGERS = [
    '0xd6365555f6a697C7C295bA741100AA644cE28545',  # User's market
    '0x5EA0a1Cf3501C954b64902c5e92100b8A2CaB1Ac',  # AprMON / WMON Market Manager
    '0xE1C24B2E93230FBe33d32Ba38ECA3218284143e2',  # shMON / wMON Market Manager
    # Add more as discovered
]

def get_curvance_market_managers(w3) -> List[str]:
    """
    Get all registered MarketManager addresses from Central Registry.
    Falls back to known list if Central Registry query fails.
    
    Args:
        w3: Web3 instance
    
    Returns:
        List of MarketManager addresses
    """
    try:
        # Central Registry ABI for marketManagers() function
        registry_abi = [
            {
                'inputs': [],
                'name': 'marketManagers',
                'outputs': [{'internalType': 'address[]', 'name': '', 'type': 'address[]'}],
                'stateMutability': 'view',
                'type': 'function'
            }
        ]
        
        registry_contract = w3.eth.contract(
            address=w3.to_checksum_address(CURVANCE_CENTRAL_REGISTRY),
            abi=registry_abi
        )
        
        market_managers = registry_contract.functions.marketManagers().call()
        if market_managers:
            logger.info(f"Retrieved {len(market_managers)} MarketManagers from Central Registry")
            return [mm.lower() for mm in market_managers]  # Normalize to lowercase
    except Exception as e:
        logger.warning(f"Failed to query Central Registry for MarketManagers: {e}. Using fallback list.")
    
    # Fallback to known list
    return [mm.lower() for mm in KNOWN_CURVANCE_MARKET_MANAGERS]

def check_curvance_health_factor(address: str, contract, w3, market_manager_address: str = None, known_market_managers: List[str] = None) -> Optional[float]:
    """
    Check health factor for Curvance protocol using ProtocolReader.getPositionHealth.
    
    Args:
        address: User's wallet address
        contract: ProtocolReader contract instance
        w3: Web3 instance
        market_manager_address: Specific MarketManager contract address (if provided, only check this one)
        known_market_managers: List of MarketManager addresses to try (if market_manager_address not provided)
    
    Returns:
        Health factor as float (worst health across all positions), or None if error
    """
    try:
        # Convert address to checksum format
        address_checksum = w3.to_checksum_address(address)
        
        # First, get all positions to know which markets to check
        result = contract.functions.getAllDynamicState(address_checksum).call()
        market_data, user_data = result
        
        # Extract positions from user_data
        # user_data is a tuple: (veCVE[], positions[])
        positions = user_data[1]  # user_data[1] is the positions array
        
        if not positions or len(positions) == 0:
            # No positions found
            logger.debug(f"No Curvance positions found for {address}")
            return None
        
        # Determine which MarketManagers to try
        market_managers_to_try = []
        if market_manager_address:
            # User specified a specific MarketManager
            market_managers_to_try = [market_manager_address.lower()]
        elif known_market_managers:
            # Use provided list
            market_managers_to_try = [mm.lower() for mm in known_market_managers]
        else:
            # Query Central Registry for all MarketManagers
            market_managers_to_try = get_curvance_market_managers(w3)
        
        # If no MarketManagers to try, fallback to getAllDynamicState health
        if not market_managers_to_try:
            logger.warning("No MarketManager addresses provided for Curvance getPositionHealth")
            # Fallback: try to use health from getAllDynamicState if available
            health_factors = []
            for position in positions:
                health_raw = position[3]  # health is at index 3
                if health_raw > 0:
                    health_factor = health_raw / 1e18
                    health_factors.append(health_factor)
            
            if health_factors:
                return min(health_factors)
            return None
        
        # Use getPositionHealth for each position
        # Try each MarketManager to find which one has positions for this user
        zero_address = '0x0000000000000000000000000000000000000000'
        health_factors = []
        
        for position in positions:
            # position structure: (cToken, collateral, debt, health, tokenBalance)
            cToken = position[0]
            collateral = position[1]
            debt = position[2]
            
            # Skip if no debt (no loan position)
            if debt == 0:
                continue
            
            # Try each MarketManager until we find one that works
            position_health_found = False
            for mm_address in market_managers_to_try:
                try:
                    # Call getPositionHealth to check existing position
                    # Parameters: (mm, account, cToken, borrowableCToken, isDeposit, collateralAssets, isRepayment, debtAssets, bufferTime)
                    # For checking existing position: use zero for borrowableCToken and zero amounts
                    health_result = contract.functions.getPositionHealth(
                        w3.to_checksum_address(mm_address),  # IMarketManager mm
                        address_checksum,  # address account
                        cToken,  # address cToken (collateral token)
                        zero_address,  # address borrowableCToken (try zero first, might need actual address)
                        False,  # bool isDeposit (false = check existing, not simulating deposit)
                        0,  # uint256 collateralAssets (0 = check existing position)
                        False,  # bool isRepayment (false = check existing, not simulating repayment)
                        0,  # uint256 debtAssets (0 = check existing position)
                        0  # uint256 bufferTime
                    ).call()
                    
                    position_health_raw, error_code_hit = health_result
                    
                    if error_code_hit:
                        # Try next MarketManager
                        continue
                    
                    if position_health_raw > 0:
                        # Health factor is in 18 decimals (1e18 = 1.0)
                        # Note: 151% = 1.51, so 1510000000000000000 / 1e18 = 1.51
                        health_factor = position_health_raw / 1e18
                        health_factors.append(health_factor)
                        logger.debug(f"Curvance position: cToken={cToken}, MarketManager={mm_address}, health={health_factor:.4f} ({health_factor*100:.1f}%)")
                        position_health_found = True
                        break  # Found working MarketManager for this position
                    else:
                        # Health is 0, might be wrong MarketManager, try next
                        continue
                        
                except Exception as e:
                    # Try next MarketManager
                    logger.debug(f"Error calling getPositionHealth with MarketManager {mm_address} for cToken {cToken}: {e}")
                    continue
            
            # If no MarketManager worked, try fallback
            if not position_health_found:
                logger.debug(f"No working MarketManager found for cToken {cToken}, using fallback")
                health_raw = position[3]
                if health_raw > 0:
                    health_factor = health_raw / 1e18
                    health_factors.append(health_factor)
                    logger.debug(f"Using fallback health from getAllDynamicState: {health_factor:.4f}")
        
        if health_factors:
            # Return worst (lowest) health factor
            worst_hf = min(health_factors)
            logger.debug(f"Curvance worst health factor: {worst_hf:.4f}")
            return worst_hf
        else:
            return None
            
    except Exception as e:
        logger.error(f"Error checking Curvance health factor for {address}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None

def get_curvance_position_details(address: str, contract, w3, market_manager_address: str = None, known_market_managers: List[str] = None) -> List[Dict]:
    """
    Get Curvance position details including token symbols and raw amounts.
    
    Args:
        address: User's wallet address
        contract: ProtocolReader contract instance
        w3: Web3 instance
        market_manager_address: Specific MarketManager contract address
        known_market_managers: List of MarketManager addresses
    
    Returns:
        List of position dicts with: cToken, collateral_token_symbol, collateral_amount, debt_token_symbol, debt_amount
    """
    position_details = []
    
    try:
        address_checksum = w3.to_checksum_address(address)
        result = contract.functions.getAllDynamicState(address_checksum).call()
        market_data, user_data = result
        positions = user_data[1]  # positions array
        
        if not positions:
            return []
        
        # ERC20 ABI for symbol and decimals
        erc20_abi = [
            {"inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
            {"inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"}
        ]
        
        for position in positions:
            # position structure: (cToken, collateral, debt, health, tokenBalance)
            cToken = position[0]
            collateral_raw = position[1]
            debt_raw = position[2]
            
            # Skip if no debt
            if debt_raw == 0:
                continue
            
            # Get token symbol and decimals
            try:
                token_contract = w3.eth.contract(address=cToken, abi=erc20_abi)
                collateral_symbol = token_contract.functions.symbol().call()
                collateral_decimals = token_contract.functions.decimals().call()
                
                # Convert to human-readable amount (3 sig fig)
                collateral_amount = collateral_raw / (10 ** collateral_decimals)
                
                # For debt, we need to find the borrowable token - this is complex
                # For now, we'll use a placeholder or try to get it from MarketManager
                # This is a simplified version - full implementation would need MarketManager query
                debt_symbol = "?"  # Would need MarketManager to get borrowable token
                debt_decimals = 18  # Default assumption
                debt_amount = debt_raw / (10 ** debt_decimals)
                
                position_details.append({
                    'cToken': cToken,
                    'collateral_token': collateral_symbol,
                    'collateral_amount': collateral_amount,
                    'debt_token': debt_symbol,
                    'debt_amount': debt_amount
                })
            except Exception as e:
                logger.debug(f"Error getting token info for cToken {cToken}: {e}")
                # Still add position with raw amounts
                position_details.append({
                    'cToken': cToken,
                    'collateral_token': '?',
                    'collateral_amount': collateral_raw,
                    'debt_token': '?',
                    'debt_amount': debt_raw
                })
        
        return position_details
    except Exception as e:
        logger.error(f"Error getting Curvance position details for {address}: {e}")
        return []


def check_euler_health_factor(address: str, contract, w3) -> Optional[float]:
    """
    Check health factor for Euler V2 protocol using accountLens.
    
    Args:
        address: User's wallet address
        contract: accountLens contract instance
        w3: Web3 instance
    
    Returns:
        Health factor as float, or None if error
    """
    try:
        address_checksum = w3.to_checksum_address(address)
        
        # Try to get account health from accountLens
        # accountLens typically has getAccountHealth or similar function
        try:
            # Try getAccountHealth function (common in Euler V2 lens contracts)
            health_result = contract.functions.getAccountHealth(address_checksum).call()
            
            # Health factor might be returned as (healthFactor, isHealthy) or just healthFactor
            if isinstance(health_result, (list, tuple)):
                health_factor_raw = health_result[0]
            else:
                health_factor_raw = health_result
            
            # Euler V2 health factors are typically in 18 decimals (1e18 = 1.0)
            health_factor = health_factor_raw / 1e18
            
            # Filter out invalid values (like max uint256)
            if health_factor > 1e10:
                return None
            
            return health_factor
        except AttributeError:
            # If getAccountHealth doesn't exist, try alternative methods
            try:
                # Try getAccountStatus or getAccountInfo
                account_info = contract.functions.getAccountStatus(address_checksum).call()
                if isinstance(account_info, (list, tuple)) and len(account_info) > 0:
                    health_factor_raw = account_info[0]
                    health_factor = health_factor_raw / 1e18
                    if health_factor > 1e10:
                        return None
                    return health_factor
            except AttributeError:
                logger.debug("Euler accountLens doesn't have expected methods, trying EVC directly")
                # Fallback: query EVC (Euler Vault Controller) directly
                evc_address = '0x7a9324E8f270413fa2E458f5831226d99C7477CD'
                evc_abi = [
                    {
                        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                        "name": "getAccountHealth",
                        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]
                evc_contract = w3.eth.contract(address=w3.to_checksum_address(evc_address), abi=evc_abi)
                health_factor_raw = evc_contract.functions.getAccountHealth(address_checksum).call()
                health_factor = health_factor_raw / 1e18
                if health_factor > 1e10:
                    return None
                return health_factor
        
        return None
    except Exception as e:
        logger.error(f"Error checking Euler health factor for {address}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None

def get_euler_account_data(address: str, contract, w3) -> Optional[Dict]:
    """
    Get Euler account data including collateral and debt values.
    
    Args:
        address: User's wallet address
        contract: accountLens contract instance
        w3: Web3 instance
    
    Returns:
        Dict with 'collateral_usd', 'debt_usd', 'health_factor', or None if error
    """
    try:
        address_checksum = w3.to_checksum_address(address)
        
        # Try to get account balances/values from accountLens
        try:
            # Try getAccountBalances or getAccountValues
            account_data = contract.functions.getAccountBalances(address_checksum).call()
            
            # Parse the result - structure depends on Euler V2 implementation
            # Typically returns: (collateralValue, debtValue, ...)
            if isinstance(account_data, (list, tuple)):
                collateral_raw = account_data[0] if len(account_data) > 0 else 0
                debt_raw = account_data[1] if len(account_data) > 1 else 0
                
                # Values are typically in 18 decimals, convert to USD (assuming 1:1 for now)
                # In production, would need price oracle
                collateral_usd = collateral_raw / 1e18
                debt_usd = debt_raw / 1e18
                
                # Get health factor
                health_factor = check_euler_health_factor(address, contract, w3)
                
                return {
                    'collateral_usd': collateral_usd,
                    'debt_usd': debt_usd,
                    'health_factor': health_factor
                }
        except AttributeError:
            # If method doesn't exist, try alternative
            logger.debug("Euler accountLens doesn't have getAccountBalances, using health factor only")
            health_factor = check_euler_health_factor(address, contract, w3)
            if health_factor:
                return {
                    'collateral_usd': 0,  # Would need price oracle for accurate values
                    'debt_usd': 0,
                    'health_factor': health_factor
                }
        
        return None
    except Exception as e:
        logger.error(f"Error getting Euler account data for {address}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None

def get_euler_user_vaults(address: str, w3, account_lens_address: str = None, vault_lens_address: str = None) -> List[Dict]:
    """
    Get list of Euler vaults where user has positions using vaultLens.
    Euler V2 uses isolated vaults, so we need to discover which vaults the user has positions in.
    
    Args:
        address: User's wallet address
        w3: Web3 instance
        account_lens_address: accountLens contract address (for account-level queries)
        vault_lens_address: vaultLens contract address (for vault discovery)
    
    Returns:
        List of dicts with vault info: [{'vault_address': '0x...', 'health_factor': 1.5, ...}, ...]
    """
    vaults = []
    
    try:
        address_checksum = w3.to_checksum_address(address)
        
        # Use vaultLens to get user's vault positions
        # vaultLens typically has getAccountVaults or similar function
        vault_lens_addr = vault_lens_address or '0x15d1Cc54fB3f7C0498fc991a23d8Dc00DF3c32A0'
        
        # Minimal vaultLens ABI for discovering vaults
        vault_lens_abi = [
            {
                "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                "name": "getAccountVaults",
                "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "account", "type": "address"},
                    {"internalType": "address", "name": "vault", "type": "address"}
                ],
                "name": "getVaultPosition",
                "outputs": [
                    {"internalType": "uint256", "name": "healthFactor", "type": "uint256"},
                    {"internalType": "uint256", "name": "collateralValue", "type": "uint256"},
                    {"internalType": "uint256", "name": "debtValue", "type": "uint256"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        vault_lens_contract = w3.eth.contract(
            address=w3.to_checksum_address(vault_lens_addr),
            abi=vault_lens_abi
        )
        
        # Get list of vaults where user has positions
        user_vaults = []
        try:
            user_vaults = vault_lens_contract.functions.getAccountVaults(address_checksum).call()
            logger.info(f"Found {len(user_vaults)} vaults via getAccountVaults for {address}")
        except Exception as e:
            logger.warning(f"getAccountVaults failed: {e}")
            # Try alternative method: query EVC directly
            try:
                evc_address = '0x7a9324E8f270413fa2E458f5831226d99C7477CD'
                evc_abi = [
                    {
                        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                        "name": "getAccountVaults",
                        "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]
                evc_contract = w3.eth.contract(address=w3.to_checksum_address(evc_address), abi=evc_abi)
                user_vaults = evc_contract.functions.getAccountVaults(address_checksum).call()
                logger.info(f"Found {len(user_vaults)} vaults via EVC getAccountVaults for {address}")
            except Exception as e2:
                logger.warning(f"EVC getAccountVaults also failed: {e2}")
                # Last resort: try querying known vaults directly
                # From the user's URL, we know one vault: 0x28bD4F19C812CBF9e33A206f87125f14E65dc8aA
                # But we should query all possible vaults from eVaultFactory
                logger.debug("Trying to query known vaults directly")
                user_vaults = []
        
        # Query each vault for position details
        for vault_address in user_vaults:
            try:
                # Get position details for this vault
                position_data = vault_lens_contract.functions.getVaultPosition(
                    address_checksum,
                    vault_address
                ).call()
                
                health_factor_raw = position_data[0]
                collateral_value_raw = position_data[1]
                debt_value_raw = position_data[2]
                
                # Convert from 18 decimals
                health_factor = health_factor_raw / 1e18
                collateral_usd = collateral_value_raw / 1e18
                debt_usd = debt_value_raw / 1e18
                
                # Filter invalid positions
                if health_factor > 1e10 or debt_usd == 0:
                    logger.debug(f"Skipping invalid Euler vault {vault_address}: hf={health_factor}, debt={debt_usd}")
                    continue
                
                vaults.append({
                    'vault_address': vault_address,
                    'health_factor': health_factor,
                    'collateral_usd': collateral_usd,
                    'debt_usd': debt_usd
                })
                logger.info(f"Found Euler vault position: {vault_address}, hf={health_factor:.3f}")
                
            except Exception as e:
                logger.warning(f"Error getting position for vault {vault_address}: {e}")
                continue
        
        # If still no vaults found, try querying known vault directly (from user's URL)
        if not vaults:
            logger.debug("No vaults found via discovery, trying known vault from user URL")
            known_vault = '0x28bD4F19C812CBF9e33A206f87125f14E65dc8aA'  # From user's Euler URL
            try:
                position_data = vault_lens_contract.functions.getVaultPosition(
                    address_checksum,
                    known_vault
                ).call()
                
                health_factor_raw = position_data[0]
                collateral_value_raw = position_data[1]
                debt_value_raw = position_data[2]
                
                health_factor = health_factor_raw / 1e18
                collateral_usd = collateral_value_raw / 1e18
                debt_usd = debt_value_raw / 1e18
                
                if health_factor <= 1e10 and debt_usd > 0:
                    vaults.append({
                        'vault_address': known_vault,
                        'health_factor': health_factor,
                        'collateral_usd': collateral_usd,
                        'debt_usd': debt_usd
                    })
                    logger.info(f"Found Euler vault via known vault query: {known_vault}, hf={health_factor:.3f}")
            except Exception as e:
                logger.debug(f"Known vault query also failed: {e}")
        
        # If no vaults found via vaultLens, try accountLens as fallback
        if not vaults and account_lens_address:
            try:
                account_lens_abi = [
                    {
                        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                        "name": "getAccountHealth",
                        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]
                account_lens_contract = w3.eth.contract(
                    address=w3.to_checksum_address(account_lens_address),
                    abi=account_lens_abi
                )
                health_factor_raw = account_lens_contract.functions.getAccountHealth(address_checksum).call()
                health_factor = health_factor_raw / 1e18
                
                if health_factor <= 1e10:
                    vaults.append({
                        'vault_address': None,  # Unknown vault
                        'health_factor': health_factor,
                        'collateral_usd': 0,
                        'debt_usd': 0
                    })
            except Exception as e:
                logger.debug(f"Fallback to accountLens also failed: {e}")
        
        if vaults:
            logger.info(f"Found {len(vaults)} Euler vault positions for {address}")
        
    except Exception as e:
        logger.error(f"Error getting Euler user vaults for {address}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    
    return vaults


def check_neverland_health_factor(address: str, contract, w3) -> Optional[float]:
    """
    Check health factor for Neverland protocol.
    
    Args:
        address: User's wallet address
        contract: Web3 contract instance
        w3: Web3 instance
    
    Returns:
        Health factor as float, or None if error
    """
    try:
        # Convert address to checksum format (Web3.py requires checksum addresses)
        address_checksum = w3.to_checksum_address(address)
        account_data = contract.functions.getUserAccountData(address_checksum).call()
        # Health factor is at index 5 (0-indexed)
        health_factor_raw = account_data[5]
        health_factor = health_factor_raw / 1e18
        return health_factor
    except Exception as e:
        logger.error(f"Error checking Neverland health factor for {address}: {e}")
        return None

def get_neverland_account_data(address: str, contract, w3) -> Optional[Dict]:
    """
    Get Neverland account data including collateral and debt values.
    
    Args:
        address: User's wallet address
        contract: Web3 contract instance
        w3: Web3 instance
    
    Returns:
        Dict with 'collateral_usd', 'debt_usd', 'health_factor', or None if error
    """
    try:
        address_checksum = w3.to_checksum_address(address)
        account_data = contract.functions.getUserAccountData(address_checksum).call()
        # getUserAccountData returns: [totalCollateralBase, totalDebtBase, availableBorrowsBase, 
        #                              currentLiquidationThreshold, ltv, healthFactor]
        # Values are in base currency (typically USD) with 8 decimals
        collateral_base = account_data[0] / 1e8  # Convert from 8 decimals to USD
        debt_base = account_data[1] / 1e8  # Convert from 8 decimals to USD
        health_factor_raw = account_data[5]
        health_factor = health_factor_raw / 1e18
        
        return {
            'collateral_usd': collateral_base,
            'debt_usd': debt_base,
            'health_factor': health_factor
        }
    except Exception as e:
        logger.error(f"Error getting Neverland account data for {address}: {e}")
        return None


def get_morpho_user_vaults(address: str, chain_id: int = 143) -> List[Dict]:
    """
    Get list of vaults where user has positions.
    First tries GraphQL API, then falls back to querying known vault contracts directly.
    
    Args:
        address: User's wallet address
        chain_id: Chain ID (143 for Monad, 1 for Ethereum)
    
    Returns:
        List of dicts with vault info: [{'address': '0x...', 'name': '...', 'assets': '...', 'assetsUsd': 1000, ...}, ...]
    """
    vaults = []
    
    # Known Morpho vaults on Monad (can be expanded)
    # Format: (vault_address, vault_name, asset_symbol)
    known_vaults_monad = [
        ('0xbeEFf443C3CbA3E369DA795002243BeaC311aB83', 'Steakhouse High Yield USDC', 'USDC'),
        ('0xbeeffeA75cFC4128ebe10C8D7aE22016D215060D', 'Steakhouse High Yield AUSD', 'AUSD'),
    ]
    
    # Try GraphQL API first
    try:
        query = """
        query GetUserVaults($address: String!, $chainId: Int!) {
            userByAddress(
                chainId: $chainId
                address: $address
            ) {
                vaultPositions {
                    vault {
                        address
                        name
                    }
                    assets
                    assetsUsd
                    shares
                }
            }
        }
        """
        
        variables = {
            "address": address.lower(),
            "chainId": chain_id
        }
        
        response = requests.post(
            MORPHO_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'errors' in data:
                logger.error(f"Morpho GraphQL vault errors: {data['errors']}")
                for error in data['errors']:
                    logger.error(f"  GraphQL Error: {error.get('message', error)}")
            
            if 'data' in data and data['data']:
                user_data = data['data'].get('userByAddress')
                if user_data:
                    positions = user_data.get('vaultPositions', [])
                    
                    for pos in positions:
                        vault = pos.get('vault', {})
                        vault_address = vault.get('address')
                        if vault_address:
                            vaults.append({
                                'address': vault_address,
                                'name': vault.get('name', 'Unknown'),
                                'assets': pos.get('assets', '0'),
                                'assetsUsd': pos.get('assetsUsd', 0),
                                'shares': pos.get('shares', '0')
                            })
                    
                    if vaults:
                        logger.info(f"Found {len(vaults)} Morpho vaults for {address} on chain {chain_id} via GraphQL API")
                        return vaults
    except Exception as e:
        logger.debug(f"Morpho GraphQL API vault error: {e}")
    
    # Fallback: Query known vault contracts directly
    logger.info(f"GraphQL returned no vaults, querying known vault contracts directly for {address}")
    
    try:
        # Get Web3 connection for Monad
        rpc_url = os.environ.get('MONAD_NODE_URL', 'https://rpc.monad.xyz')
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        if not w3.is_connected():
            logger.error("Failed to connect to Monad RPC")
            return []
        
        # ERC4626 vault ABI (standard vault interface)
        # balanceOf(address) -> uint256: user's share balance
        # convertToAssets(uint256) -> uint256: convert shares to assets
        vault_abi = [
            {
                "inputs": [{"name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"name": "shares", "type": "uint256"}],
                "name": "convertToAssets",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "asset",
                "outputs": [{"name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        address_checksum = w3.to_checksum_address(address)
        
        # Check each known vault
        for vault_address, vault_name, asset_symbol in known_vaults_monad:
            try:
                vault_contract = w3.eth.contract(address=w3.to_checksum_address(vault_address), abi=vault_abi)
                
                # Get user's share balance
                shares = vault_contract.functions.balanceOf(address_checksum).call()
                
                if shares > 0:
                    # Convert shares to assets
                    assets = vault_contract.functions.convertToAssets(shares).call()
                    
                    # Get asset contract to get decimals and symbol
                    asset_address = vault_contract.functions.asset().call()
                    erc20_abi = [
                        {"inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
                        {"inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "stateMutability": "view", "type": "function"}
                    ]
                    
                    try:
                        asset_contract = w3.eth.contract(address=asset_address, abi=erc20_abi)
                        decimals = asset_contract.functions.decimals().call()
                        asset_symbol_actual = asset_contract.functions.symbol().call()
                        
                        # Convert to human-readable amount
                        assets_human = assets / (10 ** decimals)
                        
                        # Estimate USD value (simplified - would need price oracle for accurate USD)
                        # For stablecoins like USDC/USDT/AUSD, assume 1:1 with USD
                        assets_usd = assets_human if asset_symbol_actual in ['USDC', 'USDT', 'AUSD'] else 0
                        
                        vaults.append({
                            'address': vault_address,
                            'name': vault_name,
                            'assets': str(assets),
                            'assetsUsd': assets_usd,
                            'shares': str(shares),
                            'assetSymbol': asset_symbol_actual
                        })
                        
                        logger.info(f"Found vault position: {vault_name} - {assets_human:.2f} {asset_symbol_actual}")
                    except Exception as e:
                        logger.debug(f"Error getting asset info for vault {vault_address}: {e}")
                        # Still add vault with estimated values
                        vaults.append({
                            'address': vault_address,
                            'name': vault_name,
                            'assets': str(assets),
                            'assetsUsd': 0,  # Unknown USD value
                            'shares': str(shares),
                            'assetSymbol': asset_symbol
                        })
            except Exception as e:
                logger.debug(f"Error querying vault {vault_address}: {e}")
                continue
        
        if vaults:
            logger.info(f"Found {len(vaults)} Morpho vaults for {address} via direct contract queries")
            return vaults
            
    except Exception as e:
        logger.error(f"Error querying vault contracts directly: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    
    return []


def get_morpho_user_markets(address: str, chain_id: int = 143) -> List[Dict]:
    """
    Get list of markets where user has positions using Morpho's GraphQL API.
    
    Args:
        address: User's wallet address
        chain_id: Chain ID (143 for Monad, 1 for Ethereum)
    
    Returns:
        List of dicts with market info: [{'id': '0x...', 'healthFactor': 1.5, ...}, ...]
    """
    markets = []
    
    try:
        query = """
        query GetUserPositions($address: String!, $chainId: Int!) {
            userByAddress(
                chainId: $chainId
                address: $address
            ) {
                address
                marketPositions {
                    market {
                        uniqueKey
                        loanAsset {
                            symbol
                        }
                        collateralAsset {
                            symbol
                        }
                    }
                    healthFactor
                    state {
                        collateral
                        borrowAssets
                        borrowAssetsUsd
                    }
                    borrowAssets
                    borrowAssetsUsd
                    supplyAssets
                    supplyAssetsUsd
                }
            }
        }
        """
        
        variables = {
            "address": address.lower(),
            "chainId": chain_id
        }
        
        response = requests.post(
            MORPHO_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'errors' in data:
                logger.error(f"Morpho GraphQL errors: {data['errors']}")
                for error in data['errors']:
                    logger.error(f"  GraphQL Error: {error.get('message', error)}")
            
            if 'data' in data and data['data']:
                user_data = data['data'].get('userByAddress')
                if user_data:
                    positions = user_data.get('marketPositions', [])
                    
                    for pos in positions:
                        market = pos.get('market', {})
                        market_unique_key = market.get('uniqueKey')
                        if market_unique_key:
                            loan_asset = market.get('loanAsset', {})
                            collateral_asset = market.get('collateralAsset', {})
                            loan_symbol = loan_asset.get('symbol', '?')
                            collateral_symbol = collateral_asset.get('symbol', '?')
                            market_name = f"{collateral_symbol}-{loan_symbol}".lower()
                            
                            markets.append({
                                'id': market_unique_key,
                                'name': market_name,
                                'loanAsset': loan_symbol,
                                'collateralAsset': collateral_symbol,
                                'healthFactor': pos.get('healthFactor'),
                                'borrowAssets': pos.get('borrowAssets', '0'),
                                'borrowAssetsUsd': pos.get('borrowAssetsUsd', 0),
                                'supplyAssets': pos.get('supplyAssets', '0'),
                                'supplyAssetsUsd': pos.get('supplyAssetsUsd', 0),
                                'collateral': pos.get('state', {}).get('collateral') if pos.get('state') else pos.get('collateral')
                            })
                    
                    if markets:
                        logger.info(f"Found {len(markets)} Morpho markets for {address} on chain {chain_id} via GraphQL API")
                        return markets
                    else:
                        logger.debug(f"User {address} found but no market positions on chain {chain_id}")
                else:
                    logger.debug(f"No user data found for {address} on chain {chain_id} in Morpho API")
            else:
                logger.debug(f"No data in response for {address} on chain {chain_id}")
        else:
            logger.debug(f"Morpho GraphQL API returned status {response.status_code}: {response.text}")
            
    except Exception as e:
        logger.error(f"Morpho GraphQL API error: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    
    return []


def check_morpho_health_factor_all_markets(address: str, market_id: Optional[str] = None, chain_id: int = 143) -> Optional[float]:
    """
    Check Morpho health factor across all markets where user has positions.
    Uses GraphQL API first (which provides health factors directly), falls back to contract calls.
    
    Args:
        address: User's wallet address
        market_id: Optional specific market ID to check
        chain_id: Chain ID (143 for Monad, 1 for Ethereum)
    
    Returns:
        Health factor as float, or None if no positions found.
    """
    # First, try to get health factors directly from GraphQL API
    markets_data = get_morpho_user_markets(address, chain_id)
    
    if markets_data:
        # Filter by market_id if specified
        if market_id:
            market_id_lower = market_id.lower()
            markets_data = [m for m in markets_data if m['id'].lower() == market_id_lower]
        
        if markets_data:
            # Extract health factors from API response
            health_factors = []
            for market in markets_data:
                hf = market.get('healthFactor')
                if hf is not None:
                    try:
                        hf_float = float(hf)
                        health_factors.append(hf_float)
                    except (ValueError, TypeError):
                        pass
            
            if health_factors:
                # Return worst (lowest) health factor
                return min(health_factors)
    
    # No markets found
    logger.warning(f"No markets found for {address} via API. User may need to specify market ID.")
    return None


def calculate_repayment_needed(current_hf: float, target_hf: float, borrow_amount: float, collateral_value: float, lltv: float) -> float:
    """
    Calculate exact repayment amount needed to bring health factor from current_hf to target_hf.
    
    Morpho Health Factor Formula: HF = (Collateral * LLTV) / Borrowed
    
    To increase HF from current_hf to target_hf:
    - Current: HF_current = (Collateral * LLTV) / Borrowed_current
    - Target: HF_target = (Collateral * LLTV) / Borrowed_target
    - Solving: Borrowed_target = (Collateral * LLTV) / HF_target
    - Repayment needed = Borrowed_current - Borrowed_target
    
    Args:
        current_hf: Current health factor
        target_hf: Target health factor (should be > current_hf)
        borrow_amount: Current borrowed amount
        collateral_value: Current collateral value
        lltv: Liquidation Loan-to-Value (in 18 decimals, e.g., 0.75e18)
    
    Returns:
        Repayment amount needed (in same units as borrow_amount)
    """
    if current_hf >= target_hf:
        return 0.0
    
    if collateral_value == 0 or lltv == 0:
        return borrow_amount  # Repay all if no collateral
    
    # Calculate target borrowed amount
    # HF_target = (Collateral * LLTV) / Borrowed_target
    # Borrowed_target = (Collateral * LLTV) / HF_target
    target_borrowed = (collateral_value * lltv) / (target_hf * 1e18)  # LLTV is in 18 decimals
    
    # Repayment needed = current_borrowed - target_borrowed
    repayment_needed = borrow_amount - target_borrowed
    
    # Can't repay more than borrowed
    return max(0.0, min(repayment_needed, borrow_amount))


def get_morpho_market_details(address: str, market_id: str, chain_id: int = 143) -> Optional[Dict]:
    """
    Get detailed market information including loan asset, borrow amount, collateral, and LLTV.
    
    Args:
        address: User's wallet address
        market_id: Market ID (hex bytes32)
        chain_id: Chain ID
    
    Returns:
        Dict with market details or None
    """
    markets = get_morpho_user_markets(address, chain_id)
    if not markets:
        return None
    
    # Find the specific market
    market_id_lower = market_id.lower()
    for market in markets:
        if market['id'].lower() == market_id_lower:
            return market
    
    return None


def check_morpho_health_factor_single_market(address: str, market_id: str, contract, w3) -> Optional[float]:
    """
    Check Morpho health factor for a specific market using contract calls.
    
    Args:
        address: User's wallet address
        market_id: Market ID as hex string (bytes32 hash)
        contract: Web3 contract instance
        w3: Web3 instance
    
    Returns:
        Health factor as float, or None if error or no position
    """
    try:
        # Market ID is bytes32 - ensure it's properly formatted
        market_id_clean = market_id.replace('0x', '').lower()
        if len(market_id_clean) != 64:
            logger.error(f"Invalid market ID format: {market_id} (expected 64 hex chars)")
            return None
        
        # Convert to bytes32 format for contract call
        market_id_bytes32 = bytes.fromhex(market_id_clean)
        
        # Convert address to checksum format
        try:
            address_checksum = w3.to_checksum_address(address)
        except Exception as e:
            logger.error(f"Invalid address format: {address}, error: {e}")
            return None
        
        # Get position data
        position_data = contract.functions.position(market_id_bytes32, address_checksum).call()
        market_params, market, user_position = position_data
        
        # Extract position data
        supply_shares = user_position[0]
        borrow_shares = user_position[1]
        collateral = user_position[2]
        
        # If no borrow shares, position is healthy (no debt)
        if borrow_shares == 0:
            return float('inf')
        
        # Get market data for calculations
        total_supply_assets = market[0]
        total_supply_shares = market[1]
        total_borrow_assets = market[2]
        total_borrow_shares = market[3]
        
        # Convert shares to assets
        if total_supply_shares > 0:
            supply_assets = (supply_shares * total_supply_assets) // total_supply_shares
        else:
            supply_assets = 0
            
        if total_borrow_shares > 0:
            borrow_assets = (borrow_shares * total_borrow_assets) // total_borrow_shares
        else:
            borrow_assets = 0
        
        # Get LLTV from market params
        lltv = market_params[4] if len(market_params) > 4 else 0
        
        # If no borrow assets, position is healthy
        if borrow_assets == 0:
            return float('inf')
        
        # Calculate health factor
        # Health Factor = (Collateral Value * LLTV) / Borrowed Amount
        collateral_value = supply_assets + collateral
        health_factor = (collateral_value * lltv) / (borrow_assets * 1e18)  # LLTV is in 18 decimals
        
        return health_factor
        
    except Exception as e:
        logger.error(f"Error checking Morpho health factor for market {market_id}: {e}")
        return None

