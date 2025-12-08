import { useState, useEffect } from 'react';
import {
  Bot,
  Play,
  Pause,
  RefreshCw,
  Settings,
  DollarSign,
  Package,
  TrendingUp,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  ExternalLink,
  AlertCircle,
  Zap,
} from 'lucide-react';
import { GlassPanel } from '../components/GlassPanel';
import { autoDeployAPI, type AutoDeployStatus, type DeploymentHistoryItem, type AutoDeployCriteria } from '../services/api';

export const AutoDeploymentPage = () => {
  const [status, setStatus] = useState<AutoDeployStatus | null>(null);
  const [history, setHistory] = useState<DeploymentHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [criteria, setCriteria] = useState<Partial<AutoDeployCriteria>>({});

  const loadData = async () => {
    setLoading(true);
    try {
      const [statusData, historyData] = await Promise.all([
        autoDeployAPI.getStatus(),
        autoDeployAPI.getHistory(20),
      ]);
      setStatus(statusData);
      setHistory(historyData);
      setCriteria(statusData.criteria);
    } catch (error) {
      console.error('Failed to load auto-deploy data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggle = async () => {
    if (!status) return;

    try {
      if (status.enabled) {
        await autoDeployAPI.disable();
      } else {
        await autoDeployAPI.enable();
      }
      await loadData();
    } catch (error) {
      console.error('Failed to toggle auto-deploy:', error);
      alert('Failed to toggle auto-deployment');
    }
  };

  const handleRunNow = async () => {
    setRunning(true);
    try {
      const result = await autoDeployAPI.runNow();
      alert(`${result.message}\n\nDeployed: ${result.deployed}\nFailed: ${result.failed}\nCost: $${result.total_cost.toFixed(2)}`);
      await loadData();
    } catch (error) {
      console.error('Failed to run deployment:', error);
      alert('Failed to run deployment check');
    } finally {
      setRunning(false);
    }
  };

  const handleUpdateCriteria = async () => {
    try {
      await autoDeployAPI.updateCriteria(criteria);
      alert('Criteria updated successfully!');
      setShowSettings(false);
      await loadData();
    } catch (error) {
      console.error('Failed to update criteria:', error);
      alert('Failed to update criteria');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-12 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-indigo-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading auto-deployment data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-12">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-light text-gray-900 flex items-center gap-3">
              <Bot className="w-8 h-8 text-indigo-600" />
              Auto-Deployment
            </h1>
            <p className="text-gray-500 mt-1">Automatically deploy high-scoring products to Shopify</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={loadData}
              className="px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
            <button
              onClick={handleRunNow}
              disabled={running || !status?.enabled}
              className="px-5 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:opacity-90 transition flex items-center gap-2 shadow-lg shadow-green-500/25 disabled:opacity-50"
            >
              {running ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              Run Now
            </button>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="px-5 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:opacity-90 transition flex items-center gap-2 shadow-lg shadow-purple-500/25"
            >
              <Settings className="w-4 h-4" />
              Settings
            </button>
          </div>
        </div>

        {/* Status Banner */}
        <GlassPanel className={`p-6 border-2 ${status?.enabled ? 'border-green-500 bg-green-50' : 'border-gray-300'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-3">
                <div className={`w-4 h-4 rounded-full ${status?.enabled ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                <span className="font-semibold text-gray-900">
                  {status?.enabled ? 'Active' : 'Disabled'}
                </span>
              </div>
              {status?.last_run && (
                <>
                  <div className="text-gray-400">|</div>
                  <div className="text-gray-600 flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    Last run: {new Date(status.last_run).toLocaleString()}
                  </div>
                </>
              )}
            </div>
            <button
              onClick={handleToggle}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 font-medium transition ${
                status?.enabled
                  ? 'bg-red-100 text-red-700 hover:bg-red-200'
                  : 'bg-green-100 text-green-700 hover:bg-green-200'
              }`}
            >
              {status?.enabled ? (
                <>
                  <Pause className="w-4 h-4" />
                  Disable
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Enable
                </>
              )}
            </button>
          </div>

          {!status?.enabled && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-yellow-800">
                <p className="font-medium">Auto-deployment is currently disabled</p>
                <p className="mt-1">Enable it to start automatically deploying high-scoring products to your Shopify store.</p>
              </div>
            </div>
          )}
        </GlassPanel>

        {/* Statistics Cards */}
        <div className="grid grid-cols-4 gap-6">
          <GlassPanel className="p-6">
            <div className="flex items-center justify-between mb-4">
              <Package className="w-8 h-8 text-indigo-500" />
              <span className="text-xs text-indigo-600 bg-indigo-50 px-2 py-1 rounded-full">Total</span>
            </div>
            <p className="text-3xl font-bold text-gray-900">{status?.total_deployed || 0}</p>
            <p className="text-sm text-gray-500">Products Deployed</p>
          </GlassPanel>

          <GlassPanel className="p-6">
            <div className="flex items-center justify-between mb-4">
              <DollarSign className="w-8 h-8 text-emerald-500" />
              <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full">Cost</span>
            </div>
            <p className="text-3xl font-bold text-gray-900">${status?.total_cost.toFixed(2) || '0.00'}</p>
            <p className="text-sm text-gray-500">Total AI Cost</p>
          </GlassPanel>

          <GlassPanel className="p-6">
            <div className="flex items-center justify-between mb-4">
              <TrendingUp className="w-8 h-8 text-purple-500" />
              <span className="text-xs text-purple-600 bg-purple-50 px-2 py-1 rounded-full">Avg</span>
            </div>
            <p className="text-3xl font-bold text-gray-900">
              ${status?.total_deployed ? (status.total_cost / status.total_deployed).toFixed(2) : '0.00'}
            </p>
            <p className="text-sm text-gray-500">Cost per Product</p>
          </GlassPanel>

          <GlassPanel className="p-6">
            <div className="flex items-center justify-between mb-4">
              <Clock className="w-8 h-8 text-amber-500" />
              <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded-full">Schedule</span>
            </div>
            <p className="text-3xl font-bold text-gray-900">1h</p>
            <p className="text-sm text-gray-500">Check Interval</p>
          </GlassPanel>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <GlassPanel className="p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Deployment Criteria</h2>

            <div className="grid grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Min Score (0-100)
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={criteria.min_score || 80}
                  onChange={(e) => setCriteria({ ...criteria, min_score: Number(e.target.value) })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Min Profit Margin (%)
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={(criteria.min_profit_margin || 0.35) * 100}
                  onChange={(e) => setCriteria({ ...criteria, min_profit_margin: Number(e.target.value) / 100 })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Saturation
                </label>
                <select
                  value={criteria.max_saturation || 'medium'}
                  onChange={(e) => setCriteria({ ...criteria, max_saturation: e.target.value as 'low' | 'medium' | 'high' })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max per Day
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={criteria.max_per_day || 5}
                  onChange={(e) => setCriteria({ ...criteria, max_per_day: Number(e.target.value) })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max per Hour
                </label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={criteria.max_per_hour || 2}
                  onChange={(e) => setCriteria({ ...criteria, max_per_hour: Number(e.target.value) })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Daily Cost ($)
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={criteria.max_daily_cost || 1.0}
                  onChange={(e) => setCriteria({ ...criteria, max_daily_cost: Number(e.target.value) })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Min Trend Velocity
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={criteria.min_trend_velocity || 70}
                  onChange={(e) => setCriteria({ ...criteria, min_trend_velocity: Number(e.target.value) })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex items-end">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={criteria.require_multiple_sources ?? true}
                    onChange={(e) => setCriteria({ ...criteria, require_multiple_sources: e.target.checked })}
                    className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-sm font-medium text-gray-700">Require Multiple Sources</span>
                </label>
              </div>

              <div className="flex items-end">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={criteria.auto_publish ?? false}
                    onChange={(e) => setCriteria({ ...criteria, auto_publish: e.target.checked })}
                    className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-sm font-medium text-gray-700">Auto-Publish (vs Draft)</span>
                </label>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowSettings(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateCriteria}
                className="px-5 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg hover:opacity-90 transition flex items-center gap-2"
              >
                <CheckCircle className="w-4 h-4" />
                Save Changes
              </button>
            </div>
          </GlassPanel>
        )}

        {/* Deployment History */}
        <GlassPanel className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-6">Deployment History</h2>

          {history.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-gray-200 rounded-lg">
              <Package className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No deployments yet</p>
              <p className="text-sm text-gray-400 mt-1">Products will appear here once auto-deployed</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Product</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Niche</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Score</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">AI Cost</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Status</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Deployed</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Link</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((item) => (
                    <tr key={item.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3 px-4">
                        <span className="font-medium text-gray-900">{item.product_name}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-block px-2 py-1 text-xs bg-indigo-50 text-indigo-700 rounded-full">
                          {item.niche}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`font-semibold ${item.score >= 80 ? 'text-green-600' : 'text-amber-600'}`}>
                          {item.score.toFixed(1)}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-gray-700">${item.ai_cost.toFixed(2)}</span>
                      </td>
                      <td className="py-3 px-4">
                        {item.success ? (
                          <span className="flex items-center gap-1 text-green-600">
                            <CheckCircle className="w-4 h-4" />
                            Success
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-red-600" title={item.error || undefined}>
                            <XCircle className="w-4 h-4" />
                            Failed
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-gray-600">
                          {new Date(item.deployed_at).toLocaleString()}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {item.shopify_url && (
                          <a
                            href={item.shopify_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                          >
                            View <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassPanel>

        {/* Information Panel */}
        <GlassPanel className="p-6 bg-blue-50 border-blue-200">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-800">
              <p className="font-medium mb-2">How Auto-Deployment Works</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Runs every hour when enabled</li>
                <li>Discovers products matching your criteria</li>
                <li>Deploys top-scoring products with full AI pipeline (content + images + SEO + pricing)</li>
                <li>Products are saved as drafts by default for your review</li>
                <li>Respects daily/hourly limits and cost constraints</li>
              </ul>
            </div>
          </div>
        </GlassPanel>
      </div>
    </div>
  );
};

export default AutoDeploymentPage;
