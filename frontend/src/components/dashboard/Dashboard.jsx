/**
 * OSPRA INTELLIGENCE - DASHBOARD COMPONENT
 * =========================================
 * 
 * Main dashboard with stats, activity, and quick actions.
 * 
 * @author OspraOS
 * @date December 2024
 */

import React, { useState, useEffect } from 'react';
import { useAuth, useAuthenticatedFetch } from '../../hooks/useAuth';
import { Link } from 'react-router-dom';

// Stat Card Component
function StatCard({ title, value, change, icon, trend }) {
  const isPositive = trend === 'up';
  
  return (
    <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:bg-white/10 transition-all">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-white/60 text-sm">{title}</p>
          <p className="text-2xl font-bold text-white mt-1">{value}</p>
          {change && (
            <p className={`text-sm mt-2 ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
              {isPositive ? '↑' : '↓'} {change}
            </p>
          )}
        </div>
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/20 to-cyan-500/20 border border-white/10 flex items-center justify-center">
          <span className="text-xl">{icon}</span>
        </div>
      </div>
    </div>
  );
}

// Activity Item Component
function ActivityItem({ action, time, status }) {
  const statusColors = {
    success: 'bg-green-500',
    pending: 'bg-yellow-500',
    failed: 'bg-red-500',
  };

  return (
    <div className="flex items-center py-3 border-b border-white/5 last:border-0">
      <div className={`w-2 h-2 rounded-full ${statusColors[status] || 'bg-gray-500'} mr-3`} />
      <div className="flex-1">
        <p className="text-white/90 text-sm">{action}</p>
        <p className="text-white/40 text-xs">{time}</p>
      </div>
    </div>
  );
}

// Quick Action Button
function QuickActionButton({ icon, label, to, onClick }) {
  const Component = to ? Link : 'button';
  
  return (
    <Component
      to={to}
      onClick={onClick}
      className="flex flex-col items-center p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 hover:border-purple-500/30 transition-all group"
    >
      <span className="text-2xl mb-2 group-hover:scale-110 transition-transform">{icon}</span>
      <span className="text-white/70 text-xs text-center">{label}</span>
    </Component>
  );
}

// Main Dashboard Component
export function Dashboard() {
  const { user } = useAuth();
  const { get } = useAuthenticatedFetch();
  
  const [stats, setStats] = useState({
    revenue: '$0',
    orders: '0',
    products: '0',
    conversion: '0%',
  });
  
  const [activities, setActivities] = useState([]);
  const [autopilotStatus, setAutopilotStatus] = useState(null);

  // Fetch dashboard data
  useEffect(() => {
    async function fetchData() {
      try {
        // Fetch autopilot status
        const autopilot = await get('/api/autopilot/status');
        setAutopilotStatus(autopilot);

        // Fetch recent activities (from action queue)
        const actions = await get('/api/ai/actions');
        if (Array.isArray(actions)) {
          setActivities(actions.slice(0, 5).map(a => ({
            action: a.title || a.action_type,
            time: new Date(a.created_at).toLocaleString(),
            status: a.status === 'completed' ? 'success' : a.status === 'pending' ? 'pending' : 'failed',
          })));
        }

        // Placeholder stats - will be replaced with Shopify data
        setStats({
          revenue: '$2,450',
          orders: '34',
          products: '12',
          conversion: '3.2%',
        });
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      }
    }

    fetchData();
  }, []);

  const tierBadgeColors = {
    nest: 'from-gray-500 to-gray-600',
    flight: 'from-blue-500 to-blue-600',
    soar: 'from-purple-500 to-purple-600',
    stratosphere: 'from-yellow-500 to-orange-500',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Welcome back{user?.email ? `, ${user.email.split('@')[0]}` : ''}! 
          </h1>
          <p className="text-white/60 mt-1">Here's what's happening with your store</p>
        </div>
        
        <div className={`px-4 py-2 rounded-full bg-gradient-to-r ${tierBadgeColors[user?.tier] || tierBadgeColors.nest} text-white text-sm font-medium`}>
          {user?.tier?.charAt(0).toUpperCase() + user?.tier?.slice(1) || 'Nest'} Plan
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Revenue (This Week)" value={stats.revenue} change="12% vs last week" trend="up" icon="[PRICE]" />
        <StatCard title="Orders" value={stats.orders} change="8% vs last week" trend="up" icon="[PACKAGE]" />
        <StatCard title="Active Products" value={stats.products} icon="" />
        <StatCard title="Conversion Rate" value={stats.conversion} change="0.3% vs last week" trend="up" icon="[TREND]" />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Autopilot Status */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-semibold">[AI] Auto-Pilot</h2>
            <div className={`w-3 h-3 rounded-full ${autopilotStatus?.is_active ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`} />
          </div>
          
          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-white/60">Status</span>
              <span className={autopilotStatus?.is_active ? 'text-green-400' : 'text-white/40'}>
                {autopilotStatus?.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-white/60">Actions Today</span>
              <span className="text-white">{autopilotStatus?.actions_today || 0}</span>
            </div>
          </div>
          
          <Link to="/autopilot" className="mt-4 block w-full py-2 text-center rounded-xl bg-white/5 border border-white/10 text-white/70 hover:bg-white/10 hover:text-white transition-all text-sm">
            Configure Auto-Pilot →
          </Link>
        </div>

        {/* Recent Activity */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
          <h2 className="text-white font-semibold mb-4">[LIST] Recent Activity</h2>
          {activities.length > 0 ? (
            <div>{activities.map((activity, i) => <ActivityItem key={i} {...activity} />)}</div>
          ) : (
            <p className="text-white/40 text-sm text-center py-8">No recent activity</p>
          )}
        </div>

        {/* Quick Actions */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
          <h2 className="text-white font-semibold mb-4">[FAST] Quick Actions</h2>
          <div className="grid grid-cols-2 gap-3">
            <QuickActionButton icon="[SEARCH]" label="Find Products" to="/products" />
            <QuickActionButton icon="[START]" label="Deploy Product" to="/products?action=deploy" />
            <QuickActionButton icon="[STATS]" label="View Analytics" to="/analytics" />
            <QuickActionButton icon="[CONFIG]" label="Settings" to="/settings" />
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
