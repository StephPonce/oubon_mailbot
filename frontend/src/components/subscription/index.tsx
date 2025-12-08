import { useState, useEffect } from 'react';
import { Crown, Zap, Star, ChevronRight, X, Check, Loader2 } from 'lucide-react';

// Tier Badge Compact - Used in Sidebar
export function TierBadgeCompact({ userId, onClick }: { userId: number; onClick?: () => void }) {
  const tier = 'stratosphere'; // For demo, user has top tier
  
  const tierConfig = {
    nest: { label: 'Nest', color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/20' },
    flight: { label: 'Flight', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
    soar: { label: 'Soar', color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
    stratosphere: { label: 'Stratosphere', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
  };

  const config = tierConfig[tier as keyof typeof tierConfig] || tierConfig.nest;

  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center gap-3 p-3 rounded-xl ${config.bg} border ${config.border} hover:opacity-80 transition-all`}
    >
      <Crown className={`w-4 h-4 ${config.color}`} />
      <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>
      <ChevronRight className="w-4 h-4 text-white/30 ml-auto" />
    </button>
  );
}

// Usage Meter Mini - Used in Sidebar
export function UsageMeterMini({ userId }: { userId: number }) {
  const usage = {
    searches: { used: 247, limit: -1 }, // -1 = unlimited
    deploys: { used: 12, limit: -1 },
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="text-white/40">AI Searches</span>
        <span className="text-white/60">
          {usage.searches.limit === -1 ? 'Unlimited' : `${usage.searches.used}/${usage.searches.limit}`}
        </span>
      </div>
      <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div 
          className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"
          style={{ width: usage.searches.limit === -1 ? '100%' : `${(usage.searches.used / usage.searches.limit) * 100}%` }}
        />
      </div>
    </div>
  );
}

// Upgrade Prompt Modal
export function UpgradePrompt({ 
  isOpen, 
  onClose, 
  userId 
}: { 
  isOpen: boolean; 
  onClose: () => void; 
  userId: number;
}) {
  if (!isOpen) return null;

  const plans = [
    {
      name: 'Flight',
      price: '$29',
      period: '/month',
      features: ['50 AI searches/day', '10 product deploys', 'Basic analytics', 'Email support'],
      color: 'blue',
      popular: false,
    },
    {
      name: 'Soar',
      price: '$79',
      period: '/month',
      features: ['200 AI searches/day', 'Unlimited deploys', 'Advanced analytics', 'Priority support', 'A/B testing'],
      color: 'purple',
      popular: true,
    },
    {
      name: 'Stratosphere',
      price: '$199',
      period: '/month',
      features: ['Unlimited everything', 'White-glove onboarding', 'Dedicated success manager', 'Custom integrations', 'API access'],
      color: 'amber',
      popular: false,
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      
      <div className="relative w-full max-w-4xl glass-card-static p-6 max-h-[90vh] overflow-y-auto">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-white/5 text-white/50"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center mb-8">
          <h2 className="text-2xl font-semibold text-white mb-2">Upgrade Your Plan</h2>
          <p className="text-sm text-white/50">Unlock more features and grow your business faster</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {plans.map((plan) => (
            <div 
              key={plan.name}
              className={`relative p-5 rounded-xl border ${
                plan.popular 
                  ? 'bg-gradient-to-br from-purple-500/10 to-pink-500/5 border-purple-500/30' 
                  : 'bg-white/5 border-white/10'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-purple-500 text-white text-xs font-medium">
                  Most Popular
                </div>
              )}
              
              <h3 className={`text-lg font-semibold text-${plan.color}-400 mb-1`}>{plan.name}</h3>
              <div className="flex items-baseline gap-1 mb-4">
                <span className="text-3xl font-bold text-white">{plan.price}</span>
                <span className="text-sm text-white/40">{plan.period}</span>
              </div>

              <ul className="space-y-2 mb-6">
                {plan.features.map((feature, index) => (
                  <li key={index} className="flex items-center gap-2 text-sm text-white/70">
                    <Check className={`w-4 h-4 text-${plan.color}-400`} />
                    {feature}
                  </li>
                ))}
              </ul>

              <button className={`w-full py-2.5 rounded-lg font-medium text-sm transition-all ${
                plan.popular
                  ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:opacity-90'
                  : 'bg-white/10 text-white hover:bg-white/20'
              }`}>
                {plan.name === 'Stratosphere' ? 'Contact Sales' : 'Upgrade Now'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default { TierBadgeCompact, UsageMeterMini, UpgradePrompt };
