# Model Audit Report

Total models: **27**

## Models by Category

### Action (1 models)

- **AutoPilotLog** (line 1597)
  - Relationships: User, Action

### Ad (1 models)

- **AdCampaign** (line 603)

### Core (4 models)

- **AIUsage** (line 726)
  - Relationships: User
- **Niche** (line 1328)
  - Relationships: NicheSnapshot
- **NicheSnapshot** (line 1361)
  - Relationships: Niche
- **RankingHistory** (line 1292)
  - Relationships: Product

### Email (5 models)

- **Email** (line 867)
  - Relationships: User, UserEmailAccount
- **EmailAutomationRule** (line 934)
- **EmailFollowup** (line 1637)
- **EmailLabel** (line 1008)
- **EmailTemplate** (line 974)

### Product (7 models)

- **ABTestVariant** (line 1496)
  - Relationships: ABTest, ABTestEvent, ABTestAssignment
- **Product** (line 345)
  - Relationships: Store, ProductDeployment
- **ProductDeployment** (line 432)
  - Relationships: Product, Store
- **ProductIntelligence** (line 1270)
- **ProductSaturation** (line 481)
  - Relationships: UserProductRecommendation
- **ProductSnapshot** (line 1256)
- **ProductVelocity** (line 560)
  - Relationships: ProductSaturation

### Store (2 models)

- **CrossStoreLearning** (line 265)
  - Relationships: Store, Store, Product
- **Store** (line 201)
  - Relationships: User, Product, ProductDeployment, Action, CrossStoreLearning, CrossStoreLearning

### Testing (3 models)

- **ABTest** (line 1446)
  - Relationships: ABTestVariant, ABTestEvent, ABTestAssignment
- **ABTestAssignment** (line 1566)
  - Relationships: ABTest, ABTestVariant
- **ABTestEvent** (line 1532)
  - Relationships: ABTest, ABTestVariant

### User (4 models)

- **User** (line 150)
  - Relationships: Store, UserSettings, AIUsage, UserProductRecommendation, UserEmailAccount, Email, Action
- **UserEmailAccount** (line 827)
  - Relationships: User, Email
- **UserProductRecommendation** (line 520)
  - Relationships: User, ProductSaturation
- **UserSettings** (line 760)
  - Relationships: User

## Relationship Dependencies

```
User -> Store, UserSettings, AIUsage, UserProductRecommendation, UserEmailAccount, Email, Action
Store -> User, Product, ProductDeployment, Action, CrossStoreLearning, CrossStoreLearning
CrossStoreLearning -> Store, Store, Product
Product -> Store, ProductDeployment
ProductDeployment -> Product, Store
ProductSaturation -> UserProductRecommendation
UserProductRecommendation -> User, ProductSaturation
ProductVelocity -> ProductSaturation
AIUsage -> User
UserSettings -> User
UserEmailAccount -> User, Email
Email -> User, UserEmailAccount
RankingHistory -> Product
Niche -> NicheSnapshot
NicheSnapshot -> Niche
ABTest -> ABTestVariant, ABTestEvent, ABTestAssignment
ABTestVariant -> ABTest, ABTestEvent, ABTestAssignment
ABTestEvent -> ABTest, ABTestVariant
ABTestAssignment -> ABTest, ABTestVariant
AutoPilotLog -> User, Action
```

## Suggested File Split

- **actions_models.py**: AutoPilotLog
- **advertising_models.py**: AdCampaign
- **models.py**: AIUsage, RankingHistory, Niche, NicheSnapshot
- **email_models.py**: Email, EmailAutomationRule, EmailTemplate, EmailLabel, EmailFollowup
- **product_models.py**: Product, ProductDeployment, ProductSaturation, ProductVelocity, ProductSnapshot, ProductIntelligence, ABTestVariant
- **store_models.py**: Store, CrossStoreLearning
- **testing_models.py**: ABTest, ABTestEvent, ABTestAssignment
- **user_models.py**: User, UserProductRecommendation, UserSettings, UserEmailAccount