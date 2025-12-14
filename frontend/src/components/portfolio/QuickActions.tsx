import React from 'react';
import {
  Search,
  Plus,
  ShoppingCart,
  Settings,
  Sparkles,
  ArrowRight
} from 'lucide-react';

// ... (interfaces remain the same)

const QuickActions: React.FC<QuickActionsProps> = ({ onNavigate, onAddStore }) => {
  const actions: QuickAction[] = [
    {
      id: 'discover',
      title: 'Discover Products',
      description: 'Find trending products with AI',
      icon: Search,
      action: () => onNavigate?.('products'),
    },
    {
      id: 'add-store',
      title: 'Add New Store',
      description: 'Connect another platform',
      icon: Plus,
      action: () => onAddStore?.(),
    },
    {
      id: 'orders',
      title: 'View All Orders',
      description: 'Manage your orders',
      icon: ShoppingCart,
      action: () => onNavigate?.('orders'),
    },
    {
      id: 'ai-settings',
      title: 'AI Settings',
      description: 'Configure AI features',
      icon: Sparkles,
      action: () => onNavigate?.('settings'),
    },
  ];

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-gray-200">Quick Actions</h2>
        <p className="text-sm text-tertiary mt-1">Common tasks and shortcuts.</p>
      </div>

      <div className="space-y-3">
        {actions.map((action) => (
          <button
            key={action.id}
            onClick={action.action}
            className="w-full p-3 rounded-lg bg-glass-white/50 border border-transparent hover:bg-glass-white hover:border-gray-700 transition-all duration-200 text-left group"
          >
            <div className="flex items-center gap-4">
              <div className="p-2 bg-gray-800/70 rounded-lg">
                <action.icon className="w-5 h-5 text-brand-blue" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-gray-200">
                  {action.title}
                </h3>
                <p className="text-xs text-tertiary">
                  {action.description}
                </p>
              </div>
              <ArrowRight className="w-5 h-5 text-tertiary group-hover:text-gray-300 group-hover:translate-x-1 transition-transform" />
            </div>
          </button>
        ))}
      </div>

      <div className="mt-6 pt-6 border-t border-gray-800">
        <a
          href="#"
          onClick={(e) => { e.preventDefault(); onNavigate?.('settings'); }}
          className="text-sm font-medium text-tertiary hover:text-brand-blue transition flex items-center gap-2"
        >
          <Settings className="w-4 h-4" />
          View all settings
        </a>
      </div>
    </div>
  );
};

export default QuickActions;

