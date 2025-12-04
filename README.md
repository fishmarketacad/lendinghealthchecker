# Neverland Health Factor Monitor Bot

A Telegram bot that monitors health factors for Neverland lending positions on Monad blockchain.

## Setup

### 1. Install Python Dependencies

This is a **Python** project, not Node.js. Install dependencies using `pip`:

```bash
pip install -r requirements.txt
```

Or if you prefer using a virtual environment (recommended):

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

Create a `.env` file in the project root with the following:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
MONAD_NODE_URL=https://rpc.monad.xyz
CHECK_INTERVAL=3600
```

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
python neverlandhealthchecker.py
```

Or if using Python 3 specifically:

```bash
python3 neverlandhealthchecker.py
```

## Usage

Once the bot is running, open Telegram and:

1. Search for your bot by the username you created
2. Send `/start` to see available commands
3. Use `/monitor <threshold> <address>` to start monitoring an address
   - Example: `/monitor 1.5 0x1234567890123456789012345678901234567890`
4. Use `/check` to see current monitoring status
5. Use `/stop` to stop monitoring

You can also paste a Monad address directly to check its health factor instantly.

## Commands

- `/start` - Show help message
- `/add <protocol> <threshold> <address>` - Add an address to monitor
  - Example: `/add neverland 1.5 0x1234...`
  - Example: `/add morpho 1.5 0x1234...`
- `/list` - List all addresses you're monitoring
- `/check` - Check health factors for all monitored addresses
- `/remove <address>` - Remove an address from monitoring
- `/protocols` - List all supported protocols
- `/stop` - Stop monitoring all addresses

## Supported Protocols

- **Neverland** (`neverland`) - On Monad blockchain
- **Morpho** (`morpho`) - On Ethereum (needs contract address configuration)

See `MORPHO_SETUP.md` for Morpho-specific setup instructions.

## Troubleshooting

- **"No bot token provided"**: Make sure your `.env` file exists and contains `TELEGRAM_BOT_TOKEN=...`
- **"Could not read package.json"**: This is a Python project, use `pip install -r requirements.txt` instead of `npm install`
- **Connection errors**: Check that `MONAD_NODE_URL` is correct and accessible

