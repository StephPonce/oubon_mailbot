import { useState, useEffect } from 'react';
import { X, Rocket, Zap, Check, ArrowRight, Sparkles } from 'lucide-react';
import { subscriptionAPI, paymentsAPI } from '../../lib/api';

interface UpgradePromptProps {
  isOpen: boolean;
  onClose: () => void;
  currentTier?: string;
  triggeredBy?: string;
  userId?: number;
}

interface TierOption {
  id: string;
  name: string;
  price: string;
  description: string;
  features: string[];
  highlight?: boolean;
  gradient: string;
}

const tierOptions: TierOption[] = [
  {
    id: 'flight',
    name: 'Flight',
    price: '$29/mo',
    description: 'Start selling smarter',
    gradient: 'from-sky-400 to-sky-600',
    features: [
      'Growth products (14+ days old)',
      '25 products/week',
      'Full AI analysis',
      'Basic saturation alerts',
    ],
  },
  {
    id: 'soar',
    name: 'Soar',
    price: '$79/mo',
    description: 'Run your business, not just a store',
    gradient: 'from-blue-500 to-indigo-600',
    highlight: true,
    features: [
      'Early-spike products (7+ days)',
      'Unlimited products',
      '5 stores',
      'Full email automation',
      'Personal AI learning',
      'API access',
    ],
  },
  {
    id: 'stratosphere',
    name: 'Stratosphere',
    price: '$199/mo',
    description: 'Your AI-powered operations team',
    gradient: 'from-purple-500 to-violet-600',
    features: [
      'Day-zero products',
      'Unlimited stores',
      'Custom AI for your niche',
      'Dedicated success manager',
      'Team members (3)',
      'Priority support',
    ],
  },
];

export function UpgradePrompt({ 
  isOpen, 
  onClose, 
  currentTier = 'nest',
  triggeredBy,
  userId = 1 
}: UpgradePromptProps) {
  const [loading, setLoading] = useState<string | null>(null);
  const [selectedTier, setSelectedTier] = useState<string | null>(null);

  // Filter out current and lower tiers
  const availableTiers = tierOptions.filter(t => {
    const tierOrder = ['nest', 'flight', 'soar', 'stratosphere'];
    return tierOrder.indexOf(t.id) > tierOrder.indexOf(currentTier);
  });

  const handleUpgrade = async (tierId: string) => {
    setLoading(tierId);
    try {
      const result = await paymentsAPI.getCheckoutUrl(tierId);
      if (result.checkout_url) {
        window.open(result.checkout_url, '_blank');
      }
    } catch (error) {
      console.error('Failed to get checkout URL:', error);
      // Fallback to direct LemonSqueezy links
      const urls: Record<string, string> = {
        flight: 'https://ospra.lemonsqueezy.com/buy/7f817d94-cf31-4ab6-9ff4-54de583f7920',
        soar: 'https://ospra.lemonsqueezy.com/buy/e1f7dd88-9c08-4486-ac77-be77af8bf976',
        stratosphere: 'https://ospra.lemonsqueezy.com/buy/5d7d273d-f3df-470a-8827-40c3cd975cfc',
      };
      if (urls[tierId]) {
        window.open(urls[tierId], '_blank');
      }
    } finally {
      setLoading(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-purple-600 text-white p-6 rounded-t-2xl">
          <button 
            onClick={onClose}
            className="absolute top-4 right-4 p-2 hover:bg-white/20 rounded-full transition"
          >
            <X className="w-5 h-5" />
          </button>
          
          <div className="flex items-center gap-3 mb-2">
            <Sparkles className="w-8 h-8" />
            <h2 className="text-2xl font-bold">Unlock More Power</h2>
          </div>
          
          {triggeredBy && (
            <p className="text-blue-100">
              You've reached your {triggeredBy} limit. Upgrade to continue growing.
            </p>
          )}
        </div>

        {/* Tier Cards */}
        <div className="p-6">
          <div className="grid md:grid-cols-3 gap-4">
            {availableTiers.map((tier) => (
              <div
                key={tier.id}
                className={`
                  relative rounded-xl border-2 p-5 transition-all cursor-pointer
                  ${tier.highlight 
                    ? 'border-blue-500 shadow-lg shadow-blue-500/20 scale-105' 
                    : 'border-white/10 hover:border-white/10'
                  }
                  ${selectedTier === tier.id ? 'ring-2 ring-blue-500' : ''}
                `}
                onClick={() => setSelectedTier(tier.id)}
              >
                {tier.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-cyan-500/100 text-white text-xs font-bold px-3 py-1 rounded-full">
                    MOST POPULAR
                  </div>
                )}
                
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${tier.gradient} flex items-center justify-center mb-4`}>
                  <Rocket className="w-6 h-6 text-white" />
                </div>
                
                <h3 className="text-xl font-bold text-primary">{tier.name}</h3>
                <p className="text-sm text-tertiary mb-2">{tier.description}</p>
                <div className="text-2xl font-bold text-primary mb-4">{tier.price}</div>
                
                <ul className="space-y-2 mb-6">
                  {tier.features.map((feature, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-secondary">
                      <Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleUpgrade(tier.id);
                  }}
                  disabled={loading === tier.id}
                  className={`
                    w-full py-3 rounded-xl font-semibold flex items-center justify-center gap-2 transition
                    ${tier.highlight
                      ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:shadow-lg'
                      : 'bg-gray-100 text-primary hover:bg-gray-200'
                    }
                    ${loading === tier.id ? 'opacity-50 cursor-not-allowed' : ''}
                  `}
                >
                  {loading === tier.id ? (
                    <span className="animate-spin">⏳</span>
                  ) : (
                    <>
                      Upgrade to {tier.name}
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
            ))}
          </div>
          
          {/* Benefits */}
          <div className="mt-8 p-4   rounded-xl">
            <div className="flex items-center gap-2 text-sm text-secondary">
              <Zap className="w-4 h-4 text-yellow-500" />
              <span>All plans include 14-day money-back guarantee</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Inline banner version for when approaching limits
export function UpgradeBanner({ 
  message, 
  tier = 'soar',
  onUpgrade 
}: { 
  message: string; 
  tier?: string;
  onUpgrade?: () => void;
}) {
  return (
    <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center">
          <Zap className="w-5 h-5 text-amber-600" />
        </div>
        <div>
          <p className="font-medium text-primary">{message}</p>
          <p className="text-sm text-tertiary">Upgrade to unlock more</p>
        </div>
      </div>
      <button
        onClick={onUpgrade}
        className="px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-500 text-white font-medium rounded-lg hover:shadow-lg transition flex items-center gap-2"
      >
        Upgrade
        <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  );
}

export default UpgradePrompt;
