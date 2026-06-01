/**
 * LEARNING DASHBOARD — Self-learning Phase 3 (Task #13)
 * ======================================================
 * Read-only view of the AI feedback loop status. Consumes
 * GET /api/feedback/learning-stats which aggregates:
 *   - overall success rate (predictions that came true)
 *   - average prediction accuracy
 *   - per-niche performance (success rate, total revenue, learned adjustment)
 *   - positive vs negative learning signals
 *   - current global weights + last update timestamp
 *
 * Surfaces to the operator whether the self-learning loop is actually
 * working — without this it's an invisible system that could silently
 * stop learning and we'd never know.
 *
 * Routed at /learning.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Brain, TrendingUp, TrendingDown, Activity, RefreshCw, AlertCircle,
  Target, Award, Sparkles, GitBranch,
} from 'lucide-react';
import { authService } from '../services/auth';
import { PageLayout } from './Layout';

function fmtPct(n) {
  if (n == null) return '—';
  return `${Number(n).toFixed(1)}%`;
}

function fmtNum(n) {
  if (n == null) return '—';
  return Number(n).toLocaleString();
}

function fmtMoney(n) {
  if (n == null) return '—';
  return `$${Number(n).toFixed(0)}`;
}

function Tile({ icon, label, value, sub, color = 'text-zinc-100' }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-2">
        <div className="text-zinc-500">{icon}</div>
        <div className="text-[11px] uppercase tracking-wider text-zinc-500 font-semibold">{label}</div>
      </div>
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

function NicheRow({ niche }) {
  const adjustment = Number(niche.score_adjustment || 0);
  const adjustmentTone =
    adjustment > 0 ? 'text-emerald-400' :
    adjustment < 0 ? 'text-red-400' :
    'text-zinc-500';
  const adjustmentIcon =
    adjustment > 0 ? <TrendingUp className="w-3 h-3 inline" /> :
    adjustment < 0 ? <TrendingDown className="w-3 h-3 inline" /> :
    null;

  return (
    <tr className="border-b border-zinc-800 last:border-0">
      <td className="py-3 px-2 text-sm text-zinc-100">{niche.niche}</td>
      <td className="py-3 px-2 text-sm text-right">{niche.products_deployed}</td>
      <td className="py-3 px-2 text-sm text-right">
        <span className={
          niche.success_rate >= 70 ? 'text-emerald-400' :
          niche.success_rate >= 50 ? 'text-amber-400' :
          'text-red-400'
        }>{fmtPct(niche.success_rate)}</span>
      </td>
      <td className="py-3 px-2 text-sm text-right text-zinc-300">{fmtMoney(niche.total_revenue)}</td>
      <td className="py-3 px-2 text-sm text-right">
        <span className={adjustmentTone}>
          {adjustmentIcon}{' '}
          {adjustment > 0 ? '+' : ''}{adjustment.toFixed(1)}
        </span>
      </td>
    </tr>
  );
}

export default function LearningDashboard() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // authService.get returns parsed JSON directly (not {data: ...})
      const json = await authService.get('/api/feedback/learning-stats');
      setData(json);
    } catch (e) {
      // 401 on a fresh install means no outcomes yet — that's OK
      setError(e?.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  const niches = data?.niche_performance || [];
  const noOutcomesYet =
    !error &&
    data &&
    Number(data.total_recommendations || 0) === 0;

  return (
    <PageLayout>
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Brain className="w-5 h-5 text-cyan-400" />
              <h1 className="text-2xl font-bold text-zinc-100">Learning Loop</h1>
            </div>
            <p className="text-sm text-zinc-500">
              How the AI is improving over time — predictions vs reality, per-niche performance, learned adjustments.
            </p>
          </div>
          <button
            onClick={fetchStats}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded text-sm text-zinc-200 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {error && !data && (
          <div className="mb-4 p-4 bg-red-500/10 border border-red-500/30 rounded text-sm text-red-300 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold mb-0.5">Couldn't load learning stats</div>
              <div className="text-red-400/80">{error}</div>
            </div>
          </div>
        )}

        {noOutcomesYet && (
          <div className="mb-6 p-5 bg-zinc-900 border border-zinc-800 rounded-xl">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-zinc-100 font-semibold mb-1">No outcomes captured yet</div>
                <div className="text-sm text-zinc-400 leading-relaxed">
                  Pick products from <a href="/products" className="text-cyan-400 hover:underline">Products</a> and deploy them to Shopify to start the feedback loop.
                  The daily evaluation job (4 AM UTC) classifies outcomes once they have ≥7 days of sales data.
                </div>
              </div>
            </div>
          </div>
        )}

        {data && !noOutcomesYet && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <Tile
                icon={<Target className="w-4 h-4" />}
                label="Success rate"
                value={fmtPct(data.success_rate)}
                sub={`${data.successful}/${data.total_recommendations} predictions came true`}
                color={data.success_rate >= 70 ? 'text-emerald-400' :
                       data.success_rate >= 50 ? 'text-amber-400' : 'text-red-400'}
              />
              <Tile
                icon={<Award className="w-4 h-4" />}
                label="Prediction accuracy"
                value={fmtPct(data.avg_accuracy)}
                sub="How close projected matched actual"
              />
              <Tile
                icon={<Activity className="w-4 h-4" />}
                label="Learning events"
                value={fmtNum(data.total_learning_events)}
                sub={`${data.positive_signals || 0} positive / ${data.negative_signals || 0} negative`}
              />
              <Tile
                icon={<GitBranch className="w-4 h-4" />}
                label="Weights version"
                value={data.weight_version || 'v1.0'}
                sub={data.last_updated ? `Updated ${new Date(data.last_updated).toLocaleDateString()}` : '—'}
              />
            </div>

            {niches.length > 0 ? (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden mb-6">
                <div className="px-5 py-4 border-b border-zinc-800">
                  <div className="text-sm font-semibold text-zinc-100">Niche performance</div>
                  <div className="text-xs text-zinc-500 mt-0.5">Discovery → outcome attribution per niche, with learned score adjustments.</div>
                </div>
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-zinc-800 bg-zinc-950/50">
                      <th className="text-left text-[11px] font-semibold text-zinc-500 uppercase tracking-wider py-2 px-2">Niche</th>
                      <th className="text-right text-[11px] font-semibold text-zinc-500 uppercase tracking-wider py-2 px-2">Deployed</th>
                      <th className="text-right text-[11px] font-semibold text-zinc-500 uppercase tracking-wider py-2 px-2">Success rate</th>
                      <th className="text-right text-[11px] font-semibold text-zinc-500 uppercase tracking-wider py-2 px-2">Revenue</th>
                      <th className="text-right text-[11px] font-semibold text-zinc-500 uppercase tracking-wider py-2 px-2">Learned adj.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {niches.map((n) => <NicheRow key={n.niche} niche={n} />)}
                  </tbody>
                </table>
              </div>
            ) : null}

            {data.current_weights && Object.keys(data.current_weights).length > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                <div className="text-sm font-semibold text-zinc-100 mb-3">Current learned weights</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                  {Object.entries(data.current_weights).map(([k, v]) => (
                    <div key={k} className="bg-zinc-950 border border-zinc-800 rounded p-2.5">
                      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{k}</div>
                      <div className="text-sm font-mono text-zinc-100 mt-0.5">
                        {typeof v === 'number' ? v.toFixed(3) : String(v)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </PageLayout>
  );
}
