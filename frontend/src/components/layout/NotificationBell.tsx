// 
// NOTIFICATION BELL - Header notification center (NO MOCK DATA)
// 

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Bell, 
  TrendingUp, 
  DollarSign, 
  AlertTriangle,
  Package,
  Settings,
  X,
  ExternalLink,
  Sparkles,
  RefreshCw
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Notification {
  id: string;
  type: 'trend' | 'price_drop' | 'alert' | 'product' | 'system' | 'ai';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  action_url?: string;
  action_tab?: string;
}

const notificationIcons: Record<string, { icon: any; color: string; bg: string }> = {
  trend: { icon: TrendingUp, color: 'text-green-400', bg: 'bg-green-500/20' },
  price_drop: { icon: DollarSign, color: 'text-blue-400', bg: 'bg-blue-500/20' },
  alert: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/20' },
  product: { icon: Package, color: 'text-purple-400', bg: 'bg-purple-500/20' },
  system: { icon: Settings, color: 'text-gray-400', bg: 'bg-gray-500/20' },
  ai: { icon: Sparkles, color: 'text-cyan-400', bg: 'bg-cyan-500/20' },
};

function getToken(): string | null {
  return localStorage.getItem('ospra_token') || sessionStorage.getItem('ospra_token');
}

function timeAgo(timestamp: string): string {
  const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000);
  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export default function NotificationBell() {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  
  const unreadCount = notifications.filter(n => !n.read).length;

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  async function fetchNotifications() {
    const token = getToken();
    if (!token) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/notifications`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setNotifications(data.notifications || []);
      } else {
        setError('Failed to load notifications');
        setNotifications([]);
      }
    } catch (err) {
      setError('Connection error');
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  }

  function markAsRead(notificationId: string) {
    setNotifications(prev => prev.map(n => n.id === notificationId ? { ...n, read: true } : n));
    fetch(`${API_BASE}/api/notifications/${notificationId}/read`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${getToken()}` }
    }).catch(() => {});
  }

  function markAllAsRead() {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    fetch(`${API_BASE}/api/notifications/read-all`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${getToken()}` }
    }).catch(() => {});
  }

  function handleNotificationClick(notification: Notification) {
    markAsRead(notification.id);
    setIsOpen(false);
    if (notification.action_url) {
      const url = notification.action_tab 
        ? `${notification.action_url}?tab=${notification.action_tab}` 
        : notification.action_url;
      navigate(url);
    }
  }

  function deleteNotification(e: React.MouseEvent, notificationId: string) {
    e.stopPropagation();
    setNotifications(prev => prev.filter(n => n.id !== notificationId));
    fetch(`${API_BASE}/api/notifications/${notificationId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${getToken()}` }
    }).catch(() => {});
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all"
      >
        <Bell className="w-5 h-5 text-white/70 hover:text-white" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center animate-pulse">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 md:w-96 bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden z-50">
          <div className="flex items-center justify-between p-4 border-b border-white/10">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <Bell className="w-4 h-4 text-cyan-400" />
              Notifications
            </h3>
            <div className="flex items-center gap-2">
              {loading && <RefreshCw className="w-4 h-4 text-white/40 animate-spin" />}
              {unreadCount > 0 && (
                <button onClick={markAllAsRead} className="text-xs text-cyan-400 hover:text-cyan-300">
                  Mark all read
                </button>
              )}
            </div>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {error ? (
              <div className="p-8 text-center">
                <AlertTriangle className="w-10 h-10 text-amber-400/50 mx-auto mb-3" />
                <p className="text-white/50 text-sm">{error}</p>
                <button 
                  onClick={fetchNotifications}
                  className="mt-2 text-xs text-cyan-400 hover:text-cyan-300"
                >
                  Try again
                </button>
              </div>
            ) : notifications.length === 0 ? (
              <div className="p-8 text-center">
                <Bell className="w-10 h-10 text-white/20 mx-auto mb-3" />
                <p className="text-white/50 text-sm">No notifications yet</p>
                <p className="text-white/30 text-xs mt-1">
                  Oi will notify you when something important happens
                </p>
              </div>
            ) : (
              <div className="divide-y divide-white/5">
                {notifications.map((notification) => {
                  const { icon: Icon, color, bg } = notificationIcons[notification.type] || notificationIcons.system;
                  return (
                    <div
                      key={notification.id}
                      onClick={() => handleNotificationClick(notification)}
                      className={`p-4 hover:bg-white/5 cursor-pointer transition-colors group ${!notification.read ? 'bg-cyan-500/5' : ''}`}
                    >
                      <div className="flex gap-3">
                        <div className={`w-10 h-10 rounded-xl ${bg} flex items-center justify-center flex-shrink-0`}>
                          <Icon className={`w-5 h-5 ${color}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <p className={`text-sm font-medium ${notification.read ? 'text-white/70' : 'text-white'}`}>
                              {notification.title}
                            </p>
                            {!notification.read && <span className="w-2 h-2 bg-cyan-400 rounded-full flex-shrink-0 mt-1.5" />}
                          </div>
                          <p className="text-xs text-white/50 mt-0.5 line-clamp-2">{notification.message}</p>
                          <p className="text-xs text-white/30 mt-1">{timeAgo(notification.timestamp)}</p>
                        </div>
                        <button
                          onClick={(e) => deleteNotification(e, notification.id)}
                          className="opacity-0 group-hover:opacity-100 p-1 hover:bg-white/10 rounded-lg"
                        >
                          <X className="w-4 h-4 text-white/40" />
                        </button>
                      </div>
                      {notification.action_url && (
                        <div className="flex items-center gap-1 mt-2 ml-13">
                          <span className="text-xs text-cyan-400/70">Click to view</span>
                          <ExternalLink className="w-3 h-3 text-cyan-400/70" />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="p-3 border-t border-white/10 bg-white/5">
            <button
              onClick={() => { setIsOpen(false); navigate('/settings?tab=notifications'); }}
              className="w-full py-2 text-sm text-white/60 hover:text-white"
            >
              Notification Settings
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
