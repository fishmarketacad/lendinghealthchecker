#!/bin/bash

# Automated deployment script that handles git push + deploy
# Usage: ./deploy-auto.sh [commit_message]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

COMMIT_MSG="${1:-Auto-deploy: $(date +%Y-%m-%d\ %H:%M:%S)}"

echo -e "${GREEN}🚀 Starting automated deployment...${NC}"

# Step 1: Git add, commit, and push
echo -e "${GREEN}📝 Committing changes...${NC}"
git add -A

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo -e "${YELLOW}⚠️  No changes to commit${NC}"
else
    git commit -m "$COMMIT_MSG"
    echo -e "${GREEN}✅ Changes committed${NC}"
fi

echo -e "${GREEN}📤 Pushing to GitHub...${NC}"
git push origin main || {
    echo -e "${RED}❌ Git push failed. Continuing with deployment anyway...${NC}"
}

echo -e "${GREEN}✅ Git push complete${NC}"

# Step 2: Deploy
echo -e "${GREEN}🚀 Starting deployment...${NC}"
./deploy.sh

echo -e "${GREEN}✅ Automated deployment complete!${NC}"

