# Multi-Protocol Lending Health Factor Monitor Bot

A Telegram bot that monitors health factors for lending positions across multiple protocols on Monad blockchain. The bot automatically discovers all your positions and sends alerts when health factors drop below your configured thresholds.

## Supported Protocols

- **Neverland** - Unified lending protocol ✅
- **Morpho Blue** - Peer-to-peer lending protocol ✅
- **Curvance** - Unified lending protocol with aggregate health factors ✅
- **Euler V2** - Isolated vault lending protocol ✅ (Full support with sub-account detection)

## Features

- 🔍 **Auto-discovery**: Automatically finds all your positions across all protocols
- ⚠️ **Smart alerts**: Configurable thresholds per protocol, per market, or globally
- 📊 **Multi-protocol support**: Monitor positions from multiple protocols in one bot
- 🔄 **Periodic monitoring**: Automatic health checks at configurable intervals
- 💬 **Telegram integration**: Easy-to-use commands via Telegram

## Architecture

The bot uses a **Strategy Pattern** architecture for clean, scalable protocol support:

- **`protocol_strategy.py`**: Abstract base classes defining the protocol interface
- **`protocol_strategies_impl.py`**: Concrete implementations for each protocol (NeverlandStrategy, MorphoStrategy, CurvanceStrategy, EulerStrategy)
- **`protocols.py`**: Low-level blockchain interaction functions (ABI loading, contract calls, GraphQL queries)
- **`lendinghealthchecker.py`**: Main bot logic, Telegram handlers, and position discovery

### Why Three Protocol Files?

1. **`protocol_strategy.py`**: Defines the Strategy Pattern abstraction (`LendingProtocolStrategy` interface and `ProtocolManager`)
2. **`protocol_strategies_impl.py`**: Implements protocol-specific strategies that convert protocol data to standardized `PositionData` format
3. **`protocols.py`**: Contains low-level blockchain functions (contract calls, GraphQL queries) used by the strategies

This separation provides:
- **Clean abstraction**: New protocols can be added by implementing `LendingProtocolStrategy`
- **Reusable functions**: Low-level functions in `protocols.py` can be shared across strategies
- **Maintainability**: Protocol-specific logic is isolated and easy to modify

## Curvance Protocol - Special Considerations

Curvance uses an **aggregate health factor** model that differs from other protocols:

### What is Aggregate Health?

Unlike other protocols where each position has its own health factor, Curvance calculates **one aggregate health factor per MarketManager** that combines ALL your positions in that market.

**Example:**
- Position 1: WMON collateral (1.73), AUSD debt (11.26) → Health: 1.396
- Position 2: earnAUSD collateral (1.00), AUSD debt (1.73) → Health: 1.396 (same!)

Both positions show the same health (1.396) because `getPositionHealth()` calculates:
- **Total Collateral**: 1.73 + 1.00 = 2.73
- **Total Debt**: 11.26 + 1.73 = 12.99
- **Aggregate Health**: Calculated from combined values = 1.396

### Why Aggregate Health?

Curvance's liquidation system cares about your **overall account health** in a MarketManager, not individual position health. If your combined health drops below 1.0, you can be liquidated regardless of individual position health.

### How the Bot Handles This

1. **Groups positions by MarketManager**: All positions in the same MarketManager are grouped together
2. **Shows aggregate health**: One entry per MarketManager with the aggregate health factor
3. **Lists all collateral tokens**: Market name shows all collateral tokens (e.g., "AUSD | WMON, earnAUSD")
4. **Caches health factors**: Since all positions in a MarketManager share the same health, we cache it to avoid redundant calls

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or using a virtual environment (recommended):

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the project root:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
MONAD_NODE_URL=https://rpc.monad.xyz
CHECK_INTERVAL=3600
USER_DATA_FILE=lendinghealthchatids.json
```

**Optional environment variables:**
- `MORPHO_BLUE_ADDRESS`: Morpho Blue contract address (default: `0xD5D960E8C380B724a48AC59E2DfF1b2CB4a1eAee`)
- `CURVANCE_PROTOCOL_READER_ADDRESS`: Curvance ProtocolReader address (default: `0xBF67b967eCcf21f2C196f947b703e874D5dB649d`)
- `CURVANCE_APP_URL`: Curvance app URL (default: `https://app.curvance.com`)

**Important:** 
- **NO QUOTES** needed around values in `.env` files
- Just the value directly: `TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
- Make sure there are no spaces around the `=` sign

### 3. Get Your Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Add it to your `.env` file

### 4. Run the Bot

```bash
python lendinghealthchecker.py
```

Or if using Python 3 specifically:

```bash
python3 lendinghealthchecker.py
```

For production deployment, see `README_DEPLOYMENT.md`.

## Usage

Once the bot is running, open Telegram and:

1. Search for your bot by the username you created
2. Send `/start` to see available commands
3. Use `/add <address> <threshold>` to start monitoring an address
   - Example: `/add 0x1234... 1.5` (global threshold for all protocols)
   - Example: `/add 0x1234... 1.3 morpho` (protocol-specific threshold)
   - Example: `/add 0x1234... 1.2 morpho 0xMarketID` (market-specific threshold)
4. Use `/check` to see current health factors for all monitored addresses
5. Use `/position` to see detailed position information (collateral, debt, liquidation price)
6. Use `/list` to see all addresses you're monitoring
7. Use `/remove <address>` to remove an address from monitoring
8. Use `/stop` to stop monitoring all addresses

You can also paste a Monad address directly to check its health factor instantly.

## Commands

- `/start` - Show help message
- `/add <address> <threshold>` - Set global threshold for all protocols
- `/add <address> <threshold> <protocol>` - Set protocol-specific threshold
- `/add <address> <threshold> <protocol> <market>` - Set market-specific threshold
- `/list` - List all addresses you're monitoring
- `/check` - Check health factors for all monitored addresses (quick view)
- `/check <protocol>` - Check specific protocol (e.g., `/check morpho`)
- `/check <address>` - Check specific address
- `/position` - Show detailed position information (collateral, debt, liquidation price)
- `/position <protocol>` - Show positions for specific protocol
- `/position <address>` - Show positions for specific address
- `/remove <address>` - Remove an address from monitoring
- `/remove <address> <protocol>` - Remove protocol-specific threshold
- `/remove <address> <protocol> <market>` - Remove market-specific threshold
- `/protocols` - List all supported protocols
- `/repay` - Get rebalancing suggestions for positions below threshold
- `/stop` - Stop monitoring all addresses

## Threshold Hierarchy

Thresholds are applied in this order (most specific wins):

1. **Market-specific threshold** (e.g., `/add 0x1234... 1.2 morpho 0xMarketID`)
2. **Protocol-specific threshold** (e.g., `/add 0x1234... 1.3 morpho`)
3. **Global default threshold** (e.g., `/add 0x1234... 1.5`)

## How It Works

### Position Discovery

The bot uses a **Strategy Pattern** to automatically discover positions:

1. **ProtocolManager** iterates through registered protocol strategies
2. Each strategy's `get_positions()` method queries the protocol for user positions
3. Positions are converted to standardized `PositionData` format
4. Health factors are compared against configured thresholds
5. Alerts are sent when health factors drop below thresholds

### Protocol-Specific Details

#### Neverland
- Uses `getUserAccountData()` to get account health factor
- Single position per address (unified account)

#### Morpho Blue
- Uses GraphQL API to discover all markets where user has positions
- Falls back to contract calls for accurate amounts
- Each market is a separate position
- Calculates liquidation price from LLTV (Liquidation Loan-to-Value)

#### Curvance
- Uses `ProtocolReader.getAllDynamicState()` to get all positions
- Uses `ProtocolReader.getPositionHealth()` for aggregate health factors
- Groups positions by MarketManager (since health is aggregate per MarketManager)
- Handles packed cToken addresses and zero addresses using fallback identification

#### Euler V2
- Uses `AccountLens.getAccountEnabledVaultsInfo()` to discover EVC-enabled vaults
- Checks known isolated vaults using `getAccountInfo()` across main account and sub-accounts (0-10)
- Supports sub-account positions (positions can be on sub-account 1, 2, etc., not just main account)
- Each vault is a separate position
- Health factor calculated as `collateralValueLiquidation / liabilityValueLiquidation`

### Periodic Monitoring

The bot runs periodic health checks at the interval specified by `CHECK_INTERVAL` (default: 3600 seconds = 1 hour). When a health factor drops below the threshold, the bot sends an alert with rebalancing suggestions.

## Project Structure

```
.
├── lendinghealthchecker.py      # Main bot logic and Telegram handlers
├── protocol_strategy.py          # Strategy Pattern abstraction (base classes)
├── protocol_strategies_impl.py   # Concrete protocol implementations
├── protocols.py                  # Low-level blockchain functions
├── rebalancing.py                # Rebalancing suggestion logic
├── abis/                         # Contract ABIs
│   ├── neverland.json
│   ├── morpho.json
│   ├── curvance.json
│   ├── euler.json
│   ├── AccountLens.json
│   └── VaultLens.json
├── docs/                         # Documentation
│   ├── CURVANCE_SETUP.md
│   ├── MORPHO_DOCS.md
│   └── SECURITY_GUIDE.md
└── requirements.txt              # Python dependencies
```

## Troubleshooting

- **"No bot token provided"**: Make sure your `.env` file exists and contains `TELEGRAM_BOT_TOKEN=...`
- **Connection errors**: Check that `MONAD_NODE_URL` is correct and accessible
- **No positions found**: Make sure you have active lending positions with debt on the protocol
- **Curvance shows only one position**: This is expected - positions are grouped by MarketManager with aggregate health

## Security

- **Never commit `.env` files**: All sensitive data (API keys, tokens) should be in `.env` files
- **User data**: `lendinghealthchatids.json` contains user monitoring preferences (not sensitive, but should not be committed)
- **Read-only operations**: The bot only reads blockchain data, never signs transactions

See `docs/SECURITY_GUIDE.md` for more security best practices.

## Contributing

Contributions are welcome! To add a new protocol:

1. Implement `LendingProtocolStrategy` in `protocol_strategies_impl.py`
2. Add protocol-specific functions to `protocols.py` if needed
3. Register the strategy in `lendinghealthchecker.py`
4. Add protocol configuration to `PROTOCOL_CONFIG`
5. Update this README

## License

[Add your license here]

## Disclaimer

This bot is not officially affiliated with or endorsed by any protocol. It is an independent tool created for informational purposes only. The bot is not guaranteed to be always accurate or available. Users should not rely solely on this bot for making financial decisions.
