"""
Rebalancing logic for automatic loan repayment suggestions.
Checks vault balances and suggests actions when health factor drops below threshold.
"""
import logging
from typing import Optional, List, Dict, Tuple
import protocols

logger = logging.getLogger(__name__)


def get_vault_balances_by_asset(address: str, chain_id: int = 143) -> Dict[str, Dict]:
    """
    Get vault balances aggregated by asset symbol.
    
    Args:
        address: User's wallet address
        chain_id: Chain ID
    
    Returns:
        Dict mapping asset symbol to vault info:
        {
            'USDC': {
                'total_assets': '1000000000',  # Raw amount (wei)
                'total_assets_usd': 1000.0,    # USD value
                'vaults': [
                    {'address': '0x...', 'name': 'Steakhouse High Yield USDC', 'assets': '...', 'assetsUsd': 1000}
                ]
            },
            ...
        }
    """
    vaults = protocols.get_morpho_user_vaults(address, chain_id)
    if not vaults:
        return {}
    
    # Group vaults by asset (extract from vault name or need to query vault asset)
    # For now, we'll need to extract asset from vault name or query vault contract
    # Since vault names like "Steakhouse High Yield USDC" contain the asset, we can parse it
    balances_by_asset = {}
    
    for vault in vaults:
        vault_name = vault.get('name', '')
        # Try to get asset symbol from vault data first (from contract query)
        asset_symbol = vault.get('assetSymbol')
        
        # Fallback: Extract asset symbol from vault name
        if not asset_symbol:
            common_assets = ['USDC', 'USDT', 'AUSD', 'WETH', 'WBTC', 'ETH', 'BTC']
            for asset in common_assets:
                if asset in vault_name.upper():
                    asset_symbol = asset
                    break
            
            if not asset_symbol:
                # Fallback: use last word or parse differently
                words = vault_name.upper().split()
                if words:
                    asset_symbol = words[-1]  # Assume last word is asset
        
        if asset_symbol:
            if asset_symbol not in balances_by_asset:
                balances_by_asset[asset_symbol] = {
                    'total_assets': 0,
                    'total_assets_usd': 0.0,
                    'vaults': []
                }
            
            assets_raw = int(vault.get('assets', '0'))
            assets_usd = float(vault.get('assetsUsd', 0))
            
            balances_by_asset[asset_symbol]['total_assets'] += assets_raw
            balances_by_asset[asset_symbol]['total_assets_usd'] += assets_usd
            balances_by_asset[asset_symbol]['vaults'].append(vault)
    
    return balances_by_asset


def calculate_collateral_needed(current_hf: float, target_hf: float, borrow_amount: float, lltv: float) -> float:
    """
    Calculate collateral amount needed to bring health factor from current_hf to target_hf.
    
    Morpho Health Factor Formula: HF = (Collateral * LLTV) / Borrowed
    
    To increase HF from current_hf to target_hf:
    - Current: HF_current = (Collateral_current * LLTV) / Borrowed
    - Target: HF_target = (Collateral_target * LLTV) / Borrowed
    - Solving: Collateral_target = (HF_target * Borrowed) / LLTV
    - Collateral needed = Collateral_target - Collateral_current
    
    Args:
        current_hf: Current health factor
        target_hf: Target health factor
        borrow_amount: Current borrowed amount
        lltv: Liquidation Loan-to-Value (in 18 decimals)
    
    Returns:
        Additional collateral needed
    """
    if current_hf >= target_hf:
        return 0.0
    
    if lltv == 0:
        return float('inf')  # Can't calculate if no LLTV
    
    # Calculate current collateral from HF
    # HF_current = (Collateral_current * LLTV) / Borrowed
    # Collateral_current = (HF_current * Borrowed) / LLTV
    current_collateral = (current_hf * borrow_amount * 1e18) / lltv
    
    # Calculate target collateral
    # Collateral_target = (HF_target * Borrowed) / LLTV
    target_collateral = (target_hf * borrow_amount * 1e18) / lltv
    
    # Additional collateral needed
    collateral_needed = target_collateral - current_collateral
    
    return max(0.0, collateral_needed)


def generate_rebalancing_message(
    address: str,
    protocol_id: str,
    market_id: Optional[str],
    current_hf: float,
    threshold: float,
    chain_id: int = 143
) -> Optional[str]:
    """
    Generate rebalancing message with repayment and collateral deposit suggestions.
    
    Args:
        address: User's wallet address
        protocol_id: Protocol identifier
        market_id: Market ID (for Morpho)
        current_hf: Current health factor
        threshold: Target threshold
        chain_id: Chain ID
    
    Returns:
        Formatted message string or None if no suggestions
    """
    if protocol_id != 'morpho':
        # For now, only support Morpho rebalancing
        return None
    
    # Get worst market details
    markets = protocols.get_morpho_user_markets(address, chain_id)
    if not markets:
        return None
    
    # Find worst (lowest HF) market
    worst_market = min(markets, key=lambda x: x.get('healthFactor', float('inf')))
    
    # If market_id specified, use that instead
    if market_id:
        market_id_lower = market_id.lower()
        for market in markets:
            if market['id'].lower() == market_id_lower:
                worst_market = market
                break
    
    loan_asset = worst_market.get('loanAsset', '?')
    collateral_asset = worst_market.get('collateralAsset', '?')
    borrow_assets_usd = worst_market.get('borrowAssetsUsd', 0)
    supply_assets_usd = worst_market.get('supplyAssetsUsd', 0)
    
    # Calculate repayment needed (simplified - would need LLTV from contract)
    # For now, estimate based on HF ratio
    target_hf = threshold * 1.1  # Target 10% above threshold for safety
    repayment_needed_usd = borrow_assets_usd * (1 - (current_hf / target_hf))
    
    message_parts = []
    message_parts.append(f"⚠️ Health Factor Alert: {current_hf:.3f} < {threshold:.3f}")
    message_parts.append(f"\nAddress: `{address}`")
    message_parts.append(f"Protocol: Morpho")
    message_parts.append(f"\nMarket: {worst_market.get('name', 'Unknown').upper()}")
    message_parts.append(f"Loan Asset: {loan_asset}")
    message_parts.append(f"Borrowed: ${borrow_assets_usd:,.2f}")
    message_parts.append(f"\nNeed to repay ~${repayment_needed_usd:,.2f} {loan_asset} to reach safe threshold")
    
    market_url = f"https://app.morpho.org/monad/market/{worst_market['id']}/{worst_market['name']}?subTab=yourPosition"
    message_parts.append(f"\n[View Position]({market_url})")
    
    return "\n".join(message_parts)

