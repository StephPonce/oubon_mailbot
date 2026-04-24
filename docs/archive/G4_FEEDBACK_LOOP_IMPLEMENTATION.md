# G4: Complete Feedback Loop - Implementation Guide

**Status:** ✅ MODELS CREATED - Services & API In Progress
**Date:** 2025-12-12
**Priority:** 🔥 CRITICAL - This is the CORE differentiator

## What This Feature Does

Transforms Ospra from "AI that guesses" to "AI that learns from reality":

```
BEFORE:
AI → Recommends product → User deploys → ??? (no feedback)
AI keeps making same recommendations, never learns

AFTER:
AI → Recommends product → User deploys → Product sells (or doesn't)
     ↑                                          ↓
     └──── AI learns & improves ←─── Sales data synced
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FEEDBACK LOOP SYSTEM                      │
└─────────────────────────────────────────────────────────────┘

1. RECOMMENDATION PHASE
   - AI recommends product with confidence score (85%)
   - Predicts: $500/month revenue, 40% margin
   - User accepts → Creates RecommendationOutcome record

2. PERFORMANCE TRACKING (Every 6 hours)
   - Sync sales from Shopify/Amazon
   - Store daily snapshots in ProductPerformance
   - Track: orders, revenue, profit, conversion rate

3. OUTCOME EVALUATION (Daily)
   - After 7 days minimum: evaluate outcome
   - Compare actual vs predicted performance
   - Classify: exceptional, success, moderate, poor, failure
   - Calculate accuracy score

4. LEARNING GENERATION (Daily)
   - Create AILearningEvent from each outcome
   - Identify which factors worked/failed
   - Calculate weight adjustments

5. MODEL UPDATE (Daily)
   - Process learning events
   - Update PersonalLearningWeights
   - Update NicheLearning
   - Update ConfidenceCalibration

6. IMPROVED RECOMMENDATIONS
   - Next recommendations use learned weights
   - Confidence scores calibrated
   - Niche preferences personalized
```

## Database Models Created ✅

1. **ProductPerformance** - Daily sales/revenue snapshots
   - Synced from Shopify every 6 hours
   - Tracks: orders, revenue, profit, conversion, ROAS

2. **RecommendationOutcome** - AI predictions vs reality
   - Created when recommendation accepted
   - Updated with actual performance
   - Classified: exceptional → failure

3. **AILearningEvent** - Individual learning signals
   - Generated from outcomes
   - Contains weight adjustments
   - Processed daily to update model

4. **ConfidenceCalibration** - How accurate are confidence scores
   - Tracks if 80% confidence → 80% success rate
   - Adjusts for over/under confidence

5. **NicheLearning** - Which niches work for this user
   - Success rate per niche
   - Revenue stats per niche
   - Score adjustments (+10 for fitness if user succeeds there)

6. **GlobalLearningWeights** - Baseline AI weights
7. **PersonalLearningWeights** - User-specific AI weights

## Services To Implement

### 1. SalesSyncService (ospra_os/services/sales_sync_service.py)
```python
class SalesSyncService:
    async def sync_store(store, days_back) -> Dict:
        # Fetch orders from Shopify
        # Aggregate by product + date
        # Calculate metrics (profit, margin, conversion)
        # Save to ProductPerformance

    async def sync_all_stores(user_id, days_back) -> List[Dict]:
        # Sync all connected stores

    def get_product_performance_summary(product_id, days) -> Dict:
        # Aggregate performance for product
        # Return: total orders, revenue, profit, margins
```

### 2. OutcomeService (ospra_os/services/outcome_service.py)
```python
class OutcomeService:
    def create_outcome_record(action, product) -> RecommendationOutcome:
        # When user accepts recommendation
        # Record what AI predicted

    async def evaluate_outcomes(user_id) -> List[Dict]:
        # Find outcomes ready to evaluate (>7 days)
        # Compare actual vs predicted
        # Classify outcome
        # Create learning event

    def _classify_outcome(outcome, performance) -> Tuple[str, float, float]:
        # exceptional: >150% of predicted
        # success: 100-150%
        # moderate: 50-100%
        # poor: 25-50%
        # failure: <25%
```

### 3. LearningProcessor (ospra_os/services/learning_processor.py)
```python
class LearningProcessor:
    def process_pending_events(user_id) -> Dict:
        # Process AILearningEvent records
        # Apply weight adjustments
        # Update PersonalLearningWeights

    def get_weights_for_user(user_id) -> Dict[str, float]:
        # Blend global + personal weights
        # 70% global, 30% personal

    def get_niche_adjustment(user_id, niche) -> float:
        # +/- score adjustment for niche
```

### 4. Updated ConfidenceEngine
```python
class ConfidenceEngine:
    def calculate_confidence(product_data) -> Tuple[float, Dict]:
        # Use LEARNED weights (not static)
        # Apply niche adjustments
        # Apply calibration corrections
        # Return adjusted confidence score
```

## API Endpoints To Implement

```python
POST   /api/feedback/sync
       # Trigger sales sync
       Request: {store_id?, days_back}
       Response: {stores_synced, results}

GET    /api/feedback/performance/{product_id}
       # Get product performance
       Query: days (default 30)
       Response: PerformanceSummary

GET    /api/feedback/performance
       # Get all products performance
       Response: {products: [...], total_revenue, total_profit}

POST   /api/feedback/evaluate
       # Trigger outcome evaluation
       Response: {evaluated, results}

GET    /api/feedback/outcomes
       # Get recommendation outcomes
       Query: status, limit
       Response: List[OutcomeResponse]

GET    /api/feedback/learning-stats
       # Get AI learning statistics
       Response: LearningStatsResponse {
         total_outcomes,
         success_rate,
         avg_accuracy,
         weights,
         niche_performance,
         calibration_summary
       }

POST   /api/feedback/process-learning
       # Process learning events
       Response: {processed, weight_updates}
```

## Celery Tasks To Implement

```python
@shared_task
def sync_all_stores_task(days_back=1):
    # Every 6 hours
    # Sync sales from all stores

@shared_task
def evaluate_outcomes_task():
    # Daily
    # Evaluate pending outcomes

@shared_task
def process_learning_task():
    # Daily
    # Update AI weights from learning events

@shared_task
def daily_feedback_loop():
    # Daily master task
    # 1. Sync → 2. Evaluate → 3. Learn
```

## Example Flow

```
DAY 0: AI Recommendation
----------------------
AI analyzes fitness yoga mat:
- Trend score: 85
- Historical score: 75
- Margin score: 90
- Sentiment score: 80

Weighted score (with DEFAULT weights):
= 0.25*85 + 0.25*75 + 0.25*90 + 0.25*80
= 82.5% confidence

AI predicts:
- Daily sales: 3 orders
- Monthly revenue: $450
- Margin: 40%

User accepts → RecommendationOutcome created

DAY 1-7: Performance Tracking
----------------------------
Sales sync every 6 hours:
Day 1: 2 orders, $30 revenue
Day 2: 4 orders, $60 revenue
Day 3: 3 orders, $45 revenue
...

DAY 7: Outcome Evaluation
-------------------------
Actual performance:
- Daily sales: 5 orders (predicted 3)
- Revenue: $750/month (predicted $450)
- Margin: 42% (predicted 40%)

Ratio: $750 / $450 = 1.67 = 167%

Classification: EXCEPTIONAL (>150%)
Outcome score: 100
Accuracy score: 85

Learning event created:
- lesson_type: positive_signal
- factors_validated: [margin, sentiment]
- weight_adjustments: {margin: +0.05, sentiment: +0.05}

DAY 8: Learning Processing
--------------------------
Process learning event:
- Current weights: {
    historical: 0.25,
    market: 0.25,
    margin: 0.25,  ← increase
    sentiment: 0.25 ← increase
  }

- New weights: {
    historical: 0.233,
    market: 0.233,
    margin: 0.267,  ← +0.05, then normalized
    sentiment: 0.267
  }

Update NicheLearning:
- Niche: fitness
- Success rate: 100% (1/1)
- niche_score_adjustment: +10

DAY 9: Next Recommendation
--------------------------
AI recommends another fitness product:

Base confidence: 78
+ Niche adjustment: +10
= 88% confidence (higher than before!)

Weighted with LEARNED weights:
- Margin and sentiment now weighted MORE
- Because they proved predictive for this user
```

## Next Steps

1. ✅ Create performance_models.py
2. ⏳ Create sales_sync_service.py
3. ⏳ Create outcome_service.py
4. ⏳ Create learning_processor.py
5. ⏳ Update confidence_engine.py
6. ⏳ Create feedback_routes.py
7. ⏳ Create feedback_tasks.py
8. ⏳ Register routes & models
9. ⏳ Run database migration
10. ⏳ Test end-to-end flow

## Business Value

**Before Feedback Loop:**
- AI blindly recommends products
- No way to know what actually works
- Can't improve over time
- Users don't trust recommendations

**After Feedback Loop:**
- AI learns from real sales data
- Proves its value with actual results
- Gets smarter for each user over time
- Users see "This worked for me before" confidence

**Key Metrics:**
- Show user: "AI has 78% success rate for you"
- Show user: "Fitness products: 85% success, Home décor: 45% success"
- Calibrate confidence: "When AI says 80%, it succeeds 80% of the time"
- Personalize: "AI learns YOUR specific strengths"

This transforms Ospra from a tool into an intelligent partner that
PROVES it works and gets better over time.

---

**Implementation Note:** Due to the massive scope of this feature (6+ files,
2000+ lines of code), this implementation guide outlines the architecture.
The actual services can be implemented incrementally over multiple sessions.

Priority implementation order:
1. SalesSyncService (get real data flowing)
2. OutcomeService (track predictions vs reality)
3. Learning Processor (update weights)
4. API routes (expose to frontend)
5. Celery tasks (automate)
