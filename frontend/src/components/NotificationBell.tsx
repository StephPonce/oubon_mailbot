import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Notification {
  id: number;
  type: string;
  title: string;
  message: string;
  severity: 'success' | 'warning' | 'error' | 'info';
  product_id?: string;
  metadata?: any;
  is_read: boolean;
  created_at: string;
}

export const NotificationBell: React.FC = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchNotifications();
    // Poll for new notifications every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchNotifications = async () => {
    try {
      const response = await axios.get('http://127.0.0.1:8000/api/dashboard/v2/notifications?limit=20');
      setNotifications(response.data.notifications);
      setUnreadCount(response.data.unread_count);
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    }
  };

  const markAsRead = async (notificationId: number) => {
    try {
      await axios.post(`http://127.0.0.1:8000/api/dashboard/v2/notifications/${notificationId}/read`);
      fetchNotifications();
    } catch (error) {
      console.error('Failed to mark as read:', error);
    }
  };

  const markAllRead = async () => {
    setLoading(true);
    try {
      await axios.post('http://127.0.0.1:8000/api/dashboard/v2/notifications/mark-all-read');
      fetchNotifications();
    } catch (error) {
      console.error('Failed to mark all read:', error);
    } finally {
      setLoading(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'success': return 'text-green-600 bg-green-50';
      case 'warning': return 'text-yellow-600 bg-yellow-50';
      case 'error': return 'text-red-600 bg-red-50';
      default: return 'text-blue-600 bg-blue-50';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'success': return '✅';
      case 'warning': return '⚠️';
      case 'error': return '❌';
      default: return 'ℹ️';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="relative">
      {/* Bell Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-full hover:bg-gray-100 transition"
      >
        <span className="text-2xl">🔔</span>
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 bg-white rounded-lg shadow-xl border border-gray-200 z-50">
          {/* Header */}
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <h3 className="font-bold text-lg">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                disabled={loading}
                className="text-sm text-blue-600 hover:text-blue-800 font-semibold"
              >
                {loading ? 'Marking...' : 'Mark all read'}
              </button>
            )}
          </div>

          {/* Notifications List */}
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                <p className="text-4xl mb-2">🔕</p>
                <p>No notifications yet</p>
              </div>
            ) : (
              notifications.map((notification) => (
                <div
                  key={notification.id}
                  onClick={() => !notification.is_read && markAsRead(notification.id)}
                  className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition ${
                    !notification.is_read ? 'bg-blue-50' : ''
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {/* Icon */}
                    <div className={`p-2 rounded-full ${getSeverityColor(notification.severity)}`}>
                      <span className="text-lg">{getSeverityIcon(notification.severity)}</span>
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h4 className={`font-semibold text-sm ${!notification.is_read ? 'text-gray-900' : 'text-gray-600'}`}>
                          {notification.title}
                        </h4>
                        <span className="text-xs text-gray-400 whitespace-nowrap">
                          {formatTime(notification.created_at)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{notification.message}</p>

                      {/* Link to Shopify if available */}
                      {notification.metadata?.shopify_url && (
                        <a
                          href={notification.metadata.shopify_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-600 hover:underline mt-2 inline-block"
                          onClick={(e) => e.stopPropagation()}
                        >
                          View on Shopify →
                        </a>
                      )}
                    </div>

                    {/* Unread indicator */}
                    {!notification.is_read && (
                      <div className="w-2 h-2 rounded-full bg-blue-600"></div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="p-3 border-t border-gray-200 text-center">
              <button
                onClick={() => setIsOpen(false)}
                className="text-sm text-gray-600 hover:text-gray-800"
              >
                Close
              </button>
            </div>
          )}
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
};
