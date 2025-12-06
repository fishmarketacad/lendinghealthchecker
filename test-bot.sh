#!/bin/bash
# Script to test the bot after deployment by sending test commands and checking logs

BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
CHAT_ID="${TELEGRAM_TEST_CHAT_ID:-7677194823}"  # Default to user's chat ID

if [ -z "$BOT_TOKEN" ]; then
    echo "Error: TELEGRAM_BOT_TOKEN not set"
    exit 1
fi

# Default commands to test if none provided
if [ $# -eq 0 ]; then
    COMMANDS=("/check curvance")
else
    COMMANDS=("$@")
fi

echo "🧪 Testing bot with ${#COMMANDS[@]} command(s)"
echo "📱 Sending to chat: $CHAT_ID"
echo ""

for COMMAND in "${COMMANDS[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 Testing: $COMMAND"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Send the command via Telegram Bot API
    RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "{
            \"chat_id\": ${CHAT_ID},
            \"text\": \"${COMMAND}\"
        }")
    
    echo "📤 Response: $RESPONSE"
    
    # Wait a bit for the bot to process
    echo "⏳ Waiting 5 seconds for bot to process..."
    sleep 5
    
    echo ""
done

# Check recent logs (last 100 lines, filtered for Curvance)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Recent Curvance logs:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ssh root@167.172.74.216 "pm2 logs lendinghealthchecker --lines 200 --nostream 2>&1 | grep -i 'curvance\|error\|position\|marketmanager\|cToken' | tail -50" 2>/dev/null || echo "Could not fetch logs"

echo ""
echo "✅ Test complete!"

