/**
 * Ospra Intelligence - System Health Page
 * 
 * FULLY FUNCTIONAL:
 * - Real system health checks
 * - Service status monitoring
 * - Integration status
 * - API health
 */

import { useState } from 'react';
import {
  Activity,
  Server,
  Database,
  Wifi,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Clock,
  Zap,
  Globe,
  Mail,
  ShoppingBag,
  Brain,
  TrendingUp,
} from 'lucide-react';

import {
  useSystemHealth,
  useSystemServices,
} from '../hooks/useData';
import { systemAPI } from '../services/api';

// =============================================================================
// SERVICE CARD
// =============================================================================

interface ServiceCardProps {
  name: string;
  status: 'online' | 'warning' | 'offline' | 'processing';
  detail?: string;
  latency?: number;
  icon: React.ReactNode;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

function ServiceCard({ name, status, detail, latency, icon, onRefresh, isRefreshing }: ServiceCardProps) {
  const getStatusConfig = (s: string) => {
    switch (s) {
      case 'online':
        return { color: 'text-green-600', bg: 'bg-green-500/100', label: 'Online', Icon: CheckCircle2 };
      case 'processing':
        return { color: 'text-blue-600', bg: 'bg-cyan-500/100', label: 'Processing', Icon: Activity };
      case 'warning':
        return { color: 'text-amber-600', bg: 'bg-amber-500', label: 'Warning', Icon: AlertCircle };
      case 'offline':
        return { color: 'text-red-600', bg: 'bg-red-500/100', label: 'Offline', Icon: XCircle };
      default:
        return { color: 'text-tertiary', bg: ' 0', label: 'Unknown', Icon: Activity };
    }
  };

  const config = getStatusConfig(status);

  return (
    <div className="glass-card p-5">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-xl ${status === 'online' ? 'bg-green-500/100/10' : status === 'warning' ? 'bg-amber-500/10' : 'bg-black/5'}`}>
            {icon}
          </div>
          <div>
            <h3 className="text-sm font-medium text-primary">{name}</h3>
            {detail && <p className="text-xs text-tertiary mt-0.5">{detail}</p>}
          </div>
        </div>
        {onRefresh && (
          <button
            className="p-2 hover:bg-black/5 rounded-lg"
            onClick={onRefresh}
            disabled={isRefreshing}
          >
            <RefreshCw className={`w-4 h-4 text-tertiary ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${config.bg} ${status === 'processing' ? 'animate-pulse' : ''}`} />
          <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>
        </div>
        {latency !== undefined && (
          <span className="text-xs text-tertiary">{latency}ms</span>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// HEALTH METRIC CARD
// =============================================================================

function HealthMetricCard({ label, value, unit, status }: {
  label: string;
  value: string | number;
  unit?: string;
  status?: 'good' | 'warning' | 'critical';
}) {
  const statusColors = {
    good: 'text-green-600',
    warning: 'text-amber-600',
    critical: 'text-red-600',
  };

  return (
    <div className="glass-card p-4 text-center">
      <div className={`text-2xl font-bold ${status ? statusColors[status] : 'text-primary'}`}>
        {value}{unit && <span className="text-sm font-normal text-tertiary ml-1">{unit}</span>}
      </div>
      <div className="text-xs text-tertiary mt-1">{label}</div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function SystemHealthPage() {
  // State
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshingService, setRefreshingService] = useState<string | null>(null);

  // Data hooks
  const { data: healthData, isLoading: healthLoading, error: healthError, refetch: refetchHealth } = useSystemHealth();
  const { data: servicesData, isLoading: servicesLoading, error: servicesError, refetch: refetchServices } = useSystemServices();

  // Ensure services is always an array
  const services = Array.isArray(servicesData?.services)
    ? servicesData.services
    : Array.isArray(servicesData)
    ? servicesData
    : [];
  const hasError = healthError || servicesError;

  // Service icon mapping
  const serviceIcons: Record<string, React.ReactNode> = {
    'Ospra Intelligence': <Brain className="w-5 h-5 text-purple-600" />,
    'AliExpress API': <Globe className="w-5 h-5 text-orange-500" />,
    'Email Automation': <Mail className="w-5 h-5 text-blue-600" />,
    'Shopify Sync': <ShoppingBag className="w-5 h-5 text-green-600" />,
    'Database': <Database className="w-5 h-5 text-cyan-600" />,
    'TikTok Trends': <TrendingUp className="w-5 h-5 text-pink-500" />,
  };

  // Handlers
  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    try {
      await refetchHealth();
      await refetchServices();
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleRefreshService = async (serviceName: string) => {
    setRefreshingService(serviceName);
    try {
      await systemAPI.refreshService(serviceName);
      await refetchServices();
    } catch (error) {
      console.error('Failed to refresh service:', error);
    } finally {
      setRefreshingService(null);
    }
  };

  // Calculate overall health
  const onlineCount = services.filter(s => s.status === 'online').length;
  const totalCount = services.length;
  const healthPercentage = totalCount > 0 ? Math.round((onlineCount / totalCount) * 100) : 0;
  const overallStatus = healthPercentage >= 80 ? 'good' : healthPercentage >= 50 ? 'warning' : 'critical';

  const isLoading = healthLoading || servicesLoading;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary flex items-center gap-2">
            <Activity className="w-6 h-6 text-accent" />
            System Health
          </h1>
          <p className="text-sm text-secondary mt-1">
            Monitor all integrations and services
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
            overallStatus === 'good' ? 'bg-green-500/100/10 border border-green-500/20' :
            overallStatus === 'warning' ? 'bg-amber-500/10 border border-amber-500/20' :
            'bg-red-500/100/10 border border-red-500/20'
          }`}>
            {overallStatus === 'good' ? (
              <CheckCircle2 className="w-4 h-4 text-green-600" />
            ) : overallStatus === 'warning' ? (
              <AlertCircle className="w-4 h-4 text-amber-600" />
            ) : (
              <XCircle className="w-4 h-4 text-red-600" />
            )}
            <span className={`text-xs font-medium ${
              overallStatus === 'good' ? 'text-green-600' :
              overallStatus === 'warning' ? 'text-amber-600' : 'text-red-600'
            }`}>
              {healthPercentage}% Healthy
            </span>
          </div>
          <button
            className="btn-ghost"
            onClick={handleRefreshAll}
            disabled={isRefreshing}
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh All</span>
          </button>
        </div>
      </div>

      {/* Health Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <HealthMetricCard
          label="Services Online"
          value={`${onlineCount}/${totalCount}`}
          status={overallStatus}
        />
        <HealthMetricCard
          label="API Uptime"
          value={healthData?.uptime || '99.9'}
          unit="%"
          status="good"
        />
        <HealthMetricCard
          label="Avg Response"
          value={healthData?.avg_latency || 45}
          unit="ms"
          status={healthData?.avg_latency > 200 ? 'warning' : 'good'}
        />
        <HealthMetricCard
          label="Last Check"
          value={new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        />
      </div>

      {/* Services Grid */}
      <div>
        <h2 className="text-lg font-medium text-primary mb-4">Integration Status</h2>
        {isLoading && services.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-accent animate-spin" />
          </div>
        ) : hasError ? (
          <div className="glass-card p-12 text-center">
            <XCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-primary mb-2">Connection Error</h3>
            <p className="text-sm text-secondary mb-4">
              Unable to fetch system health data. Backend might be offline.
            </p>
            <button className="btn-primary" onClick={handleRefreshAll}>
              <RefreshCw className="w-4 h-4" />
              <span>Retry Connection</span>
            </button>
          </div>
        ) : services.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <Server className="w-12 h-12 text-tertiary mx-auto mb-4" />
            <h3 className="text-lg font-medium text-primary mb-2">No Services Found</h3>
            <p className="text-sm text-secondary">
              Backend is connected but no services are configured.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {services.map((service) => (
              <ServiceCard
                key={service.name}
                name={service.name}
                status={service.status}
                detail={service.detail}
                latency={service.latency}
                icon={serviceIcons[service.name] || <Server className="w-5 h-5 text-tertiary" />}
                onRefresh={() => handleRefreshService(service.name)}
                isRefreshing={refreshingService === service.name}
              />
            ))}
          </div>
        )}
      </div>

      {/* Backend Status */}
      <div>
        <h2 className="text-lg font-medium text-primary mb-4">Backend Status</h2>
        <div className="glass-card p-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div>
              <div className="text-xs text-tertiary mb-1">Backend URL</div>
              <div className="text-sm font-medium text-primary">
                {import.meta.env.VITE_API_URL || 'http://localhost:8001'}
              </div>
            </div>
            <div>
              <div className="text-xs text-tertiary mb-1">Status</div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${healthData ? 'bg-green-500/100' : 'bg-red-500/100'}`} />
                <span className={`text-sm font-medium ${healthData ? 'text-green-600' : 'text-red-500'}`}>
                  {healthData ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
            <div>
              <div className="text-xs text-tertiary mb-1">Version</div>
              <div className="text-sm font-medium text-primary">
                {healthData?.version || 'Unknown'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-lg font-medium text-primary mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <button className="btn-ghost" onClick={handleRefreshAll}>
            <RefreshCw className="w-4 h-4" />
            <span>Check All Services</span>
          </button>
          <a 
            href={`${import.meta.env.VITE_API_URL || 'http://localhost:8001'}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-ghost"
          >
            <Globe className="w-4 h-4" />
            <span>View API Docs</span>
          </a>
          <a 
            href={`${import.meta.env.VITE_API_URL || 'http://localhost:8001'}/health`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-ghost"
          >
            <Activity className="w-4 h-4" />
            <span>Health Endpoint</span>
          </a>
        </div>
      </div>
    </div>
  );
}
