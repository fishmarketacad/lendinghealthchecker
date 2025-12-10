# Deployment Guide

## Quick Start

### Using `deploy-auto.sh` (Recommended)

This script automatically:
1. Commits your changes
2. Pushes to GitHub
3. Deploys to your server

**Usage:**
```bash
# With custom commit message
./deploy-auto.sh "Your commit message here"

# With auto-generated commit message (uses timestamp)
./deploy-auto.sh
```

**Example:**
```bash
./deploy-auto.sh "Fix rate limiting bug"
```

### Manual Deployment

If you want to deploy without committing:
```bash
./deploy.sh
```

## What Gets Deployed

The deployment script:
- ✅ Copies all Python files (`*.py`)
- ✅ Copies `requirements.txt`
- ✅ Copies `abis/` directory
- ✅ Copies `ecosystem.config.js` (if exists)
- ❌ **Excludes** `.env` files (server maintains its own)
- ❌ **Excludes** `bot.db` (database stays on server)
- ❌ **Excludes** `lendinghealthchatids.json` (legacy, stays on server)
- ❌ **Excludes** deployment scripts (they're in `.gitignore`)

## Database Handling

The deployment script automatically:
1. **Backs up** existing `bot.db` before deployment
2. **Preserves** the database during deployment
3. **Restores** from backup if deployment creates empty database

Your user data is safe! 🛡️

## Server Setup

The script automatically:
- Sets up Python virtual environment
- Installs/updates dependencies
- Restarts the bot with PM2
- Shows recent logs

## Troubleshooting

### Git Push Fails
If GitHub push fails, deployment still continues. You can manually push later:
```bash
git push origin main
```

### No Changes to Commit
If there are no changes, the script will skip committing but still deploy.

### Check Server Status
```bash
ssh root@167.172.74.216
pm2 status
pm2 logs lendinghealthchecker
```

## Environment Variables

Make sure your server has `.env` file with:
- `TELEGRAM_BOT_TOKEN`
- `MONAD_NODE_URL`
- `CHECK_INTERVAL` (optional, default: 3600)
- `DATABASE_FILE` (optional, default: bot.db)
- `USER_PROCESSING_LIMIT` (optional, default: 10)
- `RPC_RATE_LIMIT` (optional, default: 10)
- `GRAPHQL_RATE_LIMIT` (optional, default: 5)

## First Deployment

On first deployment, the database will be created automatically. Users will need to re-add their addresses using `/add` command.
