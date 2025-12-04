#!/bin/bash

# Script to restore user data from backup on server
# Run this on the server if user data was accidentally lost

SERVER_USER="root"
SERVER_IP="167.172.74.216"
DEPLOY_PATH="/root/monadlendinghealthchecker"

echo "🔍 Looking for user data backups on server..."

ssh "${SERVER_USER}@${SERVER_IP}" << 'ENDSSH'
DEPLOY_PATH="/root/monadlendinghealthchecker"
cd "${DEPLOY_PATH}"

# Find all backups
BACKUPS=$(ls -t lendinghealthchatids.json.backup.* 2>/dev/null | head -5)

if [ -z "$BACKUPS" ]; then
    echo "❌ No backups found"
    exit 1
fi

echo "Found backups:"
echo "$BACKUPS" | nl

# Get latest backup
LATEST_BACKUP=$(ls -t lendinghealthchatids.json.backup.* 2>/dev/null | head -1)

if [ -n "$LATEST_BACKUP" ]; then
    echo ""
    echo "📋 Latest backup: $LATEST_BACKUP"
    echo "📊 Backup size: $(stat -f%z "$LATEST_BACKUP" 2>/dev/null || stat -c%s "$LATEST_BACKUP" 2>/dev/null) bytes"
    echo ""
    read -p "Restore this backup? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp "$LATEST_BACKUP" lendinghealthchatids.json
        echo "✅ User data restored from $LATEST_BACKUP"
        echo "🔄 Restarting bot..."
        pm2 restart lendinghealthchecker
    else
        echo "Cancelled"
    fi
fi
ENDSSH

