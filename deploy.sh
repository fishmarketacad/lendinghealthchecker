#!/bin/bash

# Deployment script for Lending Health Checker Bot
# Deploys to Digital Ocean server and runs with PM2

set -e  # Exit on error

# Configuration
SERVER_IP="167.172.74.216"
SERVER_USER="root"
DEPLOY_PATH="/root/monadlendinghealthchecker"
REMOTE_HOST="${SERVER_USER}@${SERVER_IP}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting deployment to ${SERVER_IP}...${NC}"

# Check if .env file exists locally
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found locally. Make sure it exists on the server.${NC}"
fi

# Create deployment package (exclude unnecessary files)
echo -e "${GREEN}📦 Preparing deployment package...${NC}"
TEMP_DIR=$(mktemp -d)
DEPLOY_DIR="${TEMP_DIR}/monadlendinghealthchecker"

mkdir -p "${DEPLOY_DIR}"

# Copy necessary files
echo "Copying files..."
cp -r lendinghealthchecker.py "${DEPLOY_DIR}/"
cp -r protocols.py "${DEPLOY_DIR}/"
cp -r rebalancing.py "${DEPLOY_DIR}/"
cp -r requirements.txt "${DEPLOY_DIR}/"

# CRITICAL: Explicitly exclude user data JSON file from being copied
if [ -f lendinghealthchatids.json ]; then
    echo "⚠️  Found local lendinghealthchatids.json - NOT copying (server maintains production copy)"
fi

# Copy ABIs directory (exclude any user data JSON files)
echo "Copying ABIs..."
mkdir -p "${DEPLOY_DIR}/abis"
cp abis/*.json "${DEPLOY_DIR}/abis/" 2>/dev/null || true

# CRITICAL: Ensure user data JSON is NOT in deployment directory
if [ -f "${DEPLOY_DIR}/lendinghealthchatids.json" ]; then
    echo "⚠️  Removing lendinghealthchatids.json from deployment directory..."
    rm -f "${DEPLOY_DIR}/lendinghealthchatids.json"
fi

# Copy ecosystem config if it exists
if [ -f ecosystem.config.js ]; then
    cp ecosystem.config.js "${DEPLOY_DIR}/"
fi

# Explicitly exclude user data JSON file (server maintains production copy)
echo "⚠️  Excluding lendinghealthchatids.json (server maintains production copy)"

# Create .gitignore for deployment
cat > "${DEPLOY_DIR}/.gitignore" << EOF
.env
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
venv/
env/
*.log
lendinghealthchatids.json
*.json
!abis/*.json
EOF

# Explicitly exclude user data JSON file (server maintains production copy)
echo "⚠️  Excluding lendinghealthchatids.json (server maintains production copy)"

# CRITICAL: Double-check that user data JSON is NOT in deployment directory before archiving
if [ -f "${DEPLOY_DIR}/lendinghealthchatids.json" ]; then
    echo "⚠️  WARNING: Found lendinghealthchatids.json in deployment directory - removing..."
    rm -f "${DEPLOY_DIR}/lendinghealthchatids.json"
fi

# Create deployment archive (exclude user data JSON explicitly)
cd "${TEMP_DIR}"
echo "Creating archive (excluding user data JSON)..."
tar czf deploy.tar.gz --exclude='lendinghealthchatids.json' monadlendinghealthchecker/
cd - > /dev/null

# Verify user data JSON is NOT in the archive
if tar tzf "${TEMP_DIR}/deploy.tar.gz" | grep -q "lendinghealthchatids.json"; then
    echo "⚠️  ERROR: lendinghealthchatids.json found in archive! Removing and recreating..."
    rm -f "${TEMP_DIR}/deploy.tar.gz"
    cd "${TEMP_DIR}"
    tar czf deploy.tar.gz --exclude='lendinghealthchatids.json' monadlendinghealthchecker/
    cd - > /dev/null
    echo "✅ Archive recreated without user data JSON"
else
    echo "✅ Verified: User data JSON NOT in archive"
fi

echo -e "${GREEN}📤 Uploading files to server...${NC}"

# Upload to server
scp "${TEMP_DIR}/deploy.tar.gz" "${REMOTE_HOST}:/tmp/"

# Cleanup local temp files
rm -rf "${TEMP_DIR}"

echo -e "${GREEN}🔧 Setting up on server...${NC}"

# Execute remote setup commands
ssh "${REMOTE_HOST}" << 'ENDSSH'
set -e

DEPLOY_PATH="/root/monadlendinghealthchecker"
DEPLOY_TAR="/tmp/deploy.tar.gz"

echo "📂 Extracting deployment package..."
mkdir -p "${DEPLOY_PATH}"

# CRITICAL: Backup existing user data JSON BEFORE extraction
USER_DATA_FILE="${DEPLOY_PATH}/lendinghealthchatids.json"
BACKUP_FILE=""
if [ -f "${USER_DATA_FILE}" ]; then
    BACKUP_FILE="${USER_DATA_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "💾 Backing up existing user data to ${BACKUP_FILE}..."
    cp "${USER_DATA_FILE}" "${BACKUP_FILE}"
    echo "✅ Backup created: $(wc -c < "${BACKUP_FILE}") bytes"
else
    echo "ℹ️  No existing user data file found (will create new one if needed)"
fi

# Extract deployment package
cd "${DEPLOY_PATH}"
tar xzf "${DEPLOY_TAR}" --strip-components=1
rm -f "${DEPLOY_TAR}"

# CRITICAL: Check if extraction created an empty/invalid user data file and remove it
if [ -f "${USER_DATA_FILE}" ]; then
    FILE_SIZE=$(stat -f%z "${USER_DATA_FILE}" 2>/dev/null || stat -c%s "${USER_DATA_FILE}" 2>/dev/null || echo "0")
    if [ "$FILE_SIZE" -lt 3 ]; then
        echo "⚠️  Found empty/invalid user data file from deployment (${FILE_SIZE} bytes) - removing..."
        rm -f "${USER_DATA_FILE}"
    fi
fi

# CRITICAL: Immediately restore user data from backup (overwrite any file from deployment)
if [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
    echo "🔄 Restoring user data from backup..."
    cp "$BACKUP_FILE" "${USER_DATA_FILE}"
    echo "✅ User data restored: $(wc -c < "${USER_DATA_FILE}") bytes"
elif [ -f "${USER_DATA_FILE}" ]; then
    # If backup doesn't exist but file exists, check if it's valid
    FILE_SIZE=$(stat -f%z "${USER_DATA_FILE}" 2>/dev/null || stat -c%s "${USER_DATA_FILE}" 2>/dev/null || echo "0")
    if [ "$FILE_SIZE" -lt 3 ]; then
        echo "⚠️  User data file is empty or invalid, checking for any backup..."
        LATEST_BACKUP=$(ls -t "${DEPLOY_PATH}/lendinghealthchatids.json.backup."* 2>/dev/null | head -1)
        if [ -n "$LATEST_BACKUP" ] && [ -f "$LATEST_BACKUP" ]; then
            echo "🔄 Found backup, restoring..."
            cp "$LATEST_BACKUP" "${USER_DATA_FILE}"
            echo "✅ User data restored from latest backup"
        fi
    else
        echo "✅ User data file exists and appears valid: ${FILE_SIZE} bytes"
    fi
else
    # No file exists - create empty one only if no backups exist
    echo "📝 No user data file found, checking for backups..."
    LATEST_BACKUP=$(ls -t "${DEPLOY_PATH}/lendinghealthchatids.json.backup."* 2>/dev/null | head -1)
    if [ -n "$LATEST_BACKUP" ] && [ -f "$LATEST_BACKUP" ]; then
        echo "🔄 Found backup, restoring..."
        cp "$LATEST_BACKUP" "${USER_DATA_FILE}"
        echo "✅ User data restored from latest backup"
    else
        echo "📝 Creating empty user data file..."
        echo "{}" > "${USER_DATA_FILE}"
    fi
fi

echo "🐍 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

echo "📥 Installing/updating dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Verifying ABIs..."
if [ -d "abis" ] && [ "$(ls -A abis/*.json 2>/dev/null)" ]; then
    echo "  Found ABI files:"
    ls -1 abis/*.json | xargs -I {} basename {}
    # Verify Neverland ABI specifically
    if [ -f "abis/neverland.json" ]; then
        echo "  ✅ Neverland ABI found"
    else
        echo "  ⚠️  Warning: Neverland ABI not found!"
    fi
else
    echo "  ⚠️  Warning: No ABI files found in abis/ directory!"
fi

# Final verification: Ensure user data JSON exists and is valid
if [ -f "${USER_DATA_FILE}" ]; then
    FILE_SIZE=$(stat -f%z "${USER_DATA_FILE}" 2>/dev/null || stat -c%s "${USER_DATA_FILE}" 2>/dev/null || echo "0")
    if [ "$FILE_SIZE" -gt 2 ]; then
        echo "✅ User data file verified (size: ${FILE_SIZE} bytes)"
    else
        echo "⚠️  Warning: User data file is empty or very small (${FILE_SIZE} bytes)"
        echo "   Attempting to restore from latest backup..."
        LATEST_BACKUP=$(ls -t "${DEPLOY_PATH}/lendinghealthchatids.json.backup."* 2>/dev/null | head -1)
        if [ -n "$LATEST_BACKUP" ] && [ -f "$LATEST_BACKUP" ]; then
            cp "$LATEST_BACKUP" "${USER_DATA_FILE}"
            echo "✅ Restored from backup: $(wc -c < "${USER_DATA_FILE}") bytes"
        fi
    fi
else
    echo "⚠️  Warning: User data file not found - attempting to restore from backup..."
    LATEST_BACKUP=$(ls -t "${DEPLOY_PATH}/lendinghealthchatids.json.backup."* 2>/dev/null | head -1)
    if [ -n "$LATEST_BACKUP" ] && [ -f "$LATEST_BACKUP" ]; then
        cp "$LATEST_BACKUP" "${USER_DATA_FILE}"
        echo "✅ Restored from backup: $(wc -c < "${USER_DATA_FILE}") bytes"
    else
        echo "📝 Creating empty user data file..."
        echo "{}" > "${USER_DATA_FILE}"
    fi
fi

echo "📋 Checking PM2..."
if ! command -v pm2 &> /dev/null; then
    echo "Installing PM2..."
    npm install -g pm2
fi

echo "🔄 Restarting bot with PM2..."
# Stop existing instance if running
pm2 stop lendinghealthchecker 2>/dev/null || true
pm2 delete lendinghealthchecker 2>/dev/null || true

# Start with ecosystem config if it exists, otherwise use direct command
if [ -f ecosystem.config.js ]; then
    pm2 start ecosystem.config.js
else
    pm2 start lendinghealthchecker.py \
        --name lendinghealthchecker \
        --interpreter venv/bin/python \
        --log-date-format "YYYY-MM-DD HH:mm:ss Z" \
        --max-memory-restart 500M \
        --log /root/monadlendinghealthchecker/logs/app.log \
        --error /root/monadlendinghealthchecker/logs/error.log \
        --merge-logs \
        --log-type json
fi

# Save PM2 process list
pm2 save

# Setup PM2 startup script
pm2 startup systemd -u root --hp /root | grep -v "PM2" | bash || true

echo "✅ Deployment complete!"
echo ""
echo "📊 PM2 Status:"
pm2 status

echo ""
echo "📝 Recent logs (last 20 lines):"
pm2 logs lendinghealthchecker --lines 20 --nostream || true

ENDSSH

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  ssh ${REMOTE_HOST}"
echo "  pm2 logs lendinghealthchecker"
echo "  pm2 restart lendinghealthchecker"
echo "  pm2 status"

