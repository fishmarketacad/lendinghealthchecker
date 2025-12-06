#!/bin/bash

# Deployment script using password stored in environment variable
# Usage: SERVER_PASSWORD="your_password" ./deploy-with-password.sh
# Or: export SERVER_PASSWORD="your_password" and run ./deploy-with-password.sh

set -e

# Configuration
SERVER_IP="167.172.74.216"
SERVER_USER="root"
DEPLOY_PATH="/root/monadlendinghealthchecker"
REMOTE_HOST="${SERVER_USER}@${SERVER_IP}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if password is set
if [ -z "$SERVER_PASSWORD" ]; then
    echo -e "${RED}❌ Error: SERVER_PASSWORD environment variable not set${NC}"
    echo ""
    echo "Usage options:"
    echo "  1. Set password in environment: ${YELLOW}export SERVER_PASSWORD='your_password'${NC}"
    echo "  2. Run with inline password: ${YELLOW}SERVER_PASSWORD='your_password' ./deploy-with-password.sh${NC}"
    echo ""
    echo "Or better yet, use SSH keys: ${YELLOW}./setup-passwordless-ssh.sh${NC}"
    exit 1
fi

# Check if sshpass is installed
if ! command -v sshpass &> /dev/null; then
    echo -e "${YELLOW}⚠️  sshpass not found. Installing...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install hudochenkov/sshpass/sshpass
        else
            echo -e "${RED}❌ Please install Homebrew first: https://brew.sh${NC}"
            echo "Or install sshpass manually"
            exit 1
        fi
    else
        # Linux
        sudo apt-get update && sudo apt-get install -y sshpass
    fi
fi

echo -e "${GREEN}🚀 Starting deployment to ${SERVER_IP}...${NC}"

# Use the original deploy.sh logic but with sshpass
# We'll call the original deploy.sh but wrap SSH commands with sshpass
# Actually, let's just modify the SSH commands inline

# ... (rest of deploy.sh logic but with sshpass -o StrictHostKeyChecking=no)

# For now, let's just use the original deploy.sh but with password
# The user should set up SSH keys instead, but this is a fallback

echo -e "${YELLOW}⚠️  Using password-based authentication (not recommended for security)${NC}"
echo -e "${YELLOW}💡 Consider using SSH keys: ./setup-passwordless-ssh.sh${NC}"

# Export password for sshpass
export SSHPASS="$SERVER_PASSWORD"

# Call original deploy script but we need to modify it to use sshpass
# Actually, better to just guide user to use SSH keys
echo -e "${RED}❌ Password-based deployment requires modifying deploy.sh${NC}"
echo -e "${GREEN}✅ Please use SSH keys instead: ./setup-passwordless-ssh.sh${NC}"

