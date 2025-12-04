#!/bin/bash

# Initial server setup script
# Run this ONCE on the server before first deployment

set -e

echo "🔧 Setting up server for Lending Health Checker Bot..."

# Update system
echo "📦 Updating system packages..."
apt-get update
apt-get upgrade -y

# Install Python and pip
echo "🐍 Installing Python..."
apt-get install -y python3 python3-pip python3-venv

# Install Node.js and npm (for PM2)
echo "📦 Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install PM2 globally
echo "📊 Installing PM2..."
npm install -g pm2

# Create directory structure
echo "📂 Creating directories..."
mkdir -p /root/monadlendinghealthchecker/logs
mkdir -p /root/monadlendinghealthchecker/abis

# Set up log rotation for PM2 (system-level)
echo "📝 Setting up log rotation..."
cat > /etc/logrotate.d/pm2 << 'EOF'
/root/.pm2/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        pm2 reloadLogs
    endscript
}

/root/monadlendinghealthchecker/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF

# Create .env template if it doesn't exist
if [ ! -f /root/monadlendinghealthchecker/.env ]; then
    echo "📝 Creating .env template..."
    cat > /root/monadlendinghealthchecker/.env << 'EOF'
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Check interval in seconds (default: 3600 = 1 hour)
CHECK_INTERVAL=3600

# User data file
USER_DATA_FILE=lendinghealthchatids.json

# Monad RPC
MONAD_NODE_URL=https://rpc.monad.xyz

# Protocol-specific addresses (optional)
# MORPHO_BLUE_ADDRESS=0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb
# CURVANCE_PROTOCOL_READER_ADDRESS=0x...
# CURVANCE_APP_URL=https://app.curvance.com
EOF
    echo "⚠️  Please edit /root/monadlendinghealthchecker/.env and add your Telegram bot token!"
fi

echo "✅ Server setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit /root/monadlendinghealthchecker/.env and add your Telegram bot token"
echo "2. Run deploy.sh from your local machine"

