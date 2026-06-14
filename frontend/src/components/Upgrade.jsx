/**
 * OSPRA INTELLIGENCE - UPGRADE PAGE
 * ==================================
 *
 * Tier comparison + upsell page. This is where useRequireTier() redirects
 * when a user hits a feature above their tier (location.state.requiredTier
 * carries which tier the feature needed).
 *
 * Pricing is the Pass 4 ladder (memory/pricing.md). Rules honored here:
 *   - Annual always saves exactly 2 months.
 *   - No trials that auto-charge: Nest is free forever, paid tiers are
 *     month-to-month.
 *
 * Paid checkout: POST /api/user/upgrade returns a LemonSqueezy checkout_url
 * in production — the tier is only granted by the payment webhook, so we
 * redirect to checkout and let /billing/success poll for the grant.
 */

import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowLeft, Check, Loader2, Lock, Sparkles } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { api } from '../services/api';
import { PageLayout } from './Layout';

const TIER_ORDER = ['nest', 'flight', 'soar', 'stratosphere'];

const TIERS = [
  {
    id: 'nest',
    name: 'Nest',
    tagline: 'Try the engine, free forever',
    monthly: 0,
    yearly: null,
    features: [
      '10 products/week discovered',
      '1 connected store',
      'Support AI preview (drafts only)',
      'Community support',
    ],
  },
  {
    id: 'flight',
    name: 'Flight',
    tagline: 'Your first store, automated',
    monthly: 29,
    yearly: 290,
    features: [
      '50 products/week discovered',
      '1 connected store',
      '100 AI support replies/mo',
      'Social sentiment scoring',
    ],
  },
  {
    id: 'soar',
    name: 'Soar',
    tagline: 'The full discovery + deploy + support stack',
    monthly: 79,
    yearly: 790,
    popular: true,
    features: [
      '250 products/week discovered',
      '3 connected stores',
      '1,000 AI support replies/mo',
      'Winner-proof signals (Meta ads, TikTok Shop)',
    ],
  },
  {
    id: 'stratosphere',
    name: 'Stratosphere',
    tagline: 'Scale across your whole portfolio',
    monthly: 199,
    yearly: 1990,
    features: [
      '1,500 products/week discovered',
      '10 connected stores',
      'Unlimited AI support replies',
      'Tenant-fine-tuned support voice',
    ],
  },
];

function TierCard({ tier, interval, currentTier, upgrading, onUpgrade, highlight }) {
  const currentIdx = TIER_ORDER.indexOf(currentTier);
  const tierIdx = TIER_ORDER.indexOf(tier.id);
  const isCurrent = tier.id === currentTier;
  const isDowngrade = tierIdx < currentIdx;
  const isUpgrading = upgrading === tier.id;
  const price = interval === 'yearly' && tier.yearly !== null ? tier.yearly : tier.monthly;
  const suffix = tier.monthly === 0 ? '' : interval === 'yearly' && tier.yearly !== null ? '/yr' : '/mo';

  return (
    <div
      className={`relative flex flex-col p-6 rounded-2xl border backdrop-blur-xl transition-all ${
        highlight
          ? 'bg-purple-500/10 border-purple-400/50 ring-2 ring-purple-400/40'
          : tier.popular
          ? 'bg-white/5 border-purple-500/40'
          : 'bg-white/5 border-white/10'
      }`}
    >
      {tier.popular && !highlight && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 text-xs font-medium text-white bg-gradient-to-r from-purple-500 to-cyan-500 rounded-full">
          Most popular
        </span>
      )}
      {highlight && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 text-xs font-medium text-white bg-purple-500 rounded-full flex items-center gap-1">
          <Lock className="w-3 h-3" /> Required for this feature
        </span>
      )}

      <h3 className="text-xl font-bold text-white">{tier.name}</h3>
      <p className="text-white/50 text-sm mt-1 min-h-[40px]">{tier.tagline}</p>

      <div className="mt-4 mb-6">
        <span className="text-4xl font-bold text-white">${price}</span>
        <span className="text-white/40 ml-1">{suffix}</span>
        {interval === 'yearly' && tier.yearly !== null && (
          <p className="text-cyan-400/80 text-xs mt-1">2 months free vs monthly</p>
        )}
        {tier.monthly === 0 && (
          <p className="text-white/40 text-xs mt-1">Free forever — no card needed</p>
        )}
      </div>

      <ul className="space-y-2.5 flex-1 mb-6">
        {tier.features.map((feature) => (
          <li key={feature} className="flex items-start gap-2 text-sm text-white/70">
            <Check className="w-4 h-4 text-purple-400 mt-0.5 shrink-0" />
            {feature}
          </li>
        ))}
      </ul>

      {isCurrent ? (
        <div className="w-full py-2.5 rounded-xl border border-purple-500/30 bg-purple-500/20 text-purple-300 text-center text-sm font-medium">
          Current plan
        </div>
      ) : isDowngrade ? (
        <div className="w-full py-2.5 rounded-xl border border-white/10 text-white/30 text-center text-sm">
          Included in your plan
        </div>
      ) : (
        <button
          onClick={() => onUpgrade(tier.id)}
          disabled={!!upgrading}
          className={`w-full py-2.5 rounded-xl text-sm font-medium transition-all flex items-center justify-center gap-2 ${
            tier.popular || highlight
              ? 'bg-gradient-to-r from-purple-500 to-cyan-500 text-white hover:opacity-90'
              : 'bg-white/10 text-white border border-white/10 hover:bg-white/20'
          } ${upgrading && !isUpgrading ? 'opacity-50' : ''}`}
        >
          {isUpgrading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {isUpgrading ? 'Opening checkout…' : `Upgrade to ${tier.name}`}
        </button>
      )}
    </div>
  );
}

export default function Upgrade() {
  const { user } = useAuth();
  const location = useLocation();
  // Named billingInterval so the setter doesn't shadow window.setInterval.
  const [billingInterval, setBillingInterval] = useState('monthly');
  const [upgrading, setUpgrading] = useState(null);
  const [error, setError] = useState(null);

  // Set when useRequireTier bounced the user here from a gated feature.
  const requiredTier = location.state?.requiredTier;
  const currentTier = user?.tier || 'nest';

  const handleUpgrade = async (tierId) => {
    setError(null);
    setUpgrading(tierId);
    try {
      const response = await api.upgradeTier(tierId, billingInterval);
      if (response.checkout_url) {
        window.location.assign(response.checkout_url);
        return; // leaving the page — keep the spinner
      }
      if (response.success) {
        // Dev/free path: tier changed directly, reload to refresh the JWT-backed UI.
        window.location.reload();
        return;
      }
      setError(response.message || 'Could not start checkout. Please try again.');
    } catch (err) {
      setError(err.message || 'Could not start checkout. Please try again.');
    }
    setUpgrading(null);
  };

  return (
    <PageLayout>
      <div className="relative max-w-6xl mx-auto">
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-2 text-white/50 hover:text-white text-sm mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to dashboard
        </Link>

        {requiredTier && (
          <div className="mb-8 p-4 rounded-xl bg-purple-500/10 border border-purple-400/30 text-purple-200 text-sm flex items-center gap-2">
            <Lock className="w-4 h-4 shrink-0" />
            That feature needs the{' '}
            <span className="font-semibold capitalize">{requiredTier}</span> plan or higher —
            you&apos;re on <span className="font-semibold capitalize">{currentTier}</span>.
          </div>
        )}

        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-white mb-3">Choose your plan</h1>
          <p className="text-white/50 max-w-xl mx-auto">
            Every plan includes AI product discovery, social sentiment scoring, and Shopify
            deployment. Upgrade or cancel anytime — no auto-charging trials, ever.
          </p>

          {/* Billing interval toggle */}
          <div className="inline-flex items-center mt-6 p-1 rounded-xl bg-white/5 border border-white/10">
            {['monthly', 'yearly'].map((option) => (
              <button
                key={option}
                onClick={() => setBillingInterval(option)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all capitalize ${
                  billingInterval === option ? 'bg-purple-500 text-white' : 'text-white/50 hover:text-white'
                }`}
              >
                {option}
                {option === 'yearly' && <span className="ml-1.5 text-xs opacity-80">2 mo free</span>}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-400/30 text-red-200 text-sm text-center">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {TIERS.map((tier) => (
            <TierCard
              key={tier.id}
              tier={tier}
              interval={billingInterval}
              currentTier={currentTier}
              upgrading={upgrading}
              onUpgrade={handleUpgrade}
              highlight={tier.id === requiredTier}
            />
          ))}
        </div>

        <p className="text-center text-white/30 text-xs mt-10">
          Payments are processed securely by LemonSqueezy. Your plan activates the moment
          payment is confirmed. Annual plans always save exactly 2 months.
        </p>
      </div>
    </PageLayout>
  );
}
