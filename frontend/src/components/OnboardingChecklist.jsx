/**
 * OSPRA INTELLIGENCE - FIRST-RUN ONBOARDING CHECKLIST (task #51e)
 * ================================================================
 *
 * Three steps to first value, shown on the dashboard until all are done:
 *   1. Connect Shopify   → authoritative: /api/shopify/oauth/status
 *   2. Run first discovery → a successful Products load writes the
 *      ospra_products_v1:* localStorage cache; presence = ran at least once
 *   3. Deploy first product → authoritative: /api/dashboard/v2/deployments
 *
 * These mirror the server-side PostHog funnel events (shopify_connected,
 * first_discovery_run, first_product_deployed) — the checklist derives the
 * same milestones from app state so it works without querying PostHog.
 *
 * Auto-hides once everything is complete; manually dismissible before that
 * (persisted per-browser).
 */

import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Check, ListChecks, Package, Rocket, Store, X } from 'lucide-react';
import { api } from '../services/api';

const DISMISS_KEY = 'ospra_onboarding_dismissed';

function hasDiscoveryCache() {
  try {
    for (let i = 0; i < localStorage.length; i++) {
      if (localStorage.key(i)?.startsWith('ospra_products_v1:')) return true;
    }
  } catch {
    // localStorage unavailable (private mode) — treat as not done
  }
  return false;
}

export function OnboardingChecklist() {
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(DISMISS_KEY) === 'true'
  );
  const [steps, setSteps] = useState(null); // null until checks resolve

  useEffect(() => {
    if (dismissed) return;
    let cancelled = false;

    (async () => {
      // Each check is independent; a failed check counts as "not done yet"
      // rather than blocking the others.
      const [shopify, deployments] = await Promise.all([
        api.getShopifyStores().catch(() => ({ connected: false })),
        api.getDeployments().catch(() => ({ total: 0 })),
      ]);
      if (cancelled) return;
      setSteps([
        {
          id: 'shopify',
          label: 'Connect your Shopify store',
          description: 'Link your store so discovered products can deploy in one click.',
          to: '/settings/stores',
          icon: Store,
          done: !!shopify?.connected,
        },
        {
          id: 'discovery',
          label: 'Run your first discovery',
          description: 'Let the engine surface winning products for your niche.',
          to: '/products',
          icon: Package,
          done: hasDiscoveryCache(),
        },
        {
          id: 'deploy',
          label: 'Deploy your first product',
          description: 'Push a graded winner to your store with AI copy.',
          to: '/products',
          icon: Rocket,
          done: (deployments?.total || 0) > 0,
        },
      ]);
    })();

    return () => {
      cancelled = true;
    };
  }, [dismissed]);

  if (dismissed || !steps) return null;

  const doneCount = steps.filter((s) => s.done).length;
  if (doneCount === steps.length) return null; // fully onboarded — vanish

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, 'true');
    setDismissed(true);
  };

  return (
    <div className="mb-8 p-6 rounded-2xl border border-purple-500/30 bg-gradient-to-br from-purple-500/10 to-cyan-500/5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <ListChecks className="w-5 h-5 text-purple-400" />
          <h2 className="text-lg font-semibold text-white">Get set up</h2>
          <span className="text-white/40 text-sm">{doneCount} of {steps.length} done</span>
        </div>
        <button
          onClick={dismiss}
          className="text-white/30 hover:text-white transition-colors"
          aria-label="Dismiss checklist"
          title="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 rounded-full bg-white/10 mb-5 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-purple-500 to-cyan-500 transition-all duration-500"
          style={{ width: `${(doneCount / steps.length) * 100}%` }}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {steps.map((step) => (
          <Link
            key={step.id}
            to={step.to}
            className={`group p-4 rounded-xl border transition-all ${
              step.done
                ? 'bg-emerald-500/5 border-emerald-400/20 cursor-default'
                : 'bg-white/5 border-white/10 hover:border-purple-400/40 hover:bg-white/10'
            }`}
            onClick={(e) => step.done && e.preventDefault()}
          >
            <div className="flex items-center gap-2 mb-2">
              {step.done ? (
                <span className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center">
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                </span>
              ) : (
                <span className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center">
                  <step.icon className="w-3.5 h-3.5 text-purple-400" />
                </span>
              )}
              <span className={`text-sm font-medium ${step.done ? 'text-white/50 line-through' : 'text-white'}`}>
                {step.label}
              </span>
            </div>
            <p className="text-white/40 text-xs leading-relaxed">{step.description}</p>
            {!step.done && (
              <span className="inline-flex items-center gap-1 text-purple-400 text-xs mt-2 group-hover:gap-2 transition-all">
                Start <ArrowRight className="w-3 h-3" />
              </span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}

export default OnboardingChecklist;
