"""
Concrete implementations of protocol strategies.

Each protocol has its own strategy class that wraps the existing protocol functions
and converts them to the standardized PositionData format.
"""
from typing import List, Optional
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
    
    # Known cToken addresses -> collateral symbols
    CTOKEN_TO_COLLATERAL_SYMBOL = {
        '0xf7a6ab4af86966c141d3c5633df658e5cdb0a735': 'loAZND',  # cloAZND
        '0x852ff1ec21d63b405ec431e04ae3ac760e29263d': 'earnAUSD',  # cearnAUSD
        '0xe01d426b589c7834a5f6b20d7e992a705d3c22ed': 'WMON',  # cWMON
        '0xdadbb2d8f9802dc458f5d7f133d053087ba8983d': 'AUSD',  # cAUSD (loAZND market)
        '0x2b4e0232f46e6db4af35474c140b968eefcb09ec': 'AUSD',  # cAUSD (muBOND market)
        '0x6e182eb501800c555bd5e662e6d350d627f504d8': 'AUSD',  # cAUSD (WMON/earnAUSD market)
    }
    
    # MarketManager -> collateral symbol mappings (fallback)
    MARKET_MANAGER_TO_COLLATERAL_SYMBOL = {
        '0x5ea0a1cf3501c954b64902c5e92100b8a2cab1ac': 'AprMON',
        '0xe1c24b2e93230fbe33d32ba38eca3218284143e2': 'shMON',
        '0xe5970cdb1916b2ccf6185c86c174eee2d330d05b': 'sMON',
        '0x830d40cdfdc494bc1a2729a7381bfce44326c944': 'muBOND',
        '0x7c822b093a116654f824ec2a35cd23a3749e4f90': 'loAZND',
        '0x83840d837e7a3e00bbb0b8501e60e989a8987c37': 'ezETH',
        '0xbbe7a3c45adbb16f6490767b663428c34aa341eb': 'sAUSD',
        '0xd6365555f6a697c7c295ba741100aa644ce28545': 'earnAUSD',  # Also WMON/AUSD market
        '0xa6a2a92f126b79ee0804845ee6b52899b4491093': 'WMON',
        '0x01c4a0d396efe982b1b103be9910321d34e1aea9': 'WBTC',
        '0xb3e9e0134354cc91b7fb9f9d6c3ab0de7854bb49': 'WETH',
    }
    
    # MarketManager -> borrowableCToken mappings
    MARKET_MANAGER_TO_BORROWABLE_CTOKEN = {
        '0x5ea0a1cf3501c954b64902c5e92100b8a2cab1ac': '0xf32b334042dc1eb9732454cc9bc1a06205d184f2',  # AprMON/WMON
        '0xe1c24b2e93230fbe33d32ba38eca3218284143e2': '0x0fced51b526bfa5619f83d97b54a57e3327eb183',  # shMON/wMON
        '0xe5970cdb1916b2ccf6185c86c174eee2d330d05b': '0xebe45a6cea7760a71d8e0fa5a0ae80a75320d708',  # sMON/wMON
        '0x830d40cdfdc494bc1a2729a7381bfce44326c944': '0x2b4e0232f46e6db4af35474c140b968eefcb09ec',  # muBOND/AUSD
        '0x7c822b093a116654f824ec2a35cd23a3749e4f90': '0xdadbb2d8f9802dc458f5d7f133d053087ba8983d',  # loAZND/AUSD
        '0x83840d837e7a3e00bbb0b8501e60e989a8987c37': '0xa206d51c02c0202a2eed8e6a757b49ab13930227',  # ezETH/WETH
        '0xbbe7a3c45adbb16f6490767b663428c34aa341eb': '0xfd493ce1a0ae986e09d17004b7e748817a47d73c',  # sAUSD/AUSD
        '0xd6365555f6a697c7c295ba741100aa644ce28545': '0x6e182eb501800c555bd5e662e6d350d627f504d8',  # WMON/AUSD, earnAUSD/AUSD
        '0xa6a2a92f126b79ee0804845ee6b52899b4491093': '0x8ee9fc28b8da872c38a496e9ddb9700bb7261774',  # WMON/USDC
        '0x01c4a0d396efe982b1b103be9910321d34e1aea9': '0x7c9d4f1695c6282da5e5509aa51fc9fb417c6f1d',  # WBTC/USDC
        '0xb3e9e0134354cc91b7fb9f9d6c3ab0de7854bb49': '0x21adbb60a5fb909e7f1fb48aacc4569615cd97b5',  # WETH/USDC
    }
    
    def __init__(self, contract, w3: Web3, app_url: str):
        self.contract = contract
        self.w3 = w3
        self.app_url = app_url
        # Caches for RPC calls
        self._ctoken_asset_cache = {}
        self._symbol_cache = {}
    
    def get_name(self) -> str:
        return "Curvance"
    
    def get_protocol_id(self) -> str:
        return "curvance"
    
    def _normalize_ctoken_symbol(self, symbol: str) -> str:
        """Strip 'c' prefix from cToken symbols if it's a valid cToken pattern."""
        if symbol == '?' or not symbol:
            return symbol
        if symbol.startswith('c') and len(symbol) > 1:
            test_without_c = symbol[1:]
            if test_without_c[0].isupper() or test_without_c.lower() in ['ausd', 'wmon', 'weth', 'usdc', 'wbtc', 'earnausd', 'loaznd']:
                return test_without_c
        return symbol
    
    def _get_ctoken_asset(self, ctoken_address: str) -> Optional[str]:
        """Get underlying asset address from cToken by calling asset()."""
        ctoken_lower = ctoken_address.lower()
        
        if ctoken_lower in self._ctoken_asset_cache:
            return self._ctoken_asset_cache[ctoken_lower]
        
        try:
            ctoken_abi = [{
                'inputs': [],
                'name': 'asset',
                'outputs': [{'internalType': 'address', 'name': '', 'type': 'address'}],
                'stateMutability': 'view',
                'type': 'function'
            }]
            
            ctoken_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(ctoken_address),
                abi=ctoken_abi
            )
            
            asset_address = ctoken_contract.functions.asset().call()
            if asset_address and asset_address != '0x0000000000000000000000000000000000000000':
                asset_lower = asset_address.lower()
                self._ctoken_asset_cache[ctoken_lower] = asset_lower
                return asset_lower
        except Exception:
            pass
        
        self._ctoken_asset_cache[ctoken_lower] = None
        return None
    
    def _get_token_symbol(self, token_address: str) -> str:
        """Get token symbol with caching."""
        token_lower = token_address.lower()
        
        if token_lower in self._symbol_cache:
            return self._symbol_cache[token_lower]
        
        try:
            erc20_abi = [{
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            }]
            token_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token_address),
                abi=erc20_abi
            )
            symbol = token_contract.functions.symbol().call()
            self._symbol_cache[token_lower] = symbol
            return symbol
        except Exception:
            self._symbol_cache[token_lower] = '?'
            return '?'
    
    def _get_collateral_symbol(self, cToken: str, market_manager: Optional[str] = None) -> str:
        """Get collateral symbol from cToken, with fallbacks."""
        if not cToken or cToken == '0x0000000000000000000000000000000000000000':
            if market_manager:
                return self.MARKET_MANAGER_TO_COLLATERAL_SYMBOL.get(market_manager.lower(), '?')
            return '?'
        
        ctoken_lower = cToken.lower()
        
        # Check known cToken mapping first
        if ctoken_lower in self.CTOKEN_TO_COLLATERAL_SYMBOL:
            return self.CTOKEN_TO_COLLATERAL_SYMBOL[ctoken_lower]
        
        # Try getting symbol from cToken contract
        symbol = self._normalize_ctoken_symbol(self._get_token_symbol(cToken))
        if symbol != '?':
            return symbol
        
        # Try underlying asset
        asset = self._get_ctoken_asset(cToken)
        if asset:
            symbol = self._normalize_ctoken_symbol(self._get_token_symbol(asset))
            if symbol != '?':
                return symbol
        
        # Fallback to MarketManager mapping
        if market_manager:
            return self.MARKET_MANAGER_TO_COLLATERAL_SYMBOL.get(market_manager.lower(), '?')
        
        return '?'
    
    def _get_debt_symbol(self, market_manager: str) -> str:
        """Get debt symbol from borrowableCToken for a MarketManager."""
        borrowable_ctoken = self.MARKET_MANAGER_TO_BORROWABLE_CTOKEN.get(market_manager.lower())
        if borrowable_ctoken:
            asset = self._get_ctoken_asset(borrowable_ctoken)
            if asset:
                return self._get_token_symbol(asset)
        return '?'
    
    def get_positions(self, user_address: str) -> List[PositionData]:
        """
        Get Curvance positions using getAllDynamicState + getPositionHealth.
        
        IMPORTANT: getPositionHealth() returns AGGREGATE health for the account within a MarketManager,
        not per-position health. If you have multiple positions (e.g., WMON collateral + earnAUSD collateral)
        in the same MarketManager, they will all show the same aggregate health factor.
        
        The aggregate combines ALL collateral and ALL debt across ALL positions in that MarketManager
        to calculate one overall health factor for your entire account in that market.
        """
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
            
            # Group positions by MarketManager (since aggregate health is per MarketManager)
            # Key: market_manager -> {health_factor, collateral_tokens: [], total_collateral, total_debt}
            mm_positions = {}  # market_manager -> position data
            
            # Cache health factors per MarketManager (since getPositionHealth returns aggregate health)
            # Key: market_manager -> health_factor
            mm_health_cache = {}  # market_manager -> health_factor
            
            # Step 3: For each position, find its MarketManager and get health factor
            for position in raw_positions:
                # position structure: (cToken, collateral, debt, health, tokenBalance)
                cToken = position[0]
                collateral_raw = position[1]
                debt_raw = position[2]
                health_raw_from_state = position[3] if len(position) > 3 else 0  # Health from getAllDynamicState
                
                logger.debug(f"Curvance: Processing position - cToken: {cToken}, collateral: {collateral_raw}, debt: {debt_raw}, health_from_state: {health_raw_from_state}")
                
                # Skip if no debt
                if debt_raw == 0:
                    logger.debug(f"Curvance: Skipping position with no debt (cToken: {cToken})")
                    continue
                
                # Try each MarketManager to find the one that works
                market_manager_found = None
                health_factor = None
                
                # Find MarketManager by calling getPositionHealth with each one
                for mm_address in market_managers:
                    try:
                        # Call getPositionHealth to get aggregate health for this MarketManager
                        # Note: This returns aggregate health combining ALL positions in this MarketManager
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
                            
                            # Found valid MarketManager for this position
                            health_factor = health_factor_candidate
                            market_manager_found = mm_address
                            
                            # Check cache - if we've already processed this MarketManager, use cached health
                            # (all positions in same MarketManager share the same aggregate health)
                            mm_lower = mm_address.lower()
                            if mm_lower in mm_health_cache:
                                health_factor = mm_health_cache[mm_lower]
                                logger.debug(f"Curvance: Using cached aggregate health {health_factor:.3f} for MM {mm_address}, cToken {cToken}")
                            else:
                                # Cache the aggregate health for this MarketManager
                                mm_health_cache[mm_lower] = health_factor
                                logger.info(f"Curvance: Found working MarketManager {mm_address} for cToken {cToken}, aggregate health: {health_factor:.3f}")
                            
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
                
                # Extract cToken address (may be packed)
                cToken_clean = cToken
                if isinstance(cToken, int):
                    hex_str = hex(cToken)[2:].zfill(64)
                    address_hex = hex_str[-40:]
                    cToken_clean = '0x' + address_hex
                elif not isinstance(cToken, str):
                    cToken_clean = str(cToken)
                
                # Get collateral symbol using improved extraction logic
                collateral_symbol = self._get_collateral_symbol(cToken_clean, market_manager_found)
                
                # Get debt symbol
                debt_symbol = self._get_debt_symbol(market_manager_found) if market_manager_found else "?"
                
                # Get token decimals for amount calculation
                try:
                    token_contract = self.w3.eth.contract(address=cToken_clean, abi=erc20_abi)
                    collateral_decimals = token_contract.functions.decimals().call()
                    collateral_amount = collateral_raw / (10 ** collateral_decimals)
                except Exception:
                    # Fallback to 18 decimals
                    collateral_decimals = 18
                    collateral_amount = collateral_raw / (10 ** collateral_decimals)
                
                debt_decimals = 18
                debt_amount = debt_raw / (10 ** debt_decimals)
                
                logger.debug(f"Curvance: Position found - MM: {market_manager_found}, cToken: {cToken}, symbol: {collateral_symbol}, health: {health_factor:.3f}")
                
                # Group by MarketManager (aggregate health is per MarketManager)
                mm_lower = market_manager_found.lower()
                if mm_lower not in mm_positions:
                    mm_positions[mm_lower] = {
                        'market_manager': market_manager_found,
                        'health_factor': health_factor,
                        'collateral_tokens': [],
                        'total_collateral': 0,
                        'total_debt': 0,
                        'debt_symbol': debt_symbol
                    }
                
                # Add this position's data to the MarketManager group
                mm_positions[mm_lower]['collateral_tokens'].append({
                    'symbol': collateral_symbol,
                    'amount': collateral_amount,
                    'cToken': cToken
                })
                mm_positions[mm_lower]['total_collateral'] += collateral_amount
                mm_positions[mm_lower]['total_debt'] += debt_amount
            
            # Convert grouped positions to PositionData list (one per MarketManager)
            for mm_lower, mm_data in mm_positions.items():
                # Create market name from collateral tokens and debt symbol
                collateral_symbols = [ct['symbol'] for ct in mm_data['collateral_tokens'] if ct['symbol'] != '?']
                unique_symbols = list(dict.fromkeys(collateral_symbols))  # Preserve order, remove duplicates
                debt_symbol = mm_data['debt_symbol']
                
                # Format: "debt | collateral1, collateral2" or just "collateral" if no debt symbol
                if debt_symbol and debt_symbol != '?':
                    if len(unique_symbols) == 1:
                        market_name = f"{debt_symbol} | {unique_symbols[0]}"
                    elif len(unique_symbols) <= 3:
                        market_name = f"{debt_symbol} | {', '.join(unique_symbols)}"
                    else:
                        market_name = f"{debt_symbol} | {', '.join(unique_symbols[:3])}..."
                else:
                    if len(unique_symbols) == 1:
                        market_name = unique_symbols[0]
                    elif len(unique_symbols) <= 3:
                        market_name = ', '.join(unique_symbols)
                    else:
                        market_name = ', '.join(unique_symbols[:3]) + '...'
                
                # Use MarketManager address as market_id (since aggregate health is per MarketManager)
                market_id = mm_data['market_manager']
                
                # Use first collateral symbol for display (or "?" if none)
                display_collateral_symbol = unique_symbols[0] if unique_symbols else "?"
                
                positions.append(PositionData(
                    protocol_name="Curvance",
                    market_name=market_name,
                    market_id=market_id,
                    health_factor=mm_data['health_factor'],
                    collateral=Asset(
                        symbol=display_collateral_symbol,
                        amount=mm_data['total_collateral'],
                        usd_value=mm_data['total_collateral'],  # Rough estimate
                        decimals=18
                    ),
                    debt=Asset(
                        symbol=mm_data['debt_symbol'],
                        amount=mm_data['total_debt'],
                        usd_value=mm_data['total_debt'],  # Rough estimate
                        decimals=18
                    ),
                    app_url=self.app_url
                ))
            
            logger.info(f"Curvance: Found {len(positions)} MarketManagers with positions from {len(raw_positions)} raw positions")
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

