/**
 * OSPRA INTELLIGENCE - PUBLIC LIVE SCOREBOARD (task #52)
 * =======================================================
 *
 * No-auth marketing page proving Ospra's picks with real outcomes from the
 * Oubon Shop dogfood store. Fetches GET /api/public/scoreboard (cached 1h
 * server-side). Honest about sample size — small numbers are shown as-is.
 */

import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, ArrowRight, BadgeCheck, Clock, RefreshCw, ShieldCheck, TrendingUp,
} from 'lucide-react';
import { API_BASE_URL } from '../services/api';

const GRADE_STYLES = {
  'A+': 'bg-emerald-500/20 text-emerald-300 border-emerald-400/30',
  A: 'bg-emerald-500/15 text-emerald-300 border-emerald-400/20',
  'B+': 'bg-cyan-500/15 text-cyan-300 border-cyan-400/20',
  B: 'bg-cyan-500/10 text-cyan-300/80 border-cyan-400/15',
  'C+': 'bg-amber-500/10 text-amber-300/80 border-amber-400/15',
  C: 'bg-amber-500/10 text-amber-300/70 border-amber-400/10',
  D: 'bg-red-500/10 text-red-300/80 border-red-400/15',
  F: 'bg-red-500/15 text-red-300 border-red-400/20',
};

function GradeBadge({ grade }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-md border text-xs font-bold ${
        GRADE_STYLES[grade] || 'bg-white/10 text-white/60 border-white/10'
      }`}
    >
      {grade || '—'}
    </span>
  );
}

function SummaryCard({ icon: Icon, label, value, hint }) {
  return (
    <div className="p-5 rounded-2xl bg-white/5 border border-white/10">
      <div className="flex items-center gap-2 text-white/50 text-sm mb-2">
        <Icon className="w-4 h-4" /> {label}
      </div>
      <div className="text-3xl font-bold text-white">{value}</div>
      {hint && <p className="text-white/40 text-xs mt-1">{hint}</p>}
    </div>
  );
}

export default function Scoreboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/public/scoreboard`);
      if (!res.ok) throw new Error(`Server responded ${res.status}`);
      setData(await res.json());
    } catch (err) {
      setError(err.message || 'Failed to load the scoreboard.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const stats = data?.stats;
  const picks = data?.picks || [];
  const winRate = stats?.buy_win_rate != null ? `${Math.round(stats.buy_win_rate * 100)}%` : '—';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
      </div>

      <div className="relative max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-white font-bold">Ospra Live Scoreboard</h1>
              <p className="text-white/40 text-xs flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" /> Powered by real store data
              </p>
            </div>
          </div>
          <Link
            to="/register"
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-purple-500 to-cyan-500 text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Try Ospra free <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        <div className="text-center mb-10">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
            Our AI grades products. Here&apos;s how those grades performed.
          </h2>
          <p className="text-white/50 max-w-2xl mx-auto text-sm">
            Every pick below was graded by Ospra and tracked on our own Shopify store —
            no cherry-picking, no backtests. {data?.meta?.note}
          </p>
        </div>

        {loading && (
          <div className="text-center py-20 text-white/40">Loading live results…</div>
        )}

        {error && !loading && (
          <div className="max-w-md mx-auto text-center p-6 rounded-2xl bg-white/5 border border-white/10">
            <p className="text-white/60 text-sm mb-4">{error}</p>
            <button
              onClick={load}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 border border-white/10 text-white text-sm hover:bg-white/20 transition-colors"
            >
              <RefreshCw className="w-4 h-4" /> Retry
            </button>
          </div>
        )}

        {data && !loading && (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
              <SummaryCard
                icon={BadgeCheck}
                label="BUY-grade win rate"
                value={winRate}
                hint={
                  stats.buy_graded_deployed
                    ? `${stats.buy_with_sales} of ${stats.buy_graded_deployed} deployed BUY-grade picks made sales`
                    : 'No deployed BUY-grade picks yet'
                }
              />
              <SummaryCard
                icon={TrendingUp}
                label="Products graded"
                value={stats.total_graded}
                hint={`${stats.avoid_graded} graded AVOID and skipped`}
              />
              <SummaryCard
                icon={Clock}
                label="First sale ≤ 14 days"
                value={
                  stats.first_sale_sample_size
                    ? `${stats.sold_within_14_days} of ${stats.first_sale_sample_size}`
                    : '—'
                }
                hint={
                  stats.median_days_to_first_sale != null
                    ? `Median ${stats.median_days_to_first_sale} days to first sale`
                    : 'Tracking begins at first deployment'
                }
              />
            </div>

            {/* Honesty note for small samples */}
            {stats.total_graded > 0 && stats.total_graded < 30 && (
              <p className="text-center text-white/30 text-xs mb-6">
                Early days: {stats.total_graded} graded picks so far. We publish everything,
                including the misses — the sample grows weekly.
              </p>
            )}

            {/* Picks table */}
            <div className="rounded-2xl border border-white/10 overflow-hidden mb-10">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-white/5 text-white/40 text-left text-xs uppercase tracking-wide">
                    <th className="px-4 py-3 font-medium">Product</th>
                    <th className="px-4 py-3 font-medium">Niche</th>
                    <th className="px-4 py-3 font-medium">Grade</th>
                    <th className="px-4 py-3 font-medium max-md:hidden">Graded</th>
                    <th className="px-4 py-3 font-medium">Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {picks.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-10 text-center text-white/40">
                        First batch of graded picks lands here soon.
                      </td>
                    </tr>
                  )}
                  {picks.map((pick, i) => (
                    <tr key={i} className="border-t border-white/5 hover:bg-white/[0.03]">
                      <td className="px-4 py-3 text-white/90 max-w-[280px] truncate">{pick.title}</td>
                      <td className="px-4 py-3 text-white/50 capitalize">{pick.niche}</td>
                      <td className="px-4 py-3"><GradeBadge grade={pick.grade} /></td>
                      <td className="px-4 py-3 text-white/40 max-md:hidden">
                        {pick.graded_at ? new Date(pick.graded_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {!pick.deployed ? (
                          <span className="text-white/30 text-xs">Not deployed</span>
                        ) : pick.units_sold > 0 ? (
                          <span className="text-emerald-400 text-xs font-medium">
                            {pick.units_sold} sold
                            {pick.days_to_first_sale != null && ` · first sale in ${pick.days_to_first_sale}d`}
                          </span>
                        ) : (
                          <span className="text-white/40 text-xs">No sales yet</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Footer CTA */}
            <div className="text-center pb-10">
              <p className="text-white/40 text-sm mb-4">{data.meta?.source}</p>
              <Link
                to="/register"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-purple-500 to-cyan-500 text-white font-medium hover:opacity-90 transition-opacity"
              >
                Get picks like these for your store <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
