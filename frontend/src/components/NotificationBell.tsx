import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Bell, Check, AlertTriangle, XCircle, Info } from 'lucide-react';

interface Notification {
  id: string;
  title: string;
  message: string;
  severity: 'success' | 'warning' | 'error' | 'info';
  is_read: boolean;
  created_at: string; // Or Date
}

export const NotificationBell: React.FC = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // ... (all logic remains the same)

  const markAllRead = async () => {
    // Placeholder for API call
    console.log('Mark all read');
    // ... update state or refetch notifications
  };

  const markAsRead = async (id: string) => {
    // Placeholder for API call
    console.log(`Marking ${id} as read`);
    // ... update state or refetch notifications
  };

  const formatTime = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString(); // Simple format for now
  };

  const getSeverityClasses = (severity: string) => {
    switch (severity) {
      case 'success': return { icon: Check, color: 'text-success-green' };
      case 'warning': return { icon: AlertTriangle, color: 'text-yellow-400' };
      case 'error': return { icon: XCircle, color: 'text-red-400' };
      default: return { icon: Info, color: 'text-blue-400' };
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-full text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 block h-2.5 w-2.5 rounded-full bg-brand-blue ring-2 ring-gray-900" />
        )}
      </button>

      {isOpen && (
        <>
          <div 
            className="absolute right-0 mt-3 w-96 bg-gray-950/80 backdrop-blur-xl border border-gray-800 rounded-2xl shadow-2xl z-50 flex flex-col"
            style={{ maxHeight: 'calc(100vh - 80px)' }}
          >
            <div className="flex-shrink-0 p-4 border-b border-gray-800 flex items-center justify-between">
              <h3 className="font-semibold text-lg text-gray-200">Notifications</h3>
              {unreadCount > 0 && (
                <button onClick={markAllRead} disabled={loading} className="text-sm text-brand-blue hover:underline font-medium">
                  {loading ? 'Marking...' : 'Mark all as read'}
                </button>
              )}
            </div>

            <div className="flex-grow overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  <Bell size={32} className="mx-auto mb-2" />
                  <p>No new notifications</p>
                </div>
              ) : (
                notifications.map((n) => {
                  const { icon: Icon, color } = getSeverityClasses(n.severity);
                  return (
                    <div
                      key={n.id}
                      onClick={() => !n.is_read && markAsRead(n.id)}
                      className={`p-4 border-b border-gray-800 cursor-pointer hover:bg-white/5 transition-colors ${!n.is_read ? 'bg-brand-blue/10' : ''}`}
                    >
                      <div className="flex items-start gap-3">
                        <Icon className={`w-5 h-5 mt-0.5 ${color} flex-shrink-0`} />
                        <div className="flex-1">
                          <h4 className="font-semibold text-sm text-gray-200">{n.title}</h4>
                          <p className="text-sm text-gray-400 mt-1">{n.message}</p>
                          <p className="text-xs text-gray-500 mt-2">{formatTime(n.created_at)}</p>
                        </div>
                        {!n.is_read && <div className="w-2.5 h-2.5 rounded-full bg-brand-blue mt-1.5 flex-shrink-0"></div>}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
        </>
      )}
    </div>
  );
};

// ... (formatTime function remains the same)

