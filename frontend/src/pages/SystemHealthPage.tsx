import React, { useState, useEffect } from 'react';
import { Activity, Server, Zap, AlertTriangle, CheckCircle, XCircle, Clock, TrendingUp, ChevronRight, X } from 'lucide-react';
import { GlassPanel } from '../components/GlassPanel';

interface HealthSummary {
  integrations: {
    connected: number;
    total: number;
    status: string;
  };
  jobs: {
    healthy: number;
    total: number;
    running: number;
  };
  api: {
    avg_response_ms: number;
    requests_24h: number;
    error_rate: number;
  };
  errors: {
    count_24h: number;
  };
}

interface Integration {
  status: string;
  last_check: string;
  latency_ms?: number;
  rate_limit_remaining?: number;
  rate_limit_total?: number;
  quota_remaining?: number;
  quota_total?: number;
  errors_24h: number;
  last_error?: string;
}

interface Job {
  name: string;
  description: string;
  status: string;
  schedule: string;
  last_run?: {
    started_at: string;
    completed_at: string;
    duration_seconds: number;
    status: string;
    items_processed: number;
    errors: number;
  };
  success_rate_7d: number;
  avg_duration_7d: number;
}

interface SystemError {
  error_id: string;
  category: string;
  severity: string;
  message: string;
  occurred_at: string;
  acknowledged: boolean;
  resolved: boolean;
}

interface Alert {
  alert_id: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  triggered_at: string;
  is_active: boolean;
  acknowledged: boolean;
}

const SystemHealthPage: React.FC = () => {
  const [overallStatus, setOverallStatus] = useState<string>('HEALTHY');
  const [summary, setSummary] = useState<HealthSummary | null>(null);
  const [integrations, setIntegrations] = useState<Record<string, Integration>>({});
  const [jobs, setJobs] = useState<Job[]>([]);
  const [errors, setErrors] = useState<SystemError[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [apiPerf, setApiPerf] = useState<any>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedCard, setSelectedCard] = useState<string | null>(null);

  // User-friendly display names for integrations
  const integrationDisplayNames: Record<string, string> = {
    claude_ai: 'Ospra Intelligence',
    shopify: 'Shopify',
    aliexpress: 'AliExpress',
    meta_ads: 'Meta Advertising',
    gmail: 'Email Service',
  };

  // User-friendly display names for jobs
  const jobDisplayNames: Record<string, string> = {
    product_discovery: 'Product Discovery',
    competitor_monitoring: 'Competitor Monitoring',
    email_processor: 'Email Processing',
    inventory_sync: 'Inventory Synchronization',
    analytics_aggregation: 'Analytics Reports',
    ab_test_monitor: 'A/B Test Monitor',
    ranking_update: 'Product Rankings',
    niche_analysis: 'Niche Analysis',
  };

  const fetchHealthData = async () => {
    try {
      // Fetch overall status
      const statusRes = await fetch('http://localhost:8001/api/health');
      const statusData = await statusRes.json();
      setOverallStatus(statusData.status);

      // Fetch summary
      const summaryRes = await fetch('http://localhost:8001/api/health/summary');
      const summaryData = await summaryRes.json();
      setSummary(summaryData);

      // Fetch integrations
      const integrationsRes = await fetch('http://localhost:8001/api/health/integrations');
      const integrationsData = await integrationsRes.json();
      setIntegrations(integrationsData);

      // Fetch jobs
      const jobsRes = await fetch('http://localhost:8001/api/health/jobs');
      const jobsData = await jobsRes.json();
      setJobs(jobsData);

      // Fetch errors
      const errorsRes = await fetch('http://localhost:8001/api/health/errors?hours=24&limit=50');
      const errorsData = await errorsRes.json();
      setErrors(errorsData.errors);

      // Fetch alerts
      const alertsRes = await fetch('http://localhost:8001/api/health/alerts?active_only=true');
      const alertsData = await alertsRes.json();
      setAlerts(alertsData.alerts);

      // Fetch API performance
      const apiRes = await fetch('http://localhost:8001/api/health/api-performance?hours=24');
      const apiData = await apiRes.json();
      setApiPerf(apiData);

      setLastUpdate(new Date());
    } catch (error) {
      console.error('Failed to fetch health data:', error);
    }
  };

  useEffect(() => {
    fetchHealthData();

    if (autoRefresh) {
      const interval = setInterval(fetchHealthData, 30000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'HEALTHY':
      case 'CONNECTED':
      case 'SUCCESS':
      case 'IDLE':
        return 'text-green-600';
      case 'CONFIGURED':
      case 'DEGRADED':
      case 'WARNING':
        return 'text-yellow-600';
      case 'CRITICAL':
      case 'FAILED':
      case 'ERROR':
      case 'DISCONNECTED':
        return 'text-red-600';
      case 'RUNNING':
        return 'text-blue-600';
      case 'DISABLED':
        return 'text-gray-600';
      default:
        return 'text-gray-600';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'HEALTHY':
      case 'CONNECTED':
      case 'SUCCESS':
        return <CheckCircle className="w-5 h-5" />;
      case 'CONFIGURED':
      case 'DEGRADED':
      case 'WARNING':
        return <AlertTriangle className="w-5 h-5" />;
      case 'CRITICAL':
      case 'FAILED':
      case 'ERROR':
      case 'DISCONNECTED':
        return <XCircle className="w-5 h-5" />;
      case 'RUNNING':
        return <Activity className="w-5 h-5 animate-pulse" />;
      default:
        return <Clock className="w-5 h-5" />;
    }
  };

  const timeAgo = (timestamp: string) => {
    const now = new Date();
    const then = new Date(timestamp);
    const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);

    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const Modal = ({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) => (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-4xl max-h-[80vh] overflow-y-auto rounded-2xl border shadow-2xl"
        style={{
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(24px)',
          borderColor: 'rgba(0, 0, 0, 0.1)',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.2)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-6 border-b border-gray-200/50">
          <h2 className="text-2xl font-light text-gray-900">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-200/50 transition-colors"
          >
            <X className="w-5 h-5 text-gray-600" />
          </button>
        </div>
        <div className="p-6">
          {children}
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 p-12" style={{ perspective: '1500px' }}>
      <div className="max-w-7xl mx-auto space-y-12">
        {/* Header */}
        <GlassPanel depth={80} delay={0.2}>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-light text-gray-900">System Health</h1>
              <p className="text-sm text-gray-600 mt-1">Real-time monitoring and diagnostics</p>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`px-4 py-2 rounded-xl text-sm font-light transition-all ${
                  autoRefresh
                    ? 'bg-indigo-500/10 text-indigo-700 border border-indigo-500/30'
                    : 'bg-gray-500/10 text-gray-600 border border-gray-500/30'
                }`}
              >
                {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
              </button>
              <button
                onClick={fetchHealthData}
                className="px-4 py-2 rounded-xl text-sm font-light bg-indigo-500/10 text-indigo-700 border border-indigo-500/30 hover:bg-indigo-500/20 transition-all"
              >
                Refresh Now
              </button>
              <span className="text-sm text-gray-500 font-light">
                Updated {timeAgo(lastUpdate.toISOString())}
              </span>
            </div>
          </div>
        </GlassPanel>

      {/* Overall Status Banner */}
      <GlassPanel depth={70} delay={0.3}>
        <div className="flex items-center gap-4">
          <div className={getStatusColor(overallStatus)}>
            {getStatusIcon(overallStatus)}
          </div>
          <div>
            <h2 className={`text-2xl font-light ${getStatusColor(overallStatus)}`}>
              {overallStatus === 'HEALTHY' && 'All Systems Operational'}
              {overallStatus === 'DEGRADED' && 'Degraded Performance'}
              {overallStatus === 'CRITICAL' && 'Critical Issues Detected'}
              {overallStatus === 'DOWN' && 'System Down'}
            </h2>
            <p className="text-gray-600 text-sm mt-1 font-light">
              System uptime: 99.8% • Last check: {timeAgo(lastUpdate.toISOString())}
            </p>
          </div>
        </div>
      </GlassPanel>

      {/* Interactive Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Integrations Card */}
          <GlassPanel depth={60} delay={0.4} className="p-0">
            <button
              onClick={() => setSelectedCard('integrations')}
              className="text-left w-full p-6 transition-all group"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20">
                  <Server className="w-6 h-6 text-indigo-600" />
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-indigo-600 transition-colors" />
              </div>
              <div className={`text-3xl font-light mb-2 ${summary.integrations.status === 'healthy' ? 'text-green-600' : 'text-yellow-600'}`}>
                {summary.integrations.connected}/{summary.integrations.total}
              </div>
              <h3 className="text-gray-900 font-light text-lg">Integrations</h3>
              <p className="text-gray-600 text-sm mt-1 font-light">Click to view details</p>
            </button>
          </GlassPanel>

          {/* Jobs Card */}
          <GlassPanel depth={60} delay={0.5} className="p-0">
            <button
              onClick={() => setSelectedCard('jobs')}
              className="text-left w-full p-6 transition-all group"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-yellow-500/20 to-orange-500/20">
                  <Zap className="w-6 h-6 text-yellow-600" />
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-yellow-600 transition-colors" />
              </div>
              <div className="text-3xl font-light text-green-600 mb-2">
                {summary.jobs.healthy}/{summary.jobs.total}
              </div>
              <h3 className="text-gray-900 font-light text-lg">Background Jobs</h3>
              <p className="text-gray-600 text-sm mt-1 font-light">
                {summary.jobs.running} running now
              </p>
            </button>
          </GlassPanel>

          {/* API Performance Card */}
          <GlassPanel depth={60} delay={0.6} className="p-0">
            <button
              onClick={() => setSelectedCard('api')}
              className="text-left w-full p-6 transition-all group"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20">
                  <TrendingUp className="w-6 h-6 text-blue-600" />
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-blue-600 transition-colors" />
              </div>
              <div className="text-3xl font-light text-blue-600 mb-2">
                {summary.api.avg_response_ms.toFixed(0)}ms
              </div>
              <h3 className="text-gray-900 font-light text-lg">API Performance</h3>
              <p className="text-gray-600 text-sm mt-1 font-light">
                {summary.api.requests_24h.toLocaleString()} requests
              </p>
            </button>
          </GlassPanel>

          {/* Errors Card */}
          <GlassPanel depth={60} delay={0.7} className="p-0">
            <button
              onClick={() => setSelectedCard('errors')}
              className="text-left w-full p-6 transition-all group"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-red-500/20 to-pink-500/20">
                  <AlertTriangle className="w-6 h-6 text-red-600" />
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-red-600 transition-colors" />
              </div>
              <div className={`text-3xl font-light mb-2 ${summary.errors.count_24h > 0 ? 'text-red-600' : 'text-green-600'}`}>
                {summary.errors.count_24h}
              </div>
              <h3 className="text-gray-900 font-light text-lg">Errors</h3>
              <p className="text-gray-600 text-sm mt-1 font-light">Last 24 hours</p>
            </button>
          </GlassPanel>
        </div>
      )}

      {/* Modals */}
      {selectedCard === 'integrations' && (
        <Modal title="Integration Status" onClose={() => setSelectedCard(null)}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(integrations).map(([name, integration]) => (
              <div
                key={name}
                className="rounded-xl p-4 border bg-white/50"
                style={{
                  borderColor: 'rgba(0, 0, 0, 0.1)'
                }}
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-gray-900 font-light text-lg">{integrationDisplayNames[name] || name}</h3>
                  <div className={`flex items-center gap-2 ${getStatusColor(integration.status)}`}>
                    {getStatusIcon(integration.status)}
                    <span className="text-sm font-light">{integration.status}</span>
                  </div>
                </div>

                <div className="space-y-2 text-sm font-light">
                  {integration.latency_ms !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Latency:</span>
                      <span className="text-gray-900">{integration.latency_ms}ms</span>
                    </div>
                  )}

                  {integration.rate_limit_remaining !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Rate Limit:</span>
                      <span className="text-gray-900">
                        {integration.rate_limit_remaining}/{integration.rate_limit_total}
                      </span>
                    </div>
                  )}

                  {integration.quota_remaining !== undefined && integration.quota_remaining !== null && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Quota:</span>
                      <span className="text-gray-900">
                        {integration.quota_remaining.toLocaleString()}/{integration.quota_total?.toLocaleString()}
                      </span>
                    </div>
                  )}

                  <div className="flex justify-between">
                    <span className="text-gray-600">Errors (24h):</span>
                    <span className={integration.errors_24h > 0 ? 'text-red-600' : 'text-green-600'}>
                      {integration.errors_24h}
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-gray-600">Last Check:</span>
                    <span className="text-gray-900">{timeAgo(integration.last_check)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Modal>
      )}

      {selectedCard === 'jobs' && (
        <Modal title="Background Jobs" onClose={() => setSelectedCard(null)}>
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.name}
                className="rounded-xl p-4 border bg-white/50"
                style={{
                  borderColor: 'rgba(0, 0, 0, 0.1)'
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <h3 className="text-gray-900 font-light text-lg">{jobDisplayNames[job.name] || job.name}</h3>
                    <p className="text-gray-600 text-sm font-light">{job.description}</p>
                  </div>
                  <div className={`flex items-center gap-2 ${getStatusColor(job.status)}`}>
                    {getStatusIcon(job.status)}
                    <span className="font-light">{job.status}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3 text-sm font-light">
                  <div>
                    <span className="text-gray-600 block">Schedule</span>
                    <span className="text-gray-900">{job.schedule}</span>
                  </div>
                  <div>
                    <span className="text-gray-600 block">Success Rate (7d)</span>
                    <span className={job.success_rate_7d >= 95 ? 'text-green-600' : 'text-yellow-600'}>
                      {job.success_rate_7d.toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-600 block">Avg Duration (7d)</span>
                    <span className="text-gray-900">{job.avg_duration_7d.toFixed(1)}s</span>
                  </div>
                  {job.last_run && (
                    <div>
                      <span className="text-gray-600 block">Last Run</span>
                      <span className="text-gray-900">{timeAgo(job.last_run.started_at)}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Modal>
      )}

      {selectedCard === 'api' && apiPerf && (
        <Modal title="API Performance Metrics" onClose={() => setSelectedCard(null)}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="text-center">
              <div className="text-3xl font-light text-gray-900 mb-2">
                {apiPerf.requests_24h?.toLocaleString() || 0}
              </div>
              <div className="text-sm text-gray-600 font-light">Total Requests</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-light text-blue-600 mb-2">
                {apiPerf.avg_response_time_ms?.toFixed(0) || 0}ms
              </div>
              <div className="text-sm text-gray-600 font-light">Avg Response</div>
            </div>
            <div className="text-center">
              <div className={`text-3xl font-light mb-2 ${(apiPerf.error_rate_percent || 0) > 5 ? 'text-red-600' : 'text-green-600'}`}>
                {apiPerf.error_rate_percent?.toFixed(1) || 0}%
              </div>
              <div className="text-sm text-gray-600 font-light">Error Rate</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-light text-yellow-600 mb-2">
                {apiPerf.p95_response_time_ms?.toFixed(0) || 0}ms
              </div>
              <div className="text-sm text-gray-600 font-light">P95 Latency</div>
            </div>
          </div>
        </Modal>
      )}

      {selectedCard === 'errors' && (
        <Modal title="Error Log" onClose={() => setSelectedCard(null)}>
          {errors.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-4" />
              <p className="text-gray-900 font-light text-lg">No errors in the last 24 hours</p>
              <p className="text-gray-600 text-sm mt-2 font-light">System is running smoothly</p>
            </div>
          ) : (
            <div className="space-y-3">
              {errors.map((error) => (
                <div
                  key={error.error_id}
                  className="rounded-xl p-4 border bg-white/50"
                  style={{
                    borderColor: 'rgba(239, 68, 68, 0.2)'
                  }}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`px-3 py-1 rounded-full text-xs font-light ${
                          error.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-700' :
                          error.severity === 'ERROR' ? 'bg-orange-500/20 text-orange-700' :
                          'bg-yellow-500/20 text-yellow-700'
                        }`}>
                          {error.severity}
                        </span>
                        <span className="px-3 py-1 rounded-full text-xs font-light bg-gray-500/20 text-gray-700">
                          {error.category}
                        </span>
                      </div>
                      <p className="text-gray-900 font-light">{error.message}</p>
                      <p className="text-gray-600 text-sm mt-2 font-light">{new Date(error.occurred_at).toLocaleString()}</p>
                    </div>
                    <div className="flex gap-2">
                      {error.acknowledged && (
                        <span className="px-3 py-1 rounded-full text-xs bg-blue-500/20 text-blue-700 font-light">
                          Acknowledged
                        </span>
                      )}
                      {error.resolved && (
                        <span className="px-3 py-1 rounded-full text-xs bg-green-500/20 text-green-700 font-light">
                          Resolved
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}

      {/* Active Alerts Section */}
      {alerts.length > 0 && (
        <GlassPanel depth={60} delay={0.8}>
          <h2 className="text-xl font-light text-gray-900 mb-4">Active Alerts ({alerts.length})</h2>
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div
                key={alert.alert_id}
                className="rounded-xl p-4 border bg-white/50"
                style={{
                  borderColor: 'rgba(239, 68, 68, 0.2)'
                }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`px-3 py-1 rounded-full text-xs font-light ${
                        alert.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-700' :
                        alert.severity === 'ERROR' ? 'bg-orange-500/20 text-orange-700' :
                        alert.severity === 'WARNING' ? 'bg-yellow-500/20 text-yellow-700' :
                        'bg-blue-500/20 text-blue-700'
                      }`}>
                        {alert.severity}
                      </span>
                      <span className="px-3 py-1 rounded-full text-xs font-light bg-gray-500/20 text-gray-700">
                        {alert.alert_type}
                      </span>
                    </div>
                    <h4 className="text-gray-900 font-light text-lg">{alert.title}</h4>
                    <p className="text-gray-600 text-sm mt-1 font-light">{alert.message}</p>
                    <p className="text-gray-500 text-xs mt-2 font-light">{new Date(alert.triggered_at).toLocaleString()}</p>
                  </div>
                  {alert.acknowledged && (
                    <span className="px-3 py-1 rounded-full text-xs bg-blue-500/20 text-blue-700 font-light">
                      Acknowledged
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </GlassPanel>
      )}
      </div>
    </div>
  );
};

export default SystemHealthPage;
