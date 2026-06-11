/**
 * OSPRA INTELLIGENCE - BILLING SUCCESS PAGE
 * ==========================================
 *
 * LemonSqueezy redirects here after checkout. The tier is granted by the
 * payment WEBHOOK (server-to-server), not by this redirect — so there's a
 * window where the user has paid but the database hasn't flipped yet.
 *
 * This page polls /api/auth/me until the server-side tier changes, then
 * rotates the access token (the tier claim lives in the JWT — without a
 * refresh, hasTier() keeps reading the old tier) and celebrates.
 */

import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Clock, Loader2, Rocket } from 'lucide-react';
import { authService } from '../services/auth';

const POLL_INTERVAL_MS = 3000;
const MAX_POLLS = 60; // ~3 minutes — webhooks normally land within seconds

export default function BillingSuccess() {
  // 'waiting' | 'granted' | 'timeout'
  const [status, setStatus] = useState('waiting');
  const [grantedTier, setGrantedTier] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const startingTier = useRef(authService.getTier());
  const stopped = useRef(false);

  useEffect(() => {
    stopped.current = false;

    const poll = async (n) => {
      if (stopped.current) return;
      if (n >= MAX_POLLS) {
        setStatus('timeout');
        return;
      }
      setAttempt(n);

      const result = await authService.refreshUser();
      const serverTier = result?.tier;

      if (serverTier && serverTier !== startingTier.current) {
        // Webhook landed. Rotate the JWT so the tier claim (which gates the
        // whole UI via hasTier) reflects the new plan.
        try {
          await authService.refreshAccessToken();
        } catch (e) {
          // Token rotation failing is non-fatal — the tier IS granted server-
          // side; the UI catches up on the next natural refresh/login.
          console.debug('Post-upgrade token refresh failed:', e.message);
        }
        setGrantedTier(serverTier);
        setStatus('granted');
        return;
      }

      setTimeout(() => poll(n + 1), POLL_INTERVAL_MS);
    };

    poll(0);
    return () => {
      stopped.current = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-6">
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
      </div>

      <div className="relative max-w-md w-full backdrop-blur-xl bg-black/40 border border-white/10 rounded-2xl p-8 text-center">
        {status === 'waiting' && (
          <>
            <Loader2 className="w-12 h-12 text-purple-400 animate-spin mx-auto mb-5" />
            <h1 className="text-2xl font-bold text-white mb-2">Confirming your payment…</h1>
            <p className="text-white/50 text-sm">
              Thanks for upgrading! We&apos;re waiting for the payment confirmation — this
              usually takes a few seconds.
            </p>
            {attempt > 10 && (
              <p className="text-white/30 text-xs mt-4">
                Still working… payment processors occasionally take a minute.
              </p>
            )}
          </>
        )}

        {status === 'granted' && (
          <>
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-5" />
            <h1 className="text-2xl font-bold text-white mb-2">
              Welcome to <span className="capitalize">{grantedTier}</span>!
            </h1>
            <p className="text-white/50 text-sm mb-6">
              Your plan is active. Everything you just unlocked is live right now.
            </p>
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-cyan-500 text-white text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <Rocket className="w-4 h-4" /> Launch dashboard
            </Link>
          </>
        )}

        {status === 'timeout' && (
          <>
            <Clock className="w-12 h-12 text-amber-400 mx-auto mb-5" />
            <h1 className="text-2xl font-bold text-white mb-2">Payment still processing</h1>
            <p className="text-white/50 text-sm mb-6">
              We haven&apos;t received the confirmation yet. Don&apos;t worry — if your payment
              went through, your plan will activate automatically within a few minutes. No
              double charges, ever.
            </p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => window.location.reload()}
                className="px-5 py-2.5 rounded-xl bg-white/10 border border-white/10 text-white text-sm hover:bg-white/20 transition-colors"
              >
                Check again
              </button>
              <Link
                to="/dashboard"
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-cyan-500 text-white text-sm font-medium hover:opacity-90 transition-opacity"
              >
                Go to dashboard
              </Link>
            </div>
            <p className="text-white/30 text-xs mt-5">
              Still stuck after 10 minutes? Email support@ospra.io and we&apos;ll sort it out.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
