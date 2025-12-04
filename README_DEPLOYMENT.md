# Deployment Guide

## Prerequisites

1. **SSH access** to your Digital Ocean server (167.172.74.216)
2. **Local machine** with `ssh` and `scp` installed
3. **Telegram Bot Token** ready

## Initial Server Setup (Run Once)

### Option 1: Run setup script on server

```bash
# Copy setup script to server
scp setup-server.sh root@167.172.74.216:/root/

# SSH into server and run setup
ssh root@167.172.74.216
chmod +x /root/setup-server.sh
/root/setup-server.sh
```

### Option 2: Manual setup

SSH into your server and run:

```bash
# Install dependencies
apt-get update
apt-get install -y python3 python3-pip python3-venv
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
npm install -g pm2

# Create directories
mkdir -p /root/monadlendinghealthchecker/logs
mkdir -p /root/monadlendinghealthchecker/abis

# Create .env file
nano /root/monadlendinghealthchecker/.env
# Add your TELEGRAM_BOT_TOKEN and other config
```

## Deployment

### First Deployment

1. **Set up .env file on server**:
   ```bash
   ssh root@167.172.74.216
   nano /root/monadlendinghealthchecker/.env
   ```
   
   Add:
   ```bash
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   CHECK_INTERVAL=3600
   USER_DATA_FILE=lendinghealthchatids.json
   MONAD_NODE_URL=https://rpc.monad.xyz
   ```

2. **Deploy from local machine**:
   ```bash
   ./deploy.sh
   ```

### Subsequent Deployments

Just run:
```bash
./deploy.sh
```

The script will:
- Upload latest code
- Install/update dependencies
- Restart the bot with PM2
- Show status and logs

## PM2 Management

### View logs
```bash
ssh root@167.172.74.216
pm2 logs lendinghealthchecker
```

### View last 50 lines
```bash
pm2 logs lendinghealthchecker --lines 50
```

### Restart bot
```bash
pm2 restart lendinghealthchecker
```

### Stop bot
```bash
pm2 stop lendinghealthchecker
```

### View status
```bash
pm2 status
```

### Monitor (real-time)
```bash
pm2 monit
```

## Log Management

PM2 is configured with automatic log rotation:
- **Max log size**: 10MB per file
- **Retention**: 5 rotated files
- **Compression**: Enabled
- **System logrotate**: Daily rotation for PM2 logs

Logs are stored in:
- `/root/monadlendinghealthchecker/logs/app.log` - Application output
- `/root/monadlendinghealthchecker/logs/error.log` - Errors
- `/root/monadlendinghealthchecker/logs/combined.log` - Combined logs

### Manual log cleanup

If logs get too large:

```bash
# Clear PM2 logs
pm2 flush

# Or manually rotate
pm2 reloadLogs

# Or delete old logs
find /root/monadlendinghealthchecker/logs -name "*.log.*" -mtime +7 -delete
```

## Troubleshooting

### Bot not starting

1. Check PM2 logs:
   ```bash
   pm2 logs lendinghealthchecker --err
   ```

2. Check if .env file exists and has correct token:
   ```bash
   cat /root/monadlendinghealthchecker/.env
   ```

3. Test Python script manually:
   ```bash
   cd /root/monadlendinghealthchecker
   source venv/bin/activate
   python lendinghealthchecker.py
   ```

### Connection issues

1. Check RPC connection:
   ```bash
   curl https://rpc.monad.xyz
   ```

2. Check Python dependencies:
   ```bash
   source venv/bin/activate
   pip list
   ```

### PM2 not persisting after reboot

```bash
pm2 startup systemd -u root --hp /root
# Follow the instructions it prints
pm2 save
```

## Environment Variables

Edit `/root/monadlendinghealthchecker/.env`:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token

# Optional
CHECK_INTERVAL=3600
MONAD_NODE_URL=https://rpc.monad.xyz
MORPHO_BLUE_ADDRESS=0x...
CURVANCE_PROTOCOL_READER_ADDRESS=0x...
```

After editing, restart:
```bash
pm2 restart lendinghealthchecker
```

## Updating Code

Just run `./deploy.sh` again. It will:
- Upload new code
- Restart the bot automatically
- Preserve your .env file and user data

## Backup

Important files to backup:
- `/root/monadlendinghealthchecker/.env` - Configuration
- `/root/monadlendinghealthchecker/lendinghealthchatids.json` - User data

```bash
# Backup user data
cp /root/monadlendinghealthchecker/lendinghealthchatids.json /root/backup-$(date +%Y%m%d).json
```

