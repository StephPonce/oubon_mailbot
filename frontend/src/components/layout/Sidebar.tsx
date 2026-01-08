// 
// SIDEBAR - Glass navigation with Ospra Intelligence branding
// Quick navigation to deep-dive views
// 

import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Package, 
  Megaphone, 
  Mail, 
  BarChart3, 
  Settings,
  Zap,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
}

// Navigation items - just structure, content comes later
const navItems = [
  { 
    path: '/', 
    icon: LayoutDashboard, 
    label: 'Overview',
    description: 'Your command center'
  },
  { 
    path: '/products', 
    icon: Package, 
    label: 'Products',
    description: 'Discovery & management'
  },
  { 
    path: '/ads', 
    icon: Megaphone, 
    label: 'Ads',
    description: 'Campaign management'
  },
  { 
    path: '/emails', 
    icon: Mail, 
    label: 'Emails',
    description: 'Automation & support'
  },
  { 
    path: '/analytics', 
    icon: BarChart3, 
    label: 'Analytics',
    description: 'Deep metrics'
  },
];

const bottomNavItems = [
  { 
    path: '/settings', 
    icon: Settings, 
    label: 'Settings',
    description: 'Configuration'
  },
];

export default function Sidebar({ isCollapsed, onToggle }: SidebarProps) {
  return (
    <aside 
      className={`
        fixed left-0 top-0 h-full z-40
        transition-all duration-300 ease-in-out
        ${isCollapsed ? 'w-[72px]' : 'w-[260px]'}
      `}
    >
      {/* Glass background */}
      <div className="absolute inset-0 bg-[rgba(255,255,255,0.02)] backdrop-blur-xl border-r border-white/[0.06]" />
      
      {/* Content */}
      <div className="relative h-full flex flex-col">
        
        {/* 
            LOGO / BRAND SECTION - Height matches header (h-16 = 64px)
            No divider - clean transition to nav
             */}
        <div className="h-16 px-4 flex items-center">
          <div className={`flex items-center ${isCollapsed ? 'justify-center w-full' : 'gap-3'}`}>
            {/* Logo */}
            <div className="relative flex-shrink-0">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
                <Zap className="w-5 h-5 text-white" />
              </div>
              {/* Breathing pulse effect - Oi is alive */}
              <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-cyan-500 animate-pulse opacity-30" />
            </div>
            
            {/* Brand text */}
            {!isCollapsed && (
              <div className="overflow-hidden">
                <h1 className="text-sm font-semibold text-white truncate">
                  Ospra Intelligence
                </h1>
              </div>
            )}
          </div>
        </div>

        {/* 
            MAIN NAVIGATION
             */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => `
                relative group flex items-center gap-3 px-3 py-2.5 rounded-xl
                transition-all duration-200
                ${isActive 
                  ? 'bg-white/[0.08] text-white shadow-lg shadow-black/20' 
                  : 'text-white/60 hover:bg-white/[0.04] hover:text-white/90'
                }
                ${isCollapsed ? 'justify-center' : ''}
              `}
            >
              {({ isActive }) => (
                <>
                  {/* Active indicator bar */}
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-blue-500 rounded-r-full" />
                  )}
                  
                  <item.icon className={`w-5 h-5 flex-shrink-0 transition-colors ${isActive ? 'text-blue-400' : ''}`} />
                  
                  {!isCollapsed && (
                    <span className="text-sm font-medium truncate">
                      {item.label}
                    </span>
                  )}
                  
                  {/* Tooltip for collapsed state */}
                  {isCollapsed && (
                    <div className="
                      absolute left-full ml-2 px-2 py-1 
                      bg-gray-900 text-white text-xs rounded-md
                      opacity-0 group-hover:opacity-100
                      pointer-events-none transition-opacity
                      whitespace-nowrap z-50
                    ">
                      {item.label}
                    </div>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* 
            BOTTOM NAVIGATION (Settings)
             */}
        <div className="p-3 border-t border-white/[0.06]">
          {bottomNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `
                relative group flex items-center gap-3 px-3 py-2.5 rounded-xl
                transition-all duration-200
                ${isActive 
                  ? 'bg-white/[0.08] text-white' 
                  : 'text-white/60 hover:bg-white/[0.04] hover:text-white/90'
                }
                ${isCollapsed ? 'justify-center' : ''}
              `}
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-blue-500 rounded-r-full" />
                  )}
                  <item.icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-blue-400' : ''}`} />
                  {!isCollapsed && (
                    <span className="text-sm font-medium truncate">
                      {item.label}
                    </span>
                  )}
                  {isCollapsed && (
                    <div className="
                      absolute left-full ml-2 px-2 py-1 
                      bg-gray-900 text-white text-xs rounded-md
                      opacity-0 group-hover:opacity-100
                      pointer-events-none transition-opacity
                      whitespace-nowrap z-50
                    ">
                      {item.label}
                    </div>
                  )}
                </>
              )}
            </NavLink>
          ))}
          
          {/* Collapse toggle */}
          <button
            onClick={onToggle}
            className={`
              w-full flex items-center gap-3 px-3 py-2.5 mt-2 rounded-xl
              text-white/40 hover:bg-white/[0.04] hover:text-white/60
              transition-all duration-200
              ${isCollapsed ? 'justify-center' : ''}
            `}
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? (
              <ChevronRight className="w-5 h-5" />
            ) : (
              <>
                <ChevronLeft className="w-5 h-5" />
                <span className="text-sm truncate">Collapse</span>
              </>
            )}
          </button>
        </div>
      </div>
    </aside>
  );
}
