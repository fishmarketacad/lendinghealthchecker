# Architecture Overview

## Protocol File Structure

The bot uses three protocol-related files with distinct responsibilities:

### 1. `protocol_strategy.py` - Strategy Pattern Abstraction

**Purpose**: Defines the abstract interface and manager for all protocols.

**Contents**:
- `LendingProtocolStrategy` (ABC): Abstract base class that all protocol strategies must implement
- `ProtocolManager`: Manages all registered strategies and provides unified interface
- `PositionData`: Standardized data structure for positions
- `Asset`: Standardized asset representation

**Why it exists**: Provides clean abstraction layer using Strategy Pattern. New protocols can be added without modifying existing code.

### 2. `protocol_strategies_impl.py` - Concrete Protocol Implementations

**Purpose**: Implements the `LendingProtocolStrategy` interface for each protocol.

**Contents**:
- `NeverlandStrategy`: Fetches Neverland positions
- `MorphoStrategy`: Fetches Morpho Blue positions
- `CurvanceStrategy`: Fetches Curvance positions (handles aggregate health)
- `EulerStrategy`: Fetches Euler V2 positions

**Responsibilities**:
- Convert protocol-specific data to standardized `PositionData` format
- Handle protocol-specific quirks (e.g., Curvance aggregate health)
- Call functions from `protocols.py` for blockchain interactions

**Why it exists**: Separates protocol-specific logic from low-level blockchain calls. Makes it easy to add new protocols.

### 3. `protocols.py` - Low-Level Blockchain Functions

**Purpose**: Contains protocol-specific blockchain interaction functions.

**Contents**:
- `load_abi()`: Load contract ABIs from JSON files
- `get_curvance_market_managers()`: Query Curvance Central Registry
- `get_morpho_user_markets()`: Query Morpho GraphQL API + contract calls
- `get_euler_user_vaults()`: Query Euler AccountLens contract
- `check_neverland_health_factor()`: Call Neverland contract
- Helper functions for token decimals, LLTV, etc.

**Responsibilities**:
- Direct blockchain/API interactions
- Contract ABI loading
- GraphQL queries (Morpho)
- Data parsing and validation

**Why it exists**: 
- Reusable low-level functions shared across strategies
- Keeps blockchain interaction logic separate from business logic
- Can be used by both Strategy Pattern code and legacy code

## Data Flow

```
User Command (/check)
    ↓
lendinghealthchecker.py
    ↓
ProtocolManager.get_all_positions()
    ↓
protocol_strategies_impl.py
    ├─ NeverlandStrategy.get_positions()
    │   └─ protocols.check_neverland_health_factor()
    ├─ MorphoStrategy.get_positions()
    │   └─ protocols.get_morpho_user_markets()
    ├─ CurvanceStrategy.get_positions()
    │   └─ protocols.get_curvance_market_managers()
    │   └─ protocols.get_curvance_position_details()
    └─ EulerStrategy.get_positions()
        └─ protocols.get_euler_user_vaults()
    ↓
PositionData (standardized format)
    ↓
lendinghealthchecker.py (format message)
    ↓
Telegram Bot Response
```

## Why Not Merge Files?

**Could we merge `protocols.py` into `protocol_strategies_impl.py`?**

Yes, but keeping them separate provides:
- **Separation of concerns**: Low-level blockchain calls vs. business logic
- **Reusability**: Functions in `protocols.py` can be used by legacy code
- **Testability**: Easier to test blockchain functions independently
- **Maintainability**: Clear boundaries between abstraction layers

**Could we merge `protocol_strategy.py` into `protocol_strategies_impl.py`?**

No - `protocol_strategy.py` defines the interface that `protocol_strategies_impl.py` implements. This is the core of the Strategy Pattern.

## Adding a New Protocol

To add a new protocol (e.g., "Aave"):

1. **Add low-level functions to `protocols.py`**:
   ```python
   def get_aave_user_positions(address: str, w3) -> List[Dict]:
       # Query Aave contracts/APIs
       pass
   ```

2. **Implement strategy in `protocol_strategies_impl.py`**:
   ```python
   class AaveStrategy(LendingProtocolStrategy):
       def get_positions(self, user_address: str) -> List[PositionData]:
           positions_data = protocols.get_aave_user_positions(user_address, self.w3)
           # Convert to PositionData format
           return [PositionData(...) for pos in positions_data]
   ```

3. **Register strategy in `lendinghealthchecker.py`**:
   ```python
   protocol_manager.register_strategy(AaveStrategy(...))
   ```

4. **Add protocol config to `PROTOCOL_CONFIG`**:
   ```python
   'aave': {
       'name': 'Aave',
       'rpc_url': '...',
       'pool_address': '...',
       ...
   }
   ```

That's it! No need to modify existing protocol code.

