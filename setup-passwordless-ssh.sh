#!/bin/bash

# Setup script for passwordless SSH deployment
# This will set up SSH key authentication so deploy.sh doesn't ask for password

set -e

# Configuration (from deploy.sh)
SERVER_IP="167.172.74.216"
SERVER_USER="root"
REMOTE_HOST="${SERVER_USER}@${SERVER_IP}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔐 Setting up passwordless SSH for deployment...${NC}"
echo ""

# Check if SSH key exists
SSH_KEY="$HOME/.ssh/id_rsa"
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${YELLOW}⚠️  No SSH key found. Generating one...${NC}"
    ssh-keygen -t rsa -b 4096 -f "$SSH_KEY" -N "" -C "deploy-key-$(date +%Y%m%d)"
    echo -e "${GREEN}✅ SSH key generated${NC}"
else
    echo -e "${GREEN}✅ SSH key found: $SSH_KEY${NC}"
fi

# Check if public key exists
SSH_PUBKEY="$SSH_KEY.pub"
if [ ! -f "$SSH_PUBKEY" ]; then
    echo -e "${RED}❌ Public key not found at $SSH_PUBKEY${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}📋 Public key to add to server:${NC}"
echo "----------------------------------------"
cat "$SSH_PUBKEY"
echo "----------------------------------------"
echo ""

echo -e "${BLUE}📝 Instructions:${NC}"
echo "1. SSH into the server: ${YELLOW}ssh ${REMOTE_HOST}${NC}"
echo "2. Run this command on the server:"
echo -e "   ${YELLOW}mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '$(cat $SSH_PUBKEY)' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys${NC}"
echo ""
echo -e "Or run this command from your local machine (will prompt for password once):"
echo -e "${YELLOW}ssh-copy-id ${REMOTE_HOST}${NC}"
echo ""

read -p "Have you added the SSH key to the server? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}🔍 Testing SSH connection...${NC}"
    if ssh -o BatchMode=yes -o ConnectTimeout=5 "${REMOTE_HOST}" "echo 'SSH connection successful!'" 2>/dev/null; then
        echo -e "${GREEN}✅ Passwordless SSH is working!${NC}"
        echo -e "${GREEN}✅ You can now run ./deploy.sh without entering a password${NC}"
    else
        echo -e "${RED}❌ Passwordless SSH is not working yet.${NC}"
        echo -e "${YELLOW}Please make sure you've added the public key to the server.${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Please add the SSH key to the server first, then run this script again.${NC}"
    exit 1
fi

