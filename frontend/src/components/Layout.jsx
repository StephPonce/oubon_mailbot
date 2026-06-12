/**
 * OSPRA INTELLIGENCE - SHARED LAYOUT
 * Floating sidebar design inspired by v0.app
 */

import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Home, Package, Bot, Zap, Settings, LogOut, Activity, Menu, PanelLeftClose, PanelLeft, Store, Brain, Trophy, Sparkles } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useSidebar } from '../hooks/useSidebar';
import { FloatingOiChat } from './FloatingOiChat';

export function Sidebar() {
  const { user, logout } = useAuth();
  const { collapsed, toggle, mobileOpen, setMobileOpen, toggleMobile } = useSidebar();
  const navigate = useNavigate();
  const location = useLocation();
  const currentPath = location.pathname;
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef(null);

  // NOTE: No separate "Winners" entry — Products IS winner-first discovery.
  // Per CLAUDE.md standing rule + user directive: "Ospra by default should be a
  // winners only product discovery based off all signals coded in. being on
  // the products page is proof enough." Don't re-add a Winners tab.
  const navItems = [
    { path: '/dashboard', icon: Home, label: 'Dashboard' },
    { path: '/products', icon: Package, label: 'Products' },
    { path: '/learning', icon: Brain, label: 'Learning' },
    { path: '/autopilot', icon: Bot, label: 'Auto-Pilot' },
    { path: '/actions', icon: Zap, label: 'Actions' },
    { path: '/settings/stores', icon: Store, label: 'Stores' },
    { path: '/scoreboard', icon: Trophy, label: 'Scoreboard' },
    { path: '/upgrade', icon: Sparkles, label: 'Upgrade' },
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
    </>
  );
}

export function PageLayout({ children, title, subtitle }) {
  const { collapsed } = useSidebar();
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-3">
      {/* Static background orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
      </div>

      <Sidebar />

      {/* Main Content - Floating Card */}
      <main className={`max-md:ml-0 max-md:mt-14 ${collapsed ? 'md:ml-[84px]' : 'md:ml-[252px]'} min-h-[calc(100vh-24px)] backdrop-blur-xl bg-black/40 border border-white/10 rounded-2xl p-6 transition-all duration-300`}>
        {(title || subtitle) && (
          <div className="mb-8">
            {title && <h1 className="text-3xl font-bold text-white mb-2">{title}</h1>}
            {subtitle && <p className="text-white/60">{subtitle}</p>}
          </div>
        )}
        {children}
      </main>

      <FloatingOiChat />
    </div>
  );
}

export default PageLayout;
