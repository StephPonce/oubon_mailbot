import React from 'react';
import {
  Search,
  Plus,
  ShoppingCart,
  Settings,
  Sparkles,
  ArrowRight
} from 'lucide-react';

interface QuickAction {
  id: string;
  title: string;
  description: string;
  icon: React.ElementType;
  color: string;
  bgColor: string;
  borderColor: string;
  action: () => void;
}

interface QuickActionsProps {
  onNavigate?: (page: string) => void;
  onAddStore?: () => void;
}

const QuickActions: React.FC<QuickActionsProps> = ({ onNavigate, onAddStore }) => {
  const actions: QuickAction[] = [
    {
      id: 'discover',
      title: 'Discover Products',
      description: 'Find trending products with AI',
      icon: Search,
      color: 'text-blue-400',
      bgColor: 'bg-blue-500/10',
      borderColor: 'border-blue-500/50',
      action: () => {
        if (onNavigate) {
          onNavigate('products');
        }
      }
    },
    {
      id: 'add-store',
      title: 'Add New Store',
      description: 'Connect another platform',
      icon: Plus,
      color: 'text-purple-400',
      bgColor: 'bg-purple-500/10',
      borderColor: 'border-purple-500/50',
      action: () => {
        if (onAddStore) {
          onAddStore();
        }
      }
    },
    {
      id: 'orders',
      title: 'View All Orders',
      description: 'Manage your orders',
      icon: ShoppingCart,
      color: 'text-green-400',
      bgColor: 'bg-green-500/10',
      borderColor: 'border-green-500/50',
      action: () => {
        if (onNavigate) {
          onNavigate('orders');
        }
      }
    },
    {
      id: 'ai-settings',
      title: 'AI Settings',
      description: 'Configure AI features',
      icon: Sparkles,
      color: 'text-yellow-400',
      bgColor: 'bg-yellow-500/10',
      borderColor: 'border-yellow-500/50',
      action: () => {
        if (onNavigate) {
          onNavigate('analytics');
        }
      }
    }
  ];

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-xl font-bold text-white">Quick Actions</h2>
        <p className="text-sm text-gray-400 mt-1">Common tasks and shortcuts</p>
      </div>

      {/* Action Cards */}
      <div className="space-y-3">
        {actions.map((action) => {
          const Icon = action.icon;

          return (
            <button
              key={action.id}
              onClick={action.action}
              className={`w-full p-4 rounded-lg border ${action.borderColor} ${action.bgColor} hover:bg-opacity-100 transition-all duration-200 text-left group hover:shadow-lg hover:scale-105`}
            >
              <div className="flex items-start gap-3">
                {/* Icon */}
                <div className={`p-2 rounded-lg ${action.bgColor}`}>
                  <Icon className={`w-5 h-5 ${action.color}`} />
                </div>

                {/* Content */}
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-medium text-white group-hover:text-blue-400 transition">
                      {action.title}
                    </h3>
                    <ArrowRight className="w-4 h-4 text-gray-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {action.description}
                  </p>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Additional Stats */}
      <div className="mt-6 pt-6 border-t border-gray-700">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase">AI Credits</p>
            <p className="text-lg font-bold text-white mt-1">2,450</p>
            <p className="text-xs text-green-400 mt-1">+120 this week</p>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase">Active Tasks</p>
            <p className="text-lg font-bold text-white mt-1">7</p>
            <p className="text-xs text-blue-400 mt-1">3 pending</p>
          </div>
        </div>
      </div>

      {/* Help Link */}
      <div className="mt-4 pt-4 border-t border-gray-700">
        <a
          href="#"
          className="text-sm text-blue-400 hover:text-blue-300 transition flex items-center gap-2"
        >
          <Settings className="w-4 h-4" />
          View all settings
        </a>
      </div>
    </div>
  );
};

export default QuickActions;
