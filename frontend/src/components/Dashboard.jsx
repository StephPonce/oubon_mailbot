/**
 * OSPRA INTELLIGENCE - DASHBOARD
 * Floating sidebar design
 */

import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Home, Package, Bot, Zap, Settings, LogOut, TrendingUp, TrendingDown, ShoppingCart, DollarSign, Clock, ChevronRight, Activity, PanelLeftClose, PanelLeft, RefreshCw, Store, Brain } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useSidebar } from '../hooks/useSidebar';
import { api } from '../services/api';
import { FloatingOiChat } from './FloatingOiChat';

function StatCard({ title, value, change, icon: Icon, color = 'purple' }) {
  const colorClasses = {
    purple: 'from-purple-500/20 to-purple-600/10 border-purple-500/30',
    cyan: 'from-cyan-500/20 to-cyan-600/10 border-cyan-500/30',
    green: 'from-green-500/20 to-green-600/10 border-green-500/30',
    yellow: 'from-yellow-500/20 to-yellow-600/10 border-yellow-500/30',
  };

  return (
    <div className={`bg-gradient-to-br ${colorClasses[color]} rounded-2xl border p-6 transition-all hover:scale-[1.02]`}>
      <div className="flex items-center justify-between mb-4">
        <span className="text-white/60 text-sm font-medium">{title}</span>
        <Icon className="w-5 h-5 text-white/60" />
      </div>
      <div className="text-3xl font-bold text-white mb-1">{value}</div>
      {change !== undefined && (
        <div className={`text-sm flex items-center gap-1 ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {Math.abs(change)}% from last week
        </div>
      )}
    </div>
  );
}

function Sidebar({ currentPath }) {
  const { user, logout } = useAuth();
  const { collapsed, toggle } = useSidebar();
  const navigate = useNavigate();
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef(null);

  // NOTE: No separate "Winners" entry — Products IS winner-first discovery.
  // Per CLAUDE.md standing rule + user directive: "Ospra by default should be a
  // winners only product discovery based off all signals coded in. being on
  // the products page is proof enough." Keep this sidebar in sync with
  // Layout.jsx — if you add a route, add it in BOTH places.
  const navItems = [
    { path: '/dashboard', icon: Home, label: 'Dashboard' },
    { path: '/products', icon: Package, label: 'Products' },
    { path: '/learning', icon: Brain, label: 'Learning' },
    { path: '/autopilot', icon: Bot, label: 'Auto-Pilot' },
    { path: '/actions', icon: Zap, label: 'Actions' },
    { path: '/settings/stores', icon: Store, label: 'Stores' },
  ];

  const tierColors = {
    nest: 'bg-gray-500',
    flight: 'bg-blue-500',
    soar: 'bg-purple-500',
    stratosphere: 'bg-gradient-to-r from-purple-500 to-cyan-500',
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    setProfileOpen(false);
    logout();
    navigate('/login');
  };

  return (
    <aside className={`${collapsed ? 'w-[72px]' : 'w-[240px]'} h-[calc(100vh-24px)] fixed left-3 top-3 backdrop-blur-xl bg-black/60 border border-white/10 rounded-2xl flex flex-col z-40 transition-all duration-300`}>
      {/* Header */}
      <div className="p-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center flex-shrink-0">
            <Activity className="w-4 h-4 text-white" />
          </div>
          {!collapsed && (
            <div>
              <h1 className="text-white font-bold text-sm">Ospra</h1>
              <p className="text-white/40 text-xs">Intelligence</p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 space-y-1">
        {navItems.map(item => (
          <Link
            key={item.path}
            to={item.path}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
              currentPath === item.path
                ? 'bg-white/10 text-white'
                : 'text-white/60 hover:bg-white/5 hover:text-white'
            } ${collapsed ? 'justify-center' : ''}`}
            title={collapsed ? item.label : ''}
          >
            <item.icon className="w-5 h-5 flex-shrink-0" />
            {!collapsed && <span className="text-sm font-medium">{item.label}</span>}
          </Link>
        ))}
        
        {/* Collapse Button */}
        <button
          onClick={toggle}
          className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-white/40 hover:bg-white/5 hover:text-white w-full ${collapsed ? 'justify-center' : ''}`}
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          {collapsed ? <PanelLeft className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
          {!collapsed && <span className="text-sm font-medium">Collapse</span>}
        </button>
      </nav>

      {/* Profile Section */}
      <div className="p-2 relative" ref={profileRef}>
        <button
          onClick={() => setProfileOpen(!profileOpen)}
          className={`w-full flex items-center gap-3 p-2 rounded-xl hover:bg-white/5 transition-all ${collapsed ? 'justify-center' : ''}`}
        >
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
            {user?.email?.[0]?.toUpperCase() || 'U'}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0 text-left">
              <p className="text-white text-sm font-medium truncate">{user?.email}</p>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${tierColors[user?.tier] || tierColors.nest}`}></span>
                <span className="text-white/40 text-xs capitalize">{user?.tier || 'Nest'}</span>
              </div>
            </div>
          )}
        </button>

        {/* Dropdown Menu */}
        {profileOpen && (
          <div className={`absolute bottom-full mb-2 ${collapsed ? 'left-2 right-2' : 'left-2 right-2'} bg-slate-800/95 backdrop-blur-xl border border-white/20 rounded-xl shadow-xl overflow-hidden`}>
            <Link
              to="/settings"
              onClick={() => setProfileOpen(false)}
              className="flex items-center gap-3 px-4 py-3 text-white/80 hover:bg-white/10 hover:text-white transition-all"
            >
              <Settings className="w-4 h-4" />
              <span className="text-sm">Settings</span>
            </Link>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-4 py-3 text-red-400 hover:bg-red-500/20 transition-all"
            >
              <LogOut className="w-4 h-4" />
              <span className="text-sm">Sign Out</span>
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}

export function Dashboard() {
  const { user } = useAuth();
  const { collapsed } = useSidebar();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    products: 0,
    orders: 0,
    revenue: 0,
    pendingActions: 0,
  });
  const [autopilotStatus, setAutopilotStatus] = useState(null);
  const [recentActions, setRecentActions] = useState([]);
  // null = fine, 'partial' = some panels failed, 'full' = nothing loaded.
  // Task #51b: failures used to be silently painted as "Inactive"/"No
  // pending actions", which reads as healthy when the API is actually down.
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    setLoadError(null);
    const [statusRes, actionsRes, actionStatsRes] = await Promise.allSettled([
      api.getAutopilotStatus(),
      api.getPendingActions({ limit: 5 }),
      api.getActionStats(),
    ]);

    const failures = [statusRes, actionsRes, actionStatsRes].filter(
      (r) => r.status === 'rejected'
    ).length;
    if (failures > 0) {
      console.error('Dashboard load failures:', failures);
      setLoadError(failures === 3 ? 'full' : 'partial');
    }

    if (statusRes.status === 'fulfilled') setAutopilotStatus(statusRes.value);
    if (actionsRes.status === 'fulfilled') {
      setRecentActions(Array.isArray(actionsRes.value) ? actionsRes.value : []);
    }
    if (actionStatsRes.status === 'fulfilled' || actionsRes.status === 'fulfilled') {
      const actionStats = actionStatsRes.status === 'fulfilled' ? actionStatsRes.value : {};
      const actions = actionsRes.status === 'fulfilled' ? actionsRes.value : null;
      setStats(prev => ({
        ...prev,
        pendingActions: actionStats.pending || actions?.length || 0,
      }));
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-3">
      {/* Static background orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
      </div>

      <Sidebar currentPath="/dashboard" />

      {/* Main Content - Floating Card */}
      <main className={`${collapsed ? 'ml-[84px]' : 'ml-[252px]'} min-h-[calc(100vh-24px)] backdrop-blur-xl bg-black/40 border border-white/10 rounded-2xl p-6 transition-all duration-300`}>
        {loadError && (
          <div className="mb-6 p-4 rounded-xl bg-amber-500/10 border border-amber-400/30 flex items-center justify-between gap-4">
            <p className="text-amber-200 text-sm">
              {loadError === 'full'
                ? "Couldn't reach the server — the data below may be stale."
                : 'Some dashboard data failed to load.'}
            </p>
            <button
              onClick={loadDashboardData}
              disabled={loading}
              className="shrink-0 flex items-center gap-2 px-4 py-1.5 rounded-lg bg-white/10 border border-white/10 text-white text-sm hover:bg-white/20 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Retry
            </button>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard title="Products" value={stats.products || '-'} icon={Package} color="purple" />
          <StatCard title="Orders Today" value={stats.orders || '-'} icon={ShoppingCart} color="cyan" />
          <StatCard title="Revenue" value={stats.revenue ? `$${stats.revenue}` : '-'} icon={DollarSign} color="green" />
          <StatCard title="Pending Actions" value={stats.pendingActions || 0} icon={Clock} color="yellow" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white/5 rounded-2xl border border-white/10 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-white">Auto-Pilot Status</h2>
              <Link to="/autopilot" className="text-purple-400 hover:text-purple-300 text-sm flex items-center gap-1">
                Configure <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
            
            {autopilotStatus ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${autopilotStatus.is_active ? 'bg-green-500' : 'bg-gray-500'}`} />
                  <span className="text-white font-medium">
                    {autopilotStatus.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                
                {autopilotStatus.config && (
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="bg-white/5 rounded-xl p-3">
                      <p className="text-white/40 mb-1">Daily Actions</p>
                      <p className="text-white font-semibold">
                        {autopilotStatus.config.max_daily_actions || 10}
                      </p>
                    </div>
                    <div className="bg-white/5 rounded-xl p-3">
                      <p className="text-white/40 mb-1">Max Spend</p>
                      <p className="text-white font-semibold">
                        ${autopilotStatus.config.max_daily_spend || 100}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-white/40 text-center py-8">
                Loading status...
              </div>
            )}
          </div>

          <div className="bg-white/5 rounded-2xl border border-white/10 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-white">Pending Actions</h2>
              <Link to="/actions" className="text-purple-400 hover:text-purple-300 text-sm flex items-center gap-1">
                View All <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
            
            {recentActions.length > 0 ? (
              <div className="space-y-3">
                {recentActions.slice(0, 5).map((action, i) => (
                  <div key={action.id || i} className="flex items-center gap-3 p-3 bg-white/5 rounded-xl">
                    <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
                      <Zap className="w-4 h-4 text-purple-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-medium truncate">
                        {action.title || action.action_type}
                      </p>
                      <p className="text-white/40 text-xs">
                        {Math.round((action.confidence || 0) * 100)}% confidence
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-white/40 text-center py-8">
                No pending actions
              </div>
            )}
          </div>
        </div>
      </main>

      <FloatingOiChat />
    </div>
  );
}

export default Dashboard;
