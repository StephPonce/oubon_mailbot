/**
 * OSPRA INTELLIGENCE - MAIN LAYOUT
 * ==================================
 * 
 * Dashboard layout with sidebar navigation and OI chat widget.
 * 
 * @author OspraOS
 * @date December 2024
 */

import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { OiChat } from '../oi/OiChat';

// Navigation items
const navItems = [
  { path: '/dashboard', icon: '[HOME]', label: 'Dashboard' },
  { path: '/products', icon: '[SEARCH]', label: 'Products' },
  { path: '/autopilot', icon: '[AI]', label: 'Auto-Pilot' },
  { path: '/analytics', icon: '[STATS]', label: 'Analytics' },
  { path: '/settings', icon: '[CONFIG]', label: 'Settings' },
];

// Sidebar Navigation Link
function NavItem({ path, icon, label }) {
  return (
    <NavLink
      to={path}
      className={({ isActive }) =>
        `flex items-center px-4 py-3 rounded-xl transition-all ${
          isActive
            ? 'bg-gradient-to-r from-purple-600/20 to-cyan-600/20 border border-purple-500/30 text-white'
            : 'text-white/60 hover:bg-white/5 hover:text-white'
        }`
      }
    >
      <span className="text-xl mr-3">{icon}</span>
      <span className="font-medium">{label}</span>
    </NavLink>
  );
}

// User Menu
function UserMenu({ user, onLogout }) {
  const [isOpen, setIsOpen] = useState(false);

  const tierColors = {
    nest: 'text-gray-400',
    flight: 'text-blue-400',
    soar: 'text-purple-400',
    stratosphere: 'text-yellow-400',
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-all"
      >
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center mr-3">
          <span className="text-white text-sm font-bold">
            {user?.email?.[0]?.toUpperCase() || '?'}
          </span>
        </div>
        <div className="flex-1 text-left">
          <p className="text-white text-sm font-medium truncate">
            {user?.email?.split('@')[0] || 'User'}
          </p>
          <p className={`text-xs ${tierColors[user?.tier] || 'text-gray-400'}`}>
            {user?.tier?.charAt(0).toUpperCase() + user?.tier?.slice(1) || 'Nest'} Plan
          </p>
        </div>
        <span className="text-white/40"></span>
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 right-0 mb-2 bg-slate-800 border border-white/10 rounded-xl shadow-xl overflow-hidden">
          <NavLink
            to="/settings"
            onClick={() => setIsOpen(false)}
            className="block px-4 py-3 text-white/70 hover:bg-white/5 hover:text-white transition-all text-sm"
          >
            [CONFIG] Settings
          </NavLink>
          <NavLink
            to="/upgrade"
            onClick={() => setIsOpen(false)}
            className="block px-4 py-3 text-purple-400 hover:bg-white/5 transition-all text-sm"
          >
            [START] Upgrade Plan
          </NavLink>
          <button
            onClick={onLogout}
            className="block w-full text-left px-4 py-3 text-red-400 hover:bg-red-500/10 transition-all text-sm border-t border-white/10"
          >
             Logout
          </button>
        </div>
      )}
    </div>
  );
}

// Main Layout Component
export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showOiChat, setShowOiChat] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
      {/* Background effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-pulse" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      <div className="relative flex">
        {/* Sidebar */}
        <aside className="fixed left-0 top-0 bottom-0 w-64 bg-slate-900/80 backdrop-blur-xl border-r border-white/10 p-4 flex flex-col">
          {/* Logo */}
          <div className="flex items-center px-4 py-4 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center mr-3">
              <span className="text-xl"></span>
            </div>
            <div>
              <h1 className="text-white font-bold">Ospra</h1>
              <p className="text-white/40 text-xs">Intelligence</p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-2">
            {navItems.map((item) => (
              <NavItem key={item.path} {...item} />
            ))}
          </nav>

          {/* OI Chat Toggle */}
          <button
            onClick={() => setShowOiChat(!showOiChat)}
            className="flex items-center px-4 py-3 rounded-xl bg-gradient-to-r from-purple-600/20 to-cyan-600/20 border border-purple-500/30 text-white hover:from-purple-600/30 hover:to-cyan-600/30 transition-all mb-4"
          >
            <span className="text-xl mr-3">[CHAT]</span>
            <span className="font-medium">Ask Oi</span>
          </button>

          {/* User Menu */}
          <UserMenu user={user} onLogout={handleLogout} />
        </aside>

        {/* Main Content */}
        <main className="flex-1 ml-64 p-8">
          <Outlet />
        </main>
      </div>

      {/* OI Chat Widget */}
      {showOiChat && (
        <div className="fixed bottom-6 right-6 w-96 z-50">
          <OiChat />
          <button
            onClick={() => setShowOiChat(false)}
            className="absolute -top-2 -right-2 w-6 h-6 bg-slate-800 border border-white/10 rounded-full text-white/60 hover:text-white flex items-center justify-center text-xs"
          >
            
          </button>
        </div>
      )}

      {/* Floating OI Button (when chat is hidden) */}
      {!showOiChat && (
        <button
          onClick={() => setShowOiChat(true)}
          className="fixed bottom-6 right-6 w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-600 to-cyan-600 shadow-lg shadow-purple-500/25 flex items-center justify-center hover:scale-110 transition-transform z-50"
        >
          <span className="text-2xl"></span>
        </button>
      )}
    </div>
  );
}

export default Layout;
