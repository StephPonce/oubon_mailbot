# A/B Testing - Quick Start Guide 🚀

Get your first A/B test running in under 5 minutes!

---

## Step 1: Open the Dashboard

Navigate to the A/B Testing page:

```
http://localhost:5173/abtesting
```

You should see the A/B Testing dashboard with a "Create Test" button.

---

## Step 2: Create a Price Test

1. Click the **"Create Test"** button
2. Select **"Price Test"**
3. Fill in the form:

```
Product ID: my-product-123
Store ID: 1
Current Price: 29.99
Test Price 1: 24.99
Test Price 2: 34.99
Duration: 7 days
Min Sample Size: 50
```

4. Click **"Create Test"**

---

## Step 3: Start the Test

Once created, you'll see your test in the list:

1. Click on your test card
2. Click the **"Start"** button
3. The test status will change to "Running"

---

## Step 4: Record Test Data

### Option A: Via API (Simulated Traffic)

```bash
# Get the test ID from the UI (e.g., 1)
TEST_ID=1

# Record 100 impressions and conversions
for i in {1..100}; do
  # Record impression
  curl -s -X POST http://localhost:8001/api/abtesting/events/impression \
    -H "Content-Type: application/json" \
    -d "{\"test_id\": $TEST_ID, \"visitor_id\": \"visitor-$i\", \"variant_id\": $((1 + RANDOM % 3))}"

  # Random conversion (30% rate)
  if [ $((RANDOM % 10)) -lt 3 ]; then
    curl -s -X POST http://localhost:8001/api/abtesting/events/conversion \
      -H "Content-Type: application/json" \
      -d "{\"test_id\": $TEST_ID, \"visitor_id\": \"visitor-$i\", \"revenue\": 29.99}"
  fi
done

echo "✅ Test data recorded!"
```

### Option B: Real Traffic

Integrate with your store's analytics:

```javascript
// When visitor views product
fetch('http://localhost:8001/api/abtesting/events/variant', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    test_id: 1,
    visitor_id: visitorId
  })
}).then(res => res.json())
  .then(data => {
    // Show visitor the assigned variant price
    displayPrice(data.variant.config.price);
  });

// When visitor makes purchase
fetch('http://localhost:8001/api/abtesting/events/conversion', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    test_id: 1,
    visitor_id: visitorId,
    revenue: purchaseAmount
  })
});
```

---

## Step 5: Monitor Results

The dashboard automatically refreshes every 30 seconds. Watch for:

- **Conversion Rate** for each variant
- **Statistical Significance** badges
- **Winner** indication when significant

Click on the test card to see detailed metrics:

- Impressions, conversions, revenue per variant
- Confidence intervals
- P-values
- Relative lift vs. control

---

## Step 6: End the Test

When you have enough data (significance badge appears):

1. Click on your test
2. Click the **"End"** button
3. Review the winner in the test details

---

## Step 7: Implement the Winner

### Auto-Implementation

If you enabled "Auto-implement winner" during creation, the winning price will be automatically deployed to Shopify when the test ends.

### Manual Implementation

If auto-implement is off:

```bash
# Get the winning variant config from the UI
# Then deploy manually via API

curl -X POST http://localhost:8001/api/abtesting/tests/{test_id}/end \
  -H "Content-Type: application/json" \
  -d '{"implement_winner": true}'
```

---

## 🎯 Example Test Scenarios

### Scenario 1: Find Optimal Price

**Goal:** Maximize revenue per visitor

```json
{
  "current_price": 49.99,
  "test_prices": [39.99, 44.99, 54.99, 59.99],
  "duration_days": 14,
  "min_sample_size": 200
}
```

**Expected Outcome:** Discover the price point that generates the most revenue.

---

### Scenario 2: Improve Click-Through Rate

**Goal:** Get more product page views

```json
{
  "current_title": "Bluetooth Speaker",
  "variant_titles": [
    "Premium Bluetooth Speaker - Crystal Clear Sound",
    "Portable Speaker: 24Hr Battery, Waterproof, Deep Bass",
    "Wireless Speaker - Rated #1 by Audiophiles"
  ],
  "duration_days": 7
}
```

**Expected Outcome:** Title that attracts the most clicks.

---

### Scenario 3: Boost Conversions

**Goal:** Increase purchase rate

```json
{
  "current_description": "High-quality Bluetooth speaker with great sound.",
  "variant_descriptions": [
    "🎵 Features:\n• 24-hour battery\n• Waterproof IPX7\n• Premium sound quality",
    "Experience music like never before! Our #1 rated speaker delivers crystal-clear sound with deep bass. Perfect for parties, travel, and outdoor adventures. Order now with free shipping!"
  ],
  "duration_days": 14
}
```

**Expected Outcome:** Description that converts more visitors into buyers.

---

## 📊 Understanding Results

### Statistical Significance

- **p < 0.05:** Variant is significantly different from control
- **p < 0.01:** Highly significant difference
- **p > 0.05:** No significant difference (need more data)

### Confidence Intervals

Shows the range where the true conversion rate likely falls:

```
95% CI: 4.2% - 6.8%
```

This means we're 95% confident the real conversion rate is between 4.2% and 6.8%.

### Relative Lift

```
+23.5% lift vs. control
```

This variant performs 23.5% better than the control.

---

## ⚡ Quick Tips

1. **Start Small:** Begin with 2-3 variants, not 10
2. **Run Longer:** Better to run 14 days than 3 days
3. **Wait for Significance:** Don't end early - let the data mature
4. **Test One Thing:** Don't change price AND title simultaneously
5. **Learn and Iterate:** Use insights from one test to inform the next

---

## 🔍 Troubleshooting

### Test not showing data?

```bash
# Check test ID is correct
curl http://localhost:8001/api/abtesting/tests/{test_id}

# Verify events are being recorded
curl http://localhost:8001/api/abtesting/tests/{test_id}?include_results=true
```

### Backend not responding?

```bash
# Check backend health
curl http://localhost:8001/health

# Restart backend if needed
cd /path/to/project
uv run uvicorn ospra_os.main:app --reload --port 8001
```

### Frontend not loading?

```bash
# Check frontend is running
curl http://localhost:5173

# Start frontend if needed
cd frontend
npm run dev
```

---

## 📱 Mobile Testing

Same API works for mobile apps:

```swift
// iOS Example
let url = URL(string: "http://localhost:8001/api/abtesting/events/variant")!
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.setValue("application/json", forHTTPHeaderField: "Content-Type")

let body: [String: Any] = [
    "test_id": 1,
    "visitor_id": visitorId
]
request.httpBody = try? JSONSerialization.data(withJSONObject: body)

URLSession.shared.dataTask(with: request) { data, response, error in
    // Handle response
}.resume()
```

---

## 🎓 Next Steps

Once you're comfortable with basic tests:

1. **Explore Other Test Types:** Try title, description, and image tests
2. **Advanced Analytics:** Dive into confidence intervals and statistical significance
3. **Automation:** Set up auto-implementation for winning variants
4. **Integration:** Connect to your real store traffic
5. **Scale:** Run multiple tests simultaneously across different products

---

## 📞 Need Help?

- **Documentation:** See `AB_TESTING_COMPLETE.md`
- **API Reference:** http://localhost:8001/docs
- **Test Suite:** Run `bash test_abtesting_api.sh`
- **Integration Tests:** Run `bash test_abtesting_integration.sh`

---

**Ready to optimize?** Click "Create Test" and start experimenting! 🚀
