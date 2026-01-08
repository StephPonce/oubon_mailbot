// 
// HEADER - Top bar with notification bell + user dropdown
// 

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  User, 
  CreditCard, 
  HelpCircle, 
  LogOut,
  ChevronDown,
  Settings,
  ExternalLink
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import NotificationBell from './NotificationBell';

interface HeaderProps {
  sidebarCollapsed: boolean;
}

export default function Header({ sidebarCollapsed }: HeaderProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    setDropdownOpen(false);
    logout();
  };

  const handleNavigate = (path: string) => {
    setDropdownOpen(false);
    navigate(path);
  };

  const handleExternalLink = (url: string) => {
    setDropdownOpen(false);
    window.open(url, '_blank');
  };

  const getInitials = () => {
    if (user?.name) {
      return user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    }
    return user?.email?.[0].toUpperCase() || 'U';
  };

  const getTierInfo = () => {
    const tierValue = (user?.tier || (user as any)?.subscription_tier || 'stratosphere').toLowerCase();
    
    const tierMap: Record<string, { label: string; color: string; bgColor: string; dotColor: string }> = {
      nest: { label: 'Nest', color: 'text-gray-400', bgColor: 'bg-gray-500/10', dotColor: 'bg-gray-400' },
      flight: { label: 'Flight', color: 'text-blue-400', bgColor: 'bg-blue-500/10', dotColor: 'bg-blue-400' },
      soar: { label: 'Soar', color: 'text-purple-400', bgColor: 'bg-purple-500/10', dotColor: 'bg-purple-400' },
      stratosphere: { label: 'Stratosphere', color: 'text-amber-400', bgColor: 'bg-amber-500/10', dotColor: 'bg-amber-400' },
    };
    
    return tierMap[tierValue] || tierMap.stratosphere;
  };

  const tierInfo = getTierInfo();

  return (
    <header 
      className={`
        fixed top-0 right-0 h-16 z-30
        transition-all duration-300 ease-in-out
        ${sidebarCollapsed ? 'left-[72px]' : 'left-[260px]'}
      `}
    >
      <div className="absolute inset-0 bg-[rgba(255,255,255,0.02)] backdrop-blur-xl border-b border-white/[0.06]" />
      
      <div className="relative h-full px-6 flex items-center justify-end gap-3">
        
        {/*  Notification Bell */}
        <NotificationBell />
        
        {/* User dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className={`
              flex items-center gap-2 p-1.5 pr-3 rounded-xl
              transition-all duration-200
              ${dropdownOpen 
                ? 'bg-white/[0.08] text-white' 
                : 'hover:bg-white/[0.04] text-white/80 hover:text-white'
              }
            `}
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-xs font-semibold text-white">
              {getInitials()}
            </div>
            
            <div className="hidden sm:block text-left">
              <div className="text-sm font-medium truncate max-w-[120px]">
                {user?.name || 'User'}
              </div>
              <div className={`text-[10px] ${tierInfo.color} flex items-center gap-1`}>
                <span className={`w-1.5 h-1.5 rounded-full ${tierInfo.dotColor}`} />
                {tierInfo.label}
              </div>
            </div>
            
            <ChevronDown className={`w-4 h-4 text-white/40 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
          </button>
          
          {dropdownOpen && (
            <div className="absolute right-0 top-full mt-2 w-64 bg-[#1a1a24] border border-white/[0.08] rounded-xl shadow-xl shadow-black/40 overflow-hidden animate-fade-in">
              <div className="px-4 py-3 border-b border-white/[0.06]">
                <div className="text-sm font-medium text-white truncate">{user?.name || 'User'}</div>
                <div className="text-xs text-white/50 truncate">{user?.email}</div>
                <div className={`mt-2 inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${tierInfo.bgColor} ${tierInfo.color}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${tierInfo.dotColor}`} />
                  {tierInfo.label} Plan
                </div>
              </div>
              
              <div className="p-2">
                <DropdownItem icon={User} label="Profile" onClick={() => handleNavigate('/settings')} description="View and edit your profile" />
                <DropdownItem icon={CreditCard} label="Billing & Subscription" onClick={() => handleNavigate('/settings?tab=subscription')} description="Manage your plan" />
                <DropdownItem icon={Settings} label="Settings" onClick={() => handleNavigate('/settings')} description="App preferences" />
                <DropdownItem icon={HelpCircle} label="Help & Support" onClick={() => handleExternalLink('https://docs.ospra.io')} description="Documentation & FAQs" external />
              </div>
              
              <div className="p-2 border-t border-white/[0.06]">
                <DropdownItem icon={LogOut} label="Sign Out" onClick={handleLogout} danger />
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

interface DropdownItemProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick: () => void;
  description?: string;
  danger?: boolean;
  external?: boolean;
}

function DropdownItem({ icon: Icon, label, onClick, description, danger, external }: DropdownItemProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all duration-150 ${danger ? 'text-red-400 hover:bg-red-500/10' : 'text-white/70 hover:bg-white/[0.06] hover:text-white'}`}
    >
      <Icon className="w-4 h-4 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm flex items-center gap-1">
          {label}
          {external && <ExternalLink className="w-3 h-3 opacity-50" />}
        </div>
        {description && <div className="text-xs text-white/40 truncate">{description}</div>}
      </div>
    </button>
  );
}
