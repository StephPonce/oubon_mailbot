import { useState, useEffect } from 'react';
import { 
  CreditCard, 
  Check, 
  ArrowRight, 
  Zap, 
  Shield, 
  Clock,
  ExternalLink,
  ChevronRight,
  Egg,
  Plane,
  Bird,
  Rocket
} from 'lucide-react';
import { motion } from 'framer-motion';
import { subscriptionAPI, usageAPI, paymentsAPI, UsageDashboard } from '../lib/api';
import { UsageMeter, TierBadge, UpgradePrompt } from '../components/subscription';

interface TierInfo {
  tier: string;
  tier_info: {
    name: string;
    price_monthly: number;
    price_display: string;
    product_freshness: string;
    products_per_week: number | string;
    store_limit: number | string;
    features: string[];
  };
}

interface PricingTier {
  tier: string;
  name: string;
  price_monthly: number;
  price_display: string;
  tagline: string;
  features: string[];
}

const tierIcons = {
  nest: Egg,
  flight: Plane,
  soar: Bird,
  stratosphere: Rocket,
};

const tierGradients = {
  nest: 'from-amber-500 to-amber-600',
  flight: 'from-sky-400 to-sky-600',
  soar: 'from-blue-500 to-indigo-600',
  stratosphere: 'from-purple-500 to-violet-600',
};

export default function SubscriptionPage() {
  const [currentTier, setCurrentTier] = useState<TierInfo | null>(null);
  const [usage, setUsage] = useState<UsageDashboard | null>(null);
  const [pricing, setPricing] = useState<PricingTier[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [upgradeLoading, setUpgradeLoading] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [tierData, usageData, pricingData] = await Promise.all([
          subscriptionAPI.getCurrentTier(1),
          usageAPI.getDashboard(1),
          subscriptionAPI.getPricing(),
        ]);
        
        setCurrentTier(tierData);
        setUsage(usageData);
        setPricing(pricingData.tiers || []);
      } catch (error) {
        console.error('Failed to fetch subscription data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleUpgrade = async (tierId: string) => {
    setUpgradeLoading(tierId);
    try {
      const result = await paymentsAPI.getCheckoutUrl(tierId);
      if (result.checkout_url) {
        window.open(result.checkout_url, '_blank');
      }
    } catch (error) {
      console.error('Failed to get checkout URL:', error);
      // Fallback URLs
      const urls: Record<string, string> = {
        flight: 'https://ospra.lemonsqueezy.com/buy/7f817d94-cf31-4ab6-9ff4-54de583f7920',
        soar: 'https://ospra.lemonsqueezy.com/buy/e1f7dd88-9c08-4486-ac77-be77af8bf976',
        stratosphere: 'https://ospra.lemonsqueezy.com/buy/5d7d273d-f3df-470a-8827-40c3cd975cfc',
      };
      if (urls[tierId]) {
        window.open(urls[tierId], '_blank');
      }
    } finally {
      setUpgradeLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/3" />
          <div className="h-48 bg-gray-200 rounded-xl" />
          <div className="h-64 bg-gray-200 rounded-xl" />
        </div>
      </div>
    );
  }

  const tier = currentTier?.tier || 'nest';
  const TierIcon = tierIcons[tier as keyof typeof tierIcons] || Egg;
  const gradient = tierGradients[tier as keyof typeof tierGradients] || tierGradients.nest;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-primary">Subscription & Billing</h1>
        <p className="text-tertiary mt-1">Manage your plan, usage, and billing settings</p>
      </div>

      {/* Current Plan Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className={`bg-gradient-to-r ${gradient} rounded-2xl p-6 text-white relative overflow-hidden`}
      >
        {/* Background decoration */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/10 rounded-full translate-y-1/2 -translate-x-1/2" />
        
        <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 bg-white/20 rounded-2xl flex items-center justify-center">
              <TierIcon className="w-8 h-8" />
            </div>
            <div>
              <div className="text-sm text-white/70">Current Plan</div>
              <h2 className="text-3xl font-bold">{currentTier?.tier_info?.name || 'Nest'}</h2>
              <div className="text-lg text-white/90 mt-1">
                {currentTier?.tier_info?.price_display || 'Free'}
              </div>
            </div>
          </div>
          
          <div className="flex flex-col sm:flex-row gap-3">
            {tier !== 'stratosphere' && (
              <button
                onClick={() => setShowUpgradeModal(true)}
                className="px-6 py-3 bg-white text-primary font-semibold rounded-xl hover:bg-gray-100 transition flex items-center justify-center gap-2"
              >
                <Zap className="w-5 h-5" />
                Upgrade Plan
              </button>
            )}
            <button
              className="px-6 py-3 bg-white/20 text-white font-semibold rounded-xl hover:bg-white/30 transition flex items-center justify-center gap-2"
            >
              <ExternalLink className="w-5 h-5" />
              Manage Billing
            </button>
          </div>
        </div>
        
        {/* Plan benefits */}
        <div className="relative mt-6 pt-6 border-t border-white/20 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div className="text-white/70 text-sm">Product Freshness</div>
            <div className="font-semibold">{currentTier?.tier_info?.product_freshness || '30+ days'}</div>
          </div>
          <div>
            <div className="text-white/70 text-sm">Products/Week</div>
            <div className="font-semibold">{currentTier?.tier_info?.products_per_week || 5}</div>
          </div>
          <div>
            <div className="text-white/70 text-sm">Store Limit</div>
            <div className="font-semibold">{currentTier?.tier_info?.store_limit || 1}</div>
          </div>
          <div>
            <div className="text-white/70 text-sm">AI Analysis</div>
            <div className="font-semibold">{tier === 'nest' ? 'Basic' : 'Full'}</div>
          </div>
        </div>
      </motion.div>

      {/* Usage Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
              <Clock className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-primary">Usage This Period</h3>
              <p className="text-sm text-tertiary">Track your activity against your plan limits</p>
            </div>
          </div>
        </div>
        
        <UsageMeter userId={1} />
      </motion.div>

      {/* Pricing Comparison */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h3 className="text-xl font-semibold text-primary mb-4">Compare Plans</h3>
        
        <div className="grid md:grid-cols-4 gap-4">
          {pricing.map((plan, index) => {
            const isCurrentPlan = plan.tier === tier;
            const PlanIcon = tierIcons[plan.tier as keyof typeof tierIcons] || Egg;
            const planGradient = tierGradients[plan.tier as keyof typeof tierGradients] || tierGradients.nest;
            
            return (
              <motion.div
                key={plan.tier}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
                className={`
                  relative bg-white rounded-xl border-2 p-5 transition-all
                  ${isCurrentPlan 
                    ? 'border-blue-500 shadow-lg shadow-blue-500/10' 
                    : 'border-white/10 hover:border-white/10'
                  }
                `}
              >
                {isCurrentPlan && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-cyan-500/100 text-white text-xs font-bold px-3 py-1 rounded-full">
                    CURRENT
                  </div>
                )}
                
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${planGradient} flex items-center justify-center mb-4`}>
                  <PlanIcon className="w-6 h-6 text-white" />
                </div>
                
                <h4 className="text-lg font-bold text-primary">{plan.name}</h4>
                <p className="text-sm text-tertiary mb-2">{plan.tagline}</p>
                <div className="text-2xl font-bold text-primary mb-4">{plan.price_display}</div>
                
                <ul className="space-y-2 mb-6">
                  {plan.features?.slice(0, 4).map((feature, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-secondary">
                      <Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                
                {!isCurrentPlan && (
                  <button
                    onClick={() => handleUpgrade(plan.tier)}
                    disabled={upgradeLoading === plan.tier}
                    className={`
                      w-full py-2.5 rounded-lg font-medium flex items-center justify-center gap-2 transition
                      ${plan.tier === 'soar' 
                        ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:shadow-lg'
                        : 'bg-gray-100 text-secondary hover:bg-gray-200'
                      }
                    `}
                  >
                    {upgradeLoading === plan.tier ? (
                      <span className="animate-spin">⏳</span>
                    ) : (
                      <>
                        {plan.tier === 'nest' ? 'Downgrade' : 'Upgrade'}
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                )}
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      {/* Billing History / Info */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6"
      >
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center">
            <CreditCard className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-primary">Billing Information</h3>
            <p className="text-sm text-tertiary">Manage your payment methods and view history</p>
          </div>
        </div>
        
        <div className="space-y-4">
          <button className="w-full flex items-center justify-between p-4   rounded-xl hover:bg-gray-100 transition">
            <div className="flex items-center gap-3">
              <Shield className="w-5 h-5 text-tertiary" />
              <span className="font-medium text-secondary">Update Payment Method</span>
            </div>
            <ChevronRight className="w-5 h-5 text-tertiary" />
          </button>
          
          <button className="w-full flex items-center justify-between p-4   rounded-xl hover:bg-gray-100 transition">
            <div className="flex items-center gap-3">
              <CreditCard className="w-5 h-5 text-tertiary" />
              <span className="font-medium text-secondary">View Billing History</span>
            </div>
            <ChevronRight className="w-5 h-5 text-tertiary" />
          </button>
        </div>
        
        <div className="mt-6 p-4 bg-cyan-500/10 rounded-xl">
          <div className="flex items-center gap-2 text-sm text-cyan-400">
            <Shield className="w-4 h-4" />
            <span>Payments are securely processed by LemonSqueezy</span>
          </div>
        </div>
      </motion.div>

      {/* Upgrade Modal */}
      <UpgradePrompt
        isOpen={showUpgradeModal}
        onClose={() => setShowUpgradeModal(false)}
        currentTier={tier}
        userId={1}
      />
    </div>
  );
}
