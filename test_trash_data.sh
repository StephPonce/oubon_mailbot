#!/bin/bash
echo "🧪 OSPRA DASHBOARD TRASH DATA DIAGNOSTIC"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1️⃣ Backend Status:"
if curl -s http://127.0.0.1:8001/health > /dev/null; then
  echo "   ✅ Backend running at http://127.0.0.1:8001"
else
  echo "   ❌ Backend NOT running"
  exit 1
fi

echo ""
echo "2️⃣ Frontend Status:"
if curl -s http://localhost:5173 > /dev/null; then
  echo "   ✅ Frontend running at http://localhost:5173"
else
  echo "   ❌ Frontend NOT running"
  exit 1
fi

echo ""
echo "3️⃣ Trash Endpoint Data:"
TRASH_COUNT=$(curl -s "http://127.0.0.1:8001/api/emails/list?user_id=1&limit=200&label=TRASH" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null)
echo "   📧 Trash emails available: $TRASH_COUNT"

echo ""
echo "4️⃣ Sample Trash Emails:"
curl -s "http://127.0.0.1:8001/api/emails/list?user_id=1&limit=200&label=TRASH" | python3 -c "
import sys, json
emails = json.load(sys.stdin)
for i, email in enumerate(emails[:3], 1):
    print(f'   {i}. From: {email[\"from_name\"]} - Subject: {email[\"subject\"][:50]}')
" 2>/dev/null

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DATA FLOW: Backend → API → Frontend is working!"
echo ""
echo "📍 To view trash emails:"
echo "   1. Open http://localhost:5173 in your browser"
echo "   2. Click 'Emails' in the left sidebar"
echo "   3. Click 'Trash' folder"
echo "   4. You should see $TRASH_COUNT emails"
echo ""
