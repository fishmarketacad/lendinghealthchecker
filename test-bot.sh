#!/bin/bash
# Script to test the bot after deployment by sending a test command and checking logs

BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
CHAT_ID="${TELEGRAM_TEST_CHAT_ID:-7677194823}"  # Default to user's chat ID
COMMAND="${1:-/position morpho}"  # Default command

if [ -z "$BOT_TOKEN" ]; then
    echo "Error: TELEGRAM_BOT_TOKEN not set"
    exit 1
fi

echo "🧪 Testing bot with command: $COMMAND"
echo "📱 Sending to chat: $CHAT_ID"

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

# Check recent logs (last 30 lines)
echo ""
echo "📋 Recent bot logs:"
ssh root@167.172.74.216 "pm2 logs lendinghealthchecker --lines 30 --nostream" 2>/dev/null || echo "Could not fetch logs"

echo ""
echo "✅ Test complete!"

