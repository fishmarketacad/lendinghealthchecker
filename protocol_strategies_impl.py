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
                # Convert to float, handling None and 0 values
                liquidation_price = float(liquidation_price) if liquidation_price is not None and float(liquidation_price) > 0 else None
                liquidation_drop_pct = float(liquidation_drop_pct) if liquidation_drop_pct is not None and float(liquidation_drop_pct) > 0 else None
                
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
                    liquidation_price=liquidation_price,  # Already None if invalid
                    liquidation_drop_pct=liquidation_drop_pct,  # Already None if invalid
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
        """Get Curvance positions using getAllDynamicState + getPositionHealth directly."""
        positions = []
        
        try:
            address_checksum = self.w3.to_checksum_address(user_address)
            logger.info(f"Curvance: Checking positions for {user_address} using ProtocolReader {self.contract.address}")
            
            # Step 1: Get all positions from getAllDynamicState
            try:
                result = self.contract.functions.getAllDynamicState(address_checksum).call()
                logger.debug(f"Curvance: getAllDynamicState returned result: {type(result)}")
                
                if not result or len(result) < 2:
                    logger.warning(f"Curvance: Invalid result from getAllDynamicState: {result}")
                    return positions
                
                market_data, user_data = result
                logger.debug(f"Curvance: market_data type: {type(market_data)}, user_data type: {type(user_data)}")
                
                if not user_data or len(user_data) < 2:
                    logger.warning(f"Curvance: Invalid user_data structure: {user_data}")
                    return positions
                
                raw_positions = user_data[1]  # positions array
                logger.info(f"Curvance: Found {len(raw_positions) if raw_positions else 0} raw positions for {user_address}")
                
                if not raw_positions:
                    logger.info(f"Curvance: No positions found for {user_address} (empty positions array)")
                    return positions
            except Exception as e:
                logger.error(f"Curvance: Error calling getAllDynamicState for {user_address}: {e}", exc_info=True)
                return positions
            
            # Step 2: Get all MarketManagers
            market_managers = protocols.get_curvance_market_managers(self.w3)
            logger.info(f"Curvance: Found {len(market_managers)} MarketManagers, {len(raw_positions)} positions")
            
            # ERC20 ABI for token info
            erc20_abi = [
                {"inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
                {"inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"}
            ]
            
            zero_address = '0x0000000000000000000000000000000000000000'
            
            # Track positions we've already seen to avoid duplicates
            # Key: (market_manager, cToken) to handle multiple positions in same MarketManager
            seen_positions = {}  # (market_manager, cToken) -> PositionData
            
            # Step 3: For each position, find its MarketManager and get health factor
            logger.info(f"Curvance: Processing {len(raw_positions)} raw positions from getAllDynamicState")
            for idx, position in enumerate(raw_positions):
                # position structure: (cToken, collateral, debt, health, tokenBalance)
                cToken = position[0]
                collateral_raw = position[1]
                debt_raw = position[2]
                health_raw_from_state = position[3] if len(position) > 3 else 0  # Health from getAllDynamicState
                
                logger.info(f"Curvance: Position {idx+1}/{len(raw_positions)} - cToken: {cToken}, collateral: {collateral_raw}, debt: {debt_raw}, health_from_state: {health_raw_from_state}")
                
                # Skip if no debt
                if debt_raw == 0:
                    logger.debug(f"Curvance: Skipping position with no debt (cToken: {cToken})")
                    continue
                
                # Try each MarketManager to find the one that works
                market_manager_found = None
                health_factor = None
                
                for mm_address in market_managers:
                    try:
                        # Call getPositionHealth to check existing position
                        health_result = self.contract.functions.getPositionHealth(
                            self.w3.to_checksum_address(mm_address),  # mm
                            address_checksum,  # account
                            cToken,  # cToken
                            zero_address,  # borrowableCToken (0 for checking existing)
                            False,  # isDeposit
                            0,  # collateralAssets (0 = check existing)
                            False,  # isRepayment
                            0,  # debtAssets (0 = check existing)
                            0  # bufferTime
                        ).call()
                        
                        position_health_raw, error_code_hit = health_result
                        
                        if error_code_hit:
                            logger.debug(f"Curvance: getPositionHealth returned error_code_hit=True for MM {mm_address}, cToken {cToken}")
                            continue  # Try next MarketManager
                        
                        if position_health_raw > 0:
                            health_factor_candidate = position_health_raw / 1e18
                            
                            # Skip if getPositionHealth returned max uint256 (invalid)
                            if health_factor_candidate > 1e10:
                                logger.debug(f"Curvance: getPositionHealth returned max uint256 for MM {mm_address}, cToken {cToken}, using fallback")
                                continue  # Try next MarketManager or use fallback
                            
                            health_factor = health_factor_candidate
                            market_manager_found = mm_address
                            logger.info(f"Curvance: Found working MarketManager {mm_address} for cToken {cToken}, health: {health_factor:.3f}")
                            break  # Found working MarketManager
                        else:
                            logger.debug(f"Curvance: getPositionHealth returned 0 health for MM {mm_address}, cToken {cToken}")
                    except Exception as e:
                        logger.debug(f"Curvance: Exception calling getPositionHealth with MM {mm_address}, cToken {cToken}: {e}")
                        continue
                
                # Fallback to health from getAllDynamicState if getPositionHealth failed or returned max uint256
                if not health_factor and health_raw_from_state > 0:
                    health_factor_candidate = health_raw_from_state / 1e18
                    # Only use fallback if it's a valid health factor (not max uint256)
                    if health_factor_candidate <= 1e10:
                        health_factor = health_factor_candidate
                        # Try to find MarketManager by matching cToken to MarketManager's supported tokens
                        # For now, use first MarketManager as fallback
                        market_manager_found = market_managers[0] if market_managers else None
                        logger.info(f"Curvance: Using fallback health from getAllDynamicState for cToken {cToken}, health: {health_factor:.3f}")
                    else:
                        logger.debug(f"Curvance: Fallback health also invalid (max uint256) for cToken {cToken}")
                
                # Skip if no valid health factor found
                if not health_factor or health_factor > 1e10:
                    logger.warning(f"Curvance: No valid health factor found for cToken {cToken} (tried {len(market_managers)} MarketManagers)")
                    continue
                
                # Skip if no MarketManager found (shouldn't happen if health_factor is set)
                if not market_manager_found:
                    logger.warning(f"Curvance: No MarketManager found for cToken {cToken} despite having health factor")
                    continue
                
                # Get token symbol and decimals
                try:
                    token_contract = self.w3.eth.contract(address=cToken, abi=erc20_abi)
                    collateral_symbol = token_contract.functions.symbol().call()
                    collateral_decimals = token_contract.functions.decimals().call()
                    collateral_amount = collateral_raw / (10 ** collateral_decimals)
                except Exception as e:
                    logger.debug(f"Error getting token info for {cToken}: {e}")
                    collateral_symbol = "?"
                    collateral_amount = collateral_raw
                
                # Debt token info (simplified - would need MarketManager to get actual borrowable token)
                debt_symbol = "?"
                debt_decimals = 18
                debt_amount = debt_raw / (10 ** debt_decimals)
                
                logger.debug(f"Curvance: Position found - MM: {market_manager_found}, cToken: {cToken}, health: {health_factor:.3f}")
                
                # Create unique key: (market_manager, cToken) to handle multiple positions in same MarketManager
                # Each position with a different collateral token is a separate position
                position_key = (market_manager_found.lower() if market_manager_found else None, cToken.lower() if cToken else None)
                
                logger.info(f"Curvance: Position key: MM={position_key[0]}, cToken={position_key[1]}, health={health_factor:.3f}")
                
                if position_key[0] and position_key[1]:
                    # Use market_id as combination of MarketManager and cToken for unique identification
                    unique_market_id = f"{market_manager_found}_{cToken}"
                    
                    if position_key not in seen_positions:
                        # First time seeing this (MarketManager, cToken) combination
                        logger.info(f"Curvance: Adding new position - MM: {market_manager_found}, cToken: {cToken}, symbol: {collateral_symbol}")
                        seen_positions[position_key] = PositionData(
                            protocol_name="Curvance",
                            market_name=f"Curvance Market ({collateral_symbol})",
                            market_id=unique_market_id,
                            health_factor=health_factor,
                            collateral=Asset(
                                symbol=collateral_symbol,
                                amount=collateral_amount,
                                usd_value=collateral_amount,  # Rough estimate
                                decimals=18
                            ),
                            debt=Asset(
                                symbol=debt_symbol,
                                amount=debt_amount,
                                usd_value=debt_amount,  # Rough estimate
                                decimals=18
                            ),
                            app_url=self.app_url
                        )
                    else:
                        # Already seen this (MarketManager, cToken) - this shouldn't happen, but log it
                        existing = seen_positions[position_key]
                        logger.warning(f"Curvance: Duplicate position detected for MM {market_manager_found}, cToken {cToken}. Existing: symbol={existing.collateral.symbol}, health={existing.health_factor:.3f}, New: symbol={collateral_symbol}, health={health_factor:.3f}")
                        # Skip duplicate - keep the first one
            
            # Convert deduplicated positions to list
            positions = list(seen_positions.values())
            logger.info(f"Curvance: Found {len(positions)} unique positions from {len(raw_positions)} raw positions")
        except Exception as e:
            logger.error(f"Error fetching Curvance positions: {e}", exc_info=True)
        
        return positions


class EulerStrategy(LendingProtocolStrategy):
    """Strategy for Euler V2 protocol."""
    
    def __init__(self, w3: Web3, account_lens_address: str, evc_address: str, app_url: str):
        self.w3 = w3
        self.account_lens_address = account_lens_address
        self.evc_address = evc_address
        self.app_url = app_url
    
    def get_name(self) -> str:
        return "Euler"
    
    def get_protocol_id(self) -> str:
        return "euler"
    
    def get_positions(self, user_address: str) -> List[PositionData]:
        """Get Euler positions for a user."""
        positions = []
        
        try:
            # Get all vaults where user has positions
            vaults_data = protocols.get_euler_user_vaults(
                user_address,
                self.w3,
                self.account_lens_address,
                self.evc_address
            )
            
            for vault in vaults_data:
                vault_address = vault.get('vault_address', '')
                hf = vault.get('health_factor')
                collateral_usd = vault.get('collateral_usd', 0)
                debt_usd = vault.get('debt_usd', 0)
                
                # Skip invalid positions
                if not hf or float(hf) > 1e10 or debt_usd == 0:
                    continue
                
                # Euler vaults don't have token symbols easily accessible
                # Use vault address short form as identifier
                vault_short = vault_address[:6] + '...' + vault_address[-4:] if len(vault_address) > 10 else vault_address
                
                positions.append(PositionData(
                    protocol_name="Euler",
                    market_name=f"Euler Vault ({vault_short})",
                    market_id=vault_address.lower(),
                    health_factor=float(hf),
                    collateral=Asset(
                        symbol="?",  # Token symbol not easily available from vault
                        amount=0,  # Amount not easily available without token decimals
                        usd_value=collateral_usd,
                        decimals=18
                    ),
                    debt=Asset(
                        symbol="?",  # Token symbol not easily available from vault
                        amount=0,  # Amount not easily available without token decimals
                        usd_value=debt_usd,
                        decimals=18
                    ),
                    app_url=self.app_url
                ))
        except Exception as e:
            logger.error(f"Error fetching Euler positions: {e}", exc_info=True)
        
        return positions

