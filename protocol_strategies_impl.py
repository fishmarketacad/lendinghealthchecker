"""
Concrete implementations of protocol strategies.

Each protocol has its own strategy class that wraps the existing protocol functions
and converts them to the standardized PositionData format.
"""
from typing import List
from web3 import Web3
import protocols
import protocol_strategy
from protocol_strategy import LendingProtocolStrategy, PositionData, Asset

logger = protocol_strategy.logger


class NeverlandStrategy(LendingProtocolStrategy):
    """Strategy for Neverland protocol."""
    
    def __init__(self, contract, w3: Web3, app_url: str):
        self.contract = contract
        self.w3 = w3
        self.app_url = app_url
    
    def get_name(self) -> str:
        return "Neverland"
    
    def get_protocol_id(self) -> str:
        return "neverland"
    
    def get_positions(self, user_address: str) -> List[PositionData]:
        """Get Neverland positions for a user."""
        positions = []
        
        try:
            # Get health factor
            health_factor = protocols.check_neverland_health_factor(
                user_address, self.contract, self.w3
            )
            
            if not health_factor or health_factor > 1e10:  # Invalid position
                return positions
            
            # Get account data for collateral/debt
            account_data = protocols.get_neverland_account_data(
                user_address, self.contract, self.w3
            )
            
            collateral_usd = account_data.get('collateral_usd', 0) if account_data else 0
            debt_usd = account_data.get('debt_usd', 0) if account_data else 0
            
            # Neverland doesn't provide token symbols/amounts, use USD only
            positions.append(PositionData(
                protocol_name="Neverland",
                market_name="Neverland",
                market_id="neverland",
                health_factor=float(health_factor),
                collateral=Asset("USD", 0, collateral_usd, 18),
                debt=Asset("USD", 0, debt_usd, 18),
                app_url=self.app_url
            ))
        except Exception as e:
            logger.error(f"Error fetching Neverland positions: {e}", exc_info=True)
        
        return positions


class MorphoStrategy(LendingProtocolStrategy):
    """Strategy for Morpho Blue protocol."""
    
    def __init__(self, w3: Web3, chain_id: int, app_url: str):
        self.w3 = w3
        self.chain_id = chain_id
        self.app_url = app_url
    
    def get_name(self) -> str:
        return "Morpho"
    
    def get_protocol_id(self) -> str:
        return "morpho"
    
    def get_positions(self, user_address: str) -> List[PositionData]:
        """Get Morpho positions for a user."""
        positions = []
        
        try:
            # Get all markets where user has positions
            markets_data = protocols.get_morpho_user_markets(user_address, self.chain_id)
            
            for market in markets_data:
                hf = market.get('healthFactor')
                borrow_usd = market.get('borrowAssetsUsd', 0)
                
                # Skip invalid positions
                if not hf or float(hf) > 1e10 or borrow_usd == 0:
                    continue
                
                # Extract market info
                market_id = market.get('id', '')
                market_name = market.get('name', '?')
                loan_symbol = market.get('loanAsset', '?')
                collateral_symbol = market.get('collateralAsset', '?')
                
                # Get amounts (prioritize human-readable amounts from contract)
                # Handle None values and ensure they're floats
                collateral_human = float(market.get('supplyAmountHuman', 0) or 0)
                borrow_human = float(market.get('borrowAmountHuman', 0) or 0)
                collateral_usd = float(market.get('supplyAssetsUsd', 0) or 0)
                
                # Get decimals
                loan_decimals = 18  # Default
                coll_decimals = 18  # Default
                
                # Get liquidation info
                liquidation_price = market.get('liquidationPrice')
                liquidation_drop_pct = market.get('liquidationDropPct')
                liquidation_price = float(liquidation_price) if liquidation_price is not None and liquidation_price > 0 else None
                liquidation_drop_pct = float(liquidation_drop_pct) if liquidation_drop_pct is not None and liquidation_drop_pct > 0 else None
                
                positions.append(PositionData(
                    protocol_name="Morpho",
                    market_name=market_name,
                    market_id=market_id,
                    health_factor=float(hf),
                    collateral=Asset(
                        symbol=collateral_symbol,
                        amount=collateral_human,
                        usd_value=collateral_usd,
                        decimals=coll_decimals
                    ),
                    debt=Asset(
                        symbol=loan_symbol,
                        amount=borrow_human,
                        usd_value=borrow_usd,
                        decimals=loan_decimals
                    ),
                    liquidation_price=liquidation_price if liquidation_price > 0 else None,
                    liquidation_drop_pct=liquidation_drop_pct if liquidation_drop_pct > 0 else None,
                    app_url=self.app_url
                ))
        except Exception as e:
            logger.error(f"Error fetching Morpho positions: {e}", exc_info=True)
        
        return positions


class CurvanceStrategy(LendingProtocolStrategy):
    """Strategy for Curvance protocol."""
    
    def __init__(self, contract, w3: Web3, app_url: str):
        self.contract = contract
        self.w3 = w3
        self.app_url = app_url
    
    def get_name(self) -> str:
        return "Curvance"
    
    def get_protocol_id(self) -> str:
        return "curvance"
    
    def get_positions(self, user_address: str) -> List[PositionData]:
        """Get Curvance positions for a user."""
        positions = []
        
        try:
            # Get all MarketManagers
            market_managers = protocols.get_curvance_market_managers(self.w3)
            
            # Get health factor (checks all MarketManagers)
            health_factor = protocols.check_curvance_health_factor(
                user_address, self.contract, self.w3, None, market_managers
            )
            
            if not health_factor or health_factor > 1e10:  # Invalid position
                return positions
            
            # Get position details
            position_details = protocols.get_curvance_position_details(
                user_address, self.contract, self.w3, None, market_managers
            )
            
            for detail in position_details:
                collateral_symbol = detail.get('collateral_token', '?')
                collateral_amount = detail.get('collateral_amount', 0)
                debt_amount = detail.get('debt_amount', 0)
                
                # Curvance doesn't provide USD values, estimate from amounts
                # (In production, would use price oracle)
                collateral_usd = collateral_amount  # Rough estimate
                debt_usd = debt_amount  # Rough estimate
                
                positions.append(PositionData(
                    protocol_name="Curvance",
                    market_name=f"Curvance Market",
                    market_id=detail.get('cToken', 'curvance'),
                    health_factor=float(health_factor),
                    collateral=Asset(
                        symbol=collateral_symbol,
                        amount=collateral_amount,
                        usd_value=collateral_usd,
                        decimals=18
                    ),
                    debt=Asset(
                        symbol=detail.get('debt_token', '?'),
                        amount=debt_amount,
                        usd_value=debt_usd,
                        decimals=18
                    ),
                    app_url=self.app_url
                ))
        except Exception as e:
            logger.error(f"Error fetching Curvance positions: {e}", exc_info=True)
        
        return positions

