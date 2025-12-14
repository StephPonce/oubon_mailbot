import { useState, useEffect } from 'react';
import { Search, Package, Mail, Brain, TrendingUp, AlertCircle } from 'lucide-react';
import { usageAPI, UsageDashboard } from '../../lib/api';

interface UsageMeterProps {
  userId?: number;
  compact?: boolean;
  onLimitReached?: (action: string, suggestion: any) => void;
}

interface UsageItemProps {
  icon: React.ElementType;
  label: string;
  current: number;
  limit: number | null | string;
  color: string;
  compact?: boolean;
}

function UsageItem({ icon: Icon, label, current, limit, color, compact }: UsageItemProps) {
  const isUnlimited = limit === null || limit === 'unlimited' || limit === -1;
  const numericLimit = typeof limit === 'number' ? limit : 0;
  const percentage = isUnlimited ? 0 : Math.min((current / numericLimit) * 100, 100);
  const isNearLimit = !isUnlimited && percentage >= 80;
  const isAtLimit = !isUnlimited && percentage >= 100;

  if (compact) {
    return (
      <div className="flex items-center justify-between py-2">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${color}`} />
          <span className="text-sm text-secondary">{label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${isAtLimit ? 'text-red-600' : isNearLimit ? 'text-amber-600' : 'text-primary'}`}>
            {current}
          </span>
          <span className="text-sm text-tertiary">/</span>
          <span className="text-sm text-tertiary">
            {isUnlimited ? '∞' : limit}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color.replace('text-', 'bg-').replace('500', '100').replace('600', '100')}`}>
            <Icon className={`w-4 h-4 ${color}`} />
          </div>
          <span className="text-sm font-medium text-secondary">{label}</span>
        </div>
        <div className="text-right">
          <span className={`text-lg font-bold ${isAtLimit ? 'text-red-600' : isNearLimit ? 'text-amber-600' : 'text-primary'}`}>
            {current}
          </span>
          <span className="text-sm text-tertiary ml-1">
            / {isUnlimited ? '∞' : limit}
          </span>
        </div>
      </div>
      
      {!isUnlimited && (
        <div className="relative h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`absolute left-0 top-0 h-full rounded-full transition-all duration-500 ${
              isAtLimit ? 'bg-red-500/100' : isNearLimit ? 'bg-amber-500' : color.replace('text-', 'bg-')
            }`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      )}
      
      {isAtLimit && (
        <div className="flex items-center gap-1 text-xs text-red-600">
          <AlertCircle className="w-3 h-3" />
          <span>Limit reached - upgrade for more</span>
        </div>
      )}
    </div>
  );
}

export function UsageMeter({ userId = 1, compact = false, onLimitReached }: UsageMeterProps) {
  const [usage, setUsage] = useState<UsageDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUsage = async () => {
      try {
        const data = await usageAPI.getDashboard(userId);
        setUsage(data);
        
        // Check for any limits reached
        if (onLimitReached && data.usage) {
          Object.entries(data.usage).forEach(([key, value]) => {
            if (value.limit && value.current >= value.limit) {
              onLimitReached(key, {
                tier: data.tier,
                current: value.current,
                limit: value.limit
              });
            }
          });
        }
      } catch (err) {
        console.error('Failed to fetch usage:', err);
        setError('Failed to load usage data');
      } finally {
        setLoading(false);
      }
    };

    fetchUsage();
    
    // Refresh every 30 seconds
    const interval = setInterval(fetchUsage, 30000);
    return () => clearInterval(interval);
  }, [userId, onLimitReached]);

  if (loading) {
    return (
      <div className={`animate-pulse space-y-4 ${compact ? 'p-2' : 'p-4'}`}>
        {[1, 2, 3].map(i => (
          <div key={i} className="h-8 bg-gray-200 rounded" />
        ))}
      </div>
    );
  }

  if (error || !usage) {
    return (
      <div className="text-center py-4 text-tertiary text-sm">
        {error || 'No usage data available'}
      </div>
    );
  }

  const usageItems = [
    {
      icon: Search,
      label: 'AliExpress Searches',
      current: usage.usage?.aliexpress_searches?.current || 0,
      limit: usage.usage?.aliexpress_searches?.limit,
      color: 'text-blue-500',
    },
    {
      icon: Package,
      label: 'Products Discovered',
      current: usage.usage?.products_discovered?.current || 0,
      limit: usage.usage?.products_discovered?.limit,
      color: 'text-green-500',
    },
    {
      icon: Brain,
      label: 'AI Queries',
      current: usage.usage?.ai_queries?.current || 0,
      limit: usage.usage?.ai_queries?.limit,
      color: 'text-purple-500',
    },
    {
      icon: Mail,
      label: 'Email Templates',
      current: usage.usage?.email_templates?.current || 0,
      limit: usage.usage?.email_templates?.limit,
      color: 'text-orange-500',
    },
  ];

  if (compact) {
    return (
      <div className="divide-y divide-gray-100">
        {usageItems.map((item, index) => (
          <UsageItem key={index} {...item} compact />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-primary">Usage This Period</h3>
        <div className="text-xs text-tertiary">
          Resets: {new Date(usage.period?.weekly_resets_at || '').toLocaleDateString()}
        </div>
      </div>
      
      <div className="space-y-5">
        {usageItems.map((item, index) => (
          <UsageItem key={index} {...item} />
        ))}
      </div>
    </div>
  );
}

// Mini version for dashboard cards
export function UsageMeterMini({ userId = 1 }: { userId?: number }) {
  const [usage, setUsage] = useState<UsageDashboard | null>(null);

  useEffect(() => {
    usageAPI.getDashboard(userId)
      .then(setUsage)
      .catch(console.error);
  }, [userId]);

  if (!usage) return null;

  const searches = usage.usage?.aliexpress_searches;
  const products = usage.usage?.products_discovered;
  
  const searchPercent = searches?.limit ? (searches.current / searches.limit) * 100 : 0;
  const productPercent = products?.limit ? (products.current / products.limit) * 100 : 0;

  return (
    <div className="flex gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-tertiary">Searches</span>
          <span className="font-medium">{searches?.current || 0}/{searches?.limit || '∞'}</span>
        </div>
        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div 
            className={`h-full rounded-full ${searchPercent >= 80 ? 'bg-amber-500' : 'bg-cyan-500/100'}`}
            style={{ width: `${Math.min(searchPercent, 100)}%` }}
          />
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-tertiary">Products</span>
          <span className="font-medium">{products?.current || 0}/{products?.limit || '∞'}</span>
        </div>
        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div 
            className={`h-full rounded-full ${productPercent >= 80 ? 'bg-amber-500' : 'bg-green-500/100'}`}
            style={{ width: `${Math.min(productPercent, 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}

export default UsageMeter;
