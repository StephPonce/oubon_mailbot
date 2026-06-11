/**
 * OSPRA INTELLIGENCE - SETTINGS
 * Floating sidebar design
 */

import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Home, Package, Bot, Zap, Settings as SettingsIcon, LogOut,
  User, CreditCard, Bell, Check, Activity, Loader2, Menu, PanelLeftClose, PanelLeft,
  Shield, Download, Trash2, AlertTriangle
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useSidebar } from '../hooks/useSidebar';
import { useToast } from '../hooks/useToast';
import { api } from '../services/api';
import { FloatingOiChat } from './FloatingOiChat';

function Sidebar({ currentPath }) {
  const { user, logout } = useAuth();
  const { collapsed, toggle, mobileOpen, setMobileOpen, toggleMobile } = useSidebar();
  const navigate = useNavigate();
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef(null);

  const navItems = [
    { path: '/dashboard', icon: Home, label: 'Dashboard' },
    { path: '/products', icon: Package, label: 'Products' },
    { path: '/autopilot', icon: Bot, label: 'Auto-Pilot' },
    { path: '/actions', icon: Zap, label: 'Actions' },
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
    <>
      {/* Mobile hamburger — sidebar is off-canvas below md (task #51f) */}
      <button
        onClick={toggleMobile}
        className="md:hidden fixed top-5 left-5 z-50 p-2 rounded-xl bg-black/60 border border-white/10 backdrop-blur-xl text-white"
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5" />
      </button>
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/60 z-40"
          onClick={() => setMobileOpen(false)}
        />
      )}
    <aside className={`w-[240px] ${collapsed ? 'md:w-[72px]' : 'md:w-[240px]'} h-[calc(100vh-24px)] fixed left-3 top-3 backdrop-blur-xl bg-black/60 border border-white/10 rounded-2xl flex flex-col z-40 max-md:z-50 transition-all duration-300 ${mobileOpen ? 'translate-x-0' : 'max-md:-translate-x-[110%]'}`}>
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

      {/* Navigation — clicking any link also closes the mobile menu */}
      <nav className="flex-1 px-2 space-y-1" onClick={() => setMobileOpen(false)}>
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
        
        {/* Collapse Button — collapse only matters at md+ */}
        <button
          onClick={(e) => { e.stopPropagation(); toggle(); }}
          className={`max-md:hidden flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-white/40 hover:bg-white/5 hover:text-white w-full ${collapsed ? 'justify-center' : ''}`}
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
              <SettingsIcon className="w-4 h-4" />
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
    </>
  );
}

/**
 * Data & Privacy panel.
 *
 * Required by Shopify Partner App approval (see
 * docs/guides/SHOPIFY_PARTNER_APP_APPROVAL_READINESS.md §4): users must
 * be able to self-serve export and deletion. The buttons hit
 * /api/account/data-export and /api/account/data-delete which call the
 * SAME backend service the GDPR webhooks call, so behaviour matches what
 * Shopify's reviewer tests via webhook ping.
 */
function DataPrivacySection() {
  const [summary, setSummary] = React.useState(null);
  const [loadingSummary, setLoadingSummary] = React.useState(true);
  const [exporting, setExporting] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [confirmEmail, setConfirmEmail] = React.useState('');
  const [deleteStores, setDeleteStores] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [done, setDone] = React.useState(null);

  React.useEffect(() => {
    let cancelled = false;
    api.getDataSummary()
      .then((res) => { if (!cancelled) setSummary(res); })
      .catch(() => { if (!cancelled) setSummary(null); })
      .finally(() => { if (!cancelled) setLoadingSummary(false); });
    return () => { cancelled = true; };
  }, []);

  const handleExport = async () => {
    setError(null);
    setExporting(true);
    try {
      const payload = await api.exportMyData();
      // Trigger a JSON download in the browser. Doing it client-side
      // keeps the backend stateless — no temp files, no S3.
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      a.download = `ospra-data-export-${stamp}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Export failed: ${e?.message || 'unknown error'}`);
    } finally {
      setExporting(false);
    }
  };

  const handleDelete = async () => {
    setError(null);
    setDeleting(true);
    try {
      const res = await api.deleteMyData({
        confirmEmail,
        deleteConnectedStores: deleteStores,
      });
      setDone(res?.message || 'Your data has been deleted.');
      setConfirmOpen(false);
    } catch (e) {
      setError(`Deletion failed: ${e?.message || 'unknown error'}`);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <SettingsSection title="Data & Privacy" icon={Shield}>
      <div className="space-y-5">
        {/* What we store */}
        <div>
          <h3 className="text-white font-medium mb-2 text-sm">What we store</h3>
          {loadingSummary ? (
            <p className="text-white/40 text-xs flex items-center gap-2">
              <Loader2 className="w-3 h-3 animate-spin" /> Counting your records…
            </p>
          ) : summary ? (
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-xl bg-white/5 border border-white/10 p-3">
                <p className="text-2xl text-white font-semibold">
                  {summary.record_counts?.email_followups_found ?? 0}
                </p>
                <p className="text-white/40 text-xs">Email follow-ups</p>
              </div>
              <div className="rounded-xl bg-white/5 border border-white/10 p-3">
                <p className="text-2xl text-white font-semibold">
                  {summary.record_counts?.orders_found ?? 0}
                </p>
                <p className="text-white/40 text-xs">Orders</p>
              </div>
              <div className="rounded-xl bg-white/5 border border-white/10 p-3">
                <p className="text-2xl text-white font-semibold">
                  {summary.store_count ?? 0}
                </p>
                <p className="text-white/40 text-xs">Connected stores</p>
              </div>
            </div>
          ) : (
            <p className="text-white/40 text-xs">Could not load record counts.</p>
          )}
        </div>

        {/* What we keep, what we don't, retention */}
        {summary && (
          <details className="text-xs">
            <summary className="text-white/60 cursor-pointer hover:text-white">
              Full data-handling summary
            </summary>
            <div className="mt-3 space-y-3 text-white/60">
              <div>
                <p className="text-white/80 font-medium mb-1">We store:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  {(summary.what_we_store || []).map((line, i) => (
                    <li key={`s-${i}`}>{line}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-white/80 font-medium mb-1">We do NOT store:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  {(summary.what_we_dont_store || []).map((line, i) => (
                    <li key={`n-${i}`}>{line}</li>
                  ))}
                </ul>
              </div>
              {summary.retention_summary && (
                <div>
                  <p className="text-white/80 font-medium mb-1">Retention:</p>
                  <ul className="list-disc list-inside space-y-0.5">
                    {Object.entries(summary.retention_summary).map(([k, v]) => (
                      <li key={k}>
                        <span className="text-white/80">{k.replace(/_/g, ' ')}:</span>{' '}
                        {v}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="pt-2">
                Full policy:{' '}
                <a
                  href="https://ospra.os/legal/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:underline"
                >
                  ospra.os/legal/privacy
                </a>
              </p>
            </div>
          </details>
        )}

        {/* Export */}
        <div className="flex items-center justify-between gap-4 pt-2 border-t border-white/10">
          <div>
            <p className="text-white text-sm font-medium">Download my data</p>
            <p className="text-white/40 text-xs">
              JSON export of every record tied to your email.
            </p>
          </div>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="px-4 py-2 rounded-xl bg-white/10 border border-white/10 text-white hover:bg-white/15 transition-all flex items-center gap-2 text-sm disabled:opacity-50"
          >
            {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {exporting ? 'Preparing…' : 'Export'}
          </button>
        </div>

        {/* Delete */}
        <div className="pt-2 border-t border-white/10">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-white text-sm font-medium">Delete my data</p>
              <p className="text-white/40 text-xs">
                Removes follow-ups and order rows. Optionally also disconnects
                and wipes data for stores you've linked.
              </p>
            </div>
            {!confirmOpen ? (
              <button
                onClick={() => setConfirmOpen(true)}
                className="px-4 py-2 rounded-xl bg-red-500/20 border border-red-500/30 text-red-300 hover:bg-red-500/30 transition-all flex items-center gap-2 text-sm"
              >
                <Trash2 className="w-4 h-4" />
                Delete
              </button>
            ) : null}
          </div>

          {confirmOpen && (
            <div className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 space-y-3">
              <div className="flex items-start gap-2 text-red-200 text-sm">
                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <p>
                  This deletes the data we hold about you. Your account record
                  itself is removed by support after a manual confirmation —
                  email <span className="font-mono">support@ospra.os</span>.
                </p>
              </div>
              <label className="block text-xs text-white/60">
                Type your email (<span className="font-mono">{summary?.user?.email || ''}</span>) to confirm:
              </label>
              <input
                type="email"
                value={confirmEmail}
                onChange={(e) => setConfirmEmail(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-white text-sm focus:border-red-500/50 focus:outline-none"
                placeholder="you@example.com"
              />
              <label className="flex items-center gap-2 text-xs text-white/70">
                <input
                  type="checkbox"
                  checked={deleteStores}
                  onChange={(e) => setDeleteStores(e.target.checked)}
                  className="accent-red-500"
                />
                Also disconnect and wipe my connected stores ({summary?.store_count ?? 0})
              </label>
              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={handleDelete}
                  disabled={deleting || !confirmEmail}
                  className="px-3 py-1.5 rounded-lg bg-red-500/30 border border-red-500/50 text-red-100 hover:bg-red-500/40 transition-all flex items-center gap-2 text-sm disabled:opacity-50"
                >
                  {deleting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                  {deleting ? 'Deleting…' : 'Confirm delete'}
                </button>
                <button
                  onClick={() => { setConfirmOpen(false); setConfirmEmail(''); }}
                  disabled={deleting}
                  className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white/70 hover:bg-white/10 text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {done && (
            <p className="mt-3 text-green-400 text-sm flex items-center gap-2">
              <Check className="w-4 h-4" /> {done}
            </p>
          )}
          {error && (
            <p className="mt-3 text-red-400 text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" /> {error}
            </p>
          )}
        </div>
      </div>
    </SettingsSection>
  );
}


function SettingsSection({ title, icon: Icon, children }) {
  return (
    <div className="bg-white/5 rounded-2xl border border-white/10 p-6 mb-6">
      <div className="flex items-center gap-3 mb-4">
        <Icon className="w-5 h-5 text-white/60" />
        <h2 className="text-lg font-semibold text-white">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function TierBadge({ tier }) {
  const tierInfo = {
    nest: { color: 'gray', label: 'Nest', price: 'Free' },
    flight: { color: 'blue', label: 'Flight', price: '$29/mo' },
    soar: { color: 'purple', label: 'Soar', price: '$79/mo' },
    stratosphere: { color: 'cyan', label: 'Stratosphere', price: '$199/mo' },
  };

  const t = tierInfo[tier] || tierInfo.nest;

  const colors = {
    gray: 'bg-gray-500/20 border-gray-500/30 text-gray-400',
    blue: 'bg-blue-500/20 border-blue-500/30 text-blue-400',
    purple: 'bg-purple-500/20 border-purple-500/30 text-purple-400',
    cyan: 'bg-cyan-500/20 border-cyan-500/30 text-cyan-400',
  };

  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl border ${colors[t.color]}`}>
      <span className="font-semibold">{t.label}</span>
      <span className="text-white/40">-</span>
      <span>{t.price}</span>
    </div>
  );
}

export function Settings() {
  const { user, logout } = useAuth();
  const { collapsed } = useSidebar();
  const navigate = useNavigate();
  const toast = useToast();
  
  const [profile, setProfile] = useState({ email: '' });
  const [notifications, setNotifications] = useState({
    email_notifications: true,
    notify_new_products: true,
    notify_price_drops: false,
    notify_trend_spikes: false,
  });
  const [savingNotifications, setSavingNotifications] = useState(false);
  const [notificationsSaved, setNotificationsSaved] = useState(false);
  const [upgrading, setUpgrading] = useState(null);

  useEffect(() => {
    loadProfile();
    loadSettings();
  }, []);

  const loadProfile = async () => {
    try {
      const response = await api.getProfile();
      if (response.success && response.profile) {
        setProfile(response.profile);
      }
    } catch (error) {
      console.error('Failed to load profile:', error);
    }
  };

  const loadSettings = async () => {
    try {
      const response = await api.getSettings();
      if (response.success && response.settings) {
        setNotifications({
          email_notifications: response.settings.email_notifications ?? true,
          notify_new_products: response.settings.notify_new_products ?? true,
          notify_price_drops: response.settings.notify_price_drops ?? false,
          notify_trend_spikes: response.settings.notify_trend_spikes ?? false,
        });
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  };

  const handleNotificationToggle = async (key) => {
    const newValue = !notifications[key];
    const newNotifications = { ...notifications, [key]: newValue };
    setNotifications(newNotifications);
    
    setSavingNotifications(true);
    try {
      await api.updateSettings({ [key]: newValue });
      setNotificationsSaved(true);
      setTimeout(() => setNotificationsSaved(false), 2000);
    } catch (error) {
      console.error('Failed to save notification setting:', error);
      setNotifications(notifications);
    } finally {
      setSavingNotifications(false);
    }
  };

  const handleUpgrade = async (tier) => {
    if (user?.tier === tier) return;
    
    setUpgrading(tier);
    try {
      const response = await api.upgradeTier(tier);
      if (response.checkout_url) {
        // Production paid path: tier is granted by the payment webhook after
        // checkout, so hand the user off to LemonSqueezy. Don't reset the
        // spinner — we're leaving the page.
        window.location.assign(response.checkout_url);
        return;
      }
      if (response.success) {
        // Dev/free path: tier changed directly.
        window.location.reload();
      }
    } catch (error) {
      console.error('Failed to upgrade:', error);
      toast.error('Failed to upgrade. Please try again.');
    } finally {
      setUpgrading(null);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const tierPrices = {
    flight: '$29/mo',
    soar: '$79/mo',
    stratosphere: '$199/mo',
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-3">
      {/* Static background orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
      </div>

      <Sidebar currentPath="/settings" />

      {/* Main Content - Floating Card */}
      <main className={`max-md:ml-0 max-md:mt-14 ${collapsed ? 'md:ml-[84px]' : 'md:ml-[252px]'} min-h-[calc(100vh-24px)] backdrop-blur-xl bg-black/40 border border-white/10 rounded-2xl p-6 transition-all duration-300`}>
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Settings</h1>
          <p className="text-white/60">Manage your account and preferences</p>
        </div>

        <div className="max-w-2xl">
          {/* Account Section */}
          <SettingsSection title="Account" icon={User}>
            <div className="space-y-4">
              <div>
                <label className="block text-white/60 text-sm mb-1">Email</label>
                <p className="text-white">{user?.email}</p>
              </div>
              <div>
                <label className="block text-white/60 text-sm mb-1">User ID</label>
                <p className="text-white/60 font-mono text-sm">{user?.user_id}</p>
              </div>
            </div>
          </SettingsSection>

          {/* Subscription Section */}
          <SettingsSection title="Subscription" icon={CreditCard}>
            <div className="space-y-4">
              <div>
                <label className="block text-white/60 text-sm mb-2">Current Plan</label>
                <TierBadge tier={user?.tier || 'nest'} />
              </div>
              
              <div className="pt-4 border-t border-white/10">
                <h3 className="text-white font-medium mb-3">Upgrade Your Plan</h3>
                <div className="space-y-3">
                  {['flight', 'soar', 'stratosphere'].map((tier) => {
                    const isCurrentTier = user?.tier === tier;
                    const isUpgrading = upgrading === tier;
                    
                    return (
                      <button
                        key={tier}
                        onClick={() => handleUpgrade(tier)}
                        disabled={isCurrentTier || upgrading}
                        className={`w-full p-4 rounded-xl border text-left transition-all flex items-center justify-between ${
                          isCurrentTier
                            ? 'bg-purple-500/20 border-purple-500/30 cursor-default'
                            : 'bg-white/5 border-white/10 hover:border-purple-500/30 hover:bg-white/10'
                        } ${upgrading && !isUpgrading ? 'opacity-50' : ''}`}
                      >
                        <div>
                          <span className="text-white font-medium capitalize">{tier}</span>
                          <span className="text-white/40 ml-2">{tierPrices[tier]}</span>
                        </div>
                        {isCurrentTier ? (
                          <span className="text-purple-400 text-sm flex items-center gap-1">
                            <Check className="w-4 h-4" /> Current
                          </span>
                        ) : isUpgrading ? (
                          <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                        ) : (
                          <span className="text-purple-400 text-sm">Upgrade</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </SettingsSection>

          {/* Notifications Section */}
          <SettingsSection title="Notifications" icon={Bell}>
            <div className="space-y-4">
              {[
                { key: 'email_notifications', label: 'Email notifications', desc: 'Receive emails about important updates' },
                { key: 'notify_new_products', label: 'New product alerts', desc: 'Get notified when trending products are found' },
                { key: 'notify_price_drops', label: 'Price drop alerts', desc: 'Get notified when supplier prices drop' },
                { key: 'notify_trend_spikes', label: 'Trend spike alerts', desc: 'Get notified when products start trending' },
              ].map(({ key, label, desc }) => (
                <div key={key} className="flex items-center justify-between">
                  <div>
                    <span className="text-white">{label}</span>
                    <p className="text-white/40 text-xs">{desc}</p>
                  </div>
                  <button
                    onClick={() => handleNotificationToggle(key)}
                    disabled={savingNotifications}
                    className={`w-12 h-6 rounded-full transition-all ${
                      notifications[key] ? 'bg-green-500' : 'bg-white/20'
                    }`}
                  >
                    <div className={`w-5 h-5 rounded-full bg-white transition-transform ${
                      notifications[key] ? 'translate-x-6' : 'translate-x-0.5'
                    }`} />
                  </button>
                </div>
              ))}
              
              {notificationsSaved && (
                <p className="text-green-400 text-sm flex items-center gap-1">
                  <Check className="w-3 h-3" /> Settings saved
                </p>
              )}
            </div>
          </SettingsSection>

          {/* Data & Privacy — Shopify Partner App approval requirement */}
          <DataPrivacySection />

          {/* Danger Zone */}
          <SettingsSection title="Danger Zone" icon={LogOut}>
            <button
              onClick={handleLogout}
              className="w-full py-3 rounded-xl bg-red-500/20 border border-red-500/30 text-red-400 font-medium hover:bg-red-500/30 transition-all flex items-center justify-center gap-2"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </SettingsSection>
        </div>
      </main>

      <FloatingOiChat />
    </div>
  );
}

export default Settings;
