"""
Strategy Pattern implementation for lending protocols.

This module provides a clean, scalable architecture for adding new protocols
without modifying existing code.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from web3 import Web3
import logging
import asyncio
from time import time

logger = logging.getLogger(__name__)


@dataclass
class Asset:
    """Standardized asset representation."""
    symbol: str
    amount: float
    usd_value: float
    decimals: int = 18


@dataclass
class PositionData:
    """Standardized position data structure."""
    protocol_name: str
    market_name: str
    market_id: str
    health_factor: float
    collateral: Asset
    debt: Asset
    liquidation_price: Optional[float] = None
    liquidation_drop_pct: Optional[float] = None
    app_url: Optional[str] = None
    
    def format_amount(self, val: float) -> str:
        """Format amount with K/M suffixes."""
        if val >= 1_000_000:
            return f"{val/1_000_000:.2f}M"
        if val >= 1_000:
            return f"{val/1_000:.1f}k"
        if val >= 1:
            return f"{val:.2f}"
        return f"{val:.4f}"
    
    def format_usd(self, val: float) -> str:
        """Format USD value with K/M suffixes."""
        if val >= 1_000_000:
            return f"${val/1_000_000:.2f}M"
        if val >= 1_000:
            return f"${val/1_000:.2f}K"
        return f"${val:.2f}"


class LendingProtocolStrategy(ABC):
    """Abstract base class defining the interface for all lending protocols."""
    
    @abstractmethod
    def get_positions(self, user_address: str) -> List[PositionData]:
        """
        Fetch all positions for a user and return standardized PositionData objects.
        
        Args:
            user_address: User's wallet address
            
        Returns:
            List of PositionData objects
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the protocol name."""
        pass
    
    @abstractmethod
    def get_protocol_id(self) -> str:
        """Return the protocol identifier (e.g., 'morpho', 'curvance')."""
        pass


class ProtocolManager:
    """Manages all protocol strategies and provides unified interface."""
    
    def __init__(self):
        self.strategies: dict[str, LendingProtocolStrategy] = {}
    
    def register_strategy(self, strategy: LendingProtocolStrategy):
        """Register a protocol strategy."""
        protocol_id = strategy.get_protocol_id()
        self.strategies[protocol_id] = strategy
        logger.info(f"Registered protocol strategy: {strategy.get_name()} ({protocol_id})")
    
    def get_all_positions(self, user_address: str, filter_protocol: Optional[str] = None) -> List[PositionData]:
        """
        Get all positions across all registered protocols (synchronous version).
        
        Args:
            user_address: User's wallet address
            filter_protocol: Optional protocol ID to filter results
            
        Returns:
            List of PositionData objects from all protocols
        """
        all_positions = []
        
        strategies_to_check = self.strategies.values()
        if filter_protocol:
            if filter_protocol not in self.strategies:
                logger.warning(f"Unknown protocol filter: {filter_protocol}")
                return []
            strategies_to_check = [self.strategies[filter_protocol]]
        
        for strategy in strategies_to_check:
            try:
                positions = strategy.get_positions(user_address)
                all_positions.extend(positions)
            except Exception as e:
                logger.error(f"Error fetching positions from {strategy.get_name()}: {e}", exc_info=True)
        
        return all_positions
    
    async def get_all_positions_async(self, user_address: str, filter_protocol: Optional[str] = None) -> List[PositionData]:
        """
        Get all positions across all registered protocols in parallel (async version).
        
        Args:
            user_address: User's wallet address
            filter_protocol: Optional protocol ID to filter results
            
        Returns:
            List of PositionData objects from all protocols
        """
        strategies_to_check = list(self.strategies.values())
        if filter_protocol:
            if filter_protocol not in self.strategies:
                logger.warning(f"Unknown protocol filter: {filter_protocol}")
                return []
            strategies_to_check = [self.strategies[filter_protocol]]
        
        if len(strategies_to_check) > 1:
            logger.debug(f"[PARALLEL] Checking {len(strategies_to_check)} protocols in parallel for {user_address[:8]}...")
        
        # Run all protocol checks in parallel
        async def fetch_positions(strategy):
            try:
                protocol_start = time()
                # Run synchronous get_positions in thread pool
                positions = await asyncio.to_thread(strategy.get_positions, user_address)
                elapsed = time() - protocol_start
                logger.debug(f"[PARALLEL] {strategy.get_name()} completed in {elapsed:.2f}s ({len(positions)} positions)")
                return positions
            except Exception as e:
                logger.error(f"Error fetching positions from {strategy.get_name()}: {e}", exc_info=True)
                return []
        
        # Execute all protocol checks concurrently
        results = await asyncio.gather(*[fetch_positions(strategy) for strategy in strategies_to_check], return_exceptions=True)
        
        # Flatten results and filter out exceptions
        all_positions = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Protocol check failed with exception: {result}")
                continue
            all_positions.extend(result)
        
        return all_positions
    
    def get_protocol_names(self) -> List[str]:
        """Get list of all registered protocol names."""
        return [strategy.get_name() for strategy in self.strategies.values()]


# Import protocol functions (will be done in implementations)
# This avoids circular imports

