import { useState, useEffect } from 'react';
import { Egg, Plane, Bird, Rocket, Crown } from 'lucide-react';
import { subscriptionAPI } from '../../lib/api';

interface TierBadgeProps {
  userId?: number;
  showName?: boolean;
  size?: 'sm' | 'md' | 'lg';
  onClick?: () => void;
}

const tierConfig = {
  nest: {
    icon: Egg,
    color: 'bg-amber-100 text-amber-800 border-amber-200',
    gradient: 'from-amber-500 to-amber-600',
    name: 'Nest',
  },
  flight: {
    icon: Plane,
    color: 'bg-sky-100 text-sky-800 border-sky-200',
    gradient: 'from-sky-400 to-sky-600',
    name: 'Flight',
  },
  soar: {
    icon: Bird,
    color: 'bg-blue-100 text-blue-800 border-cyan-500/20',
    gradient: 'from-blue-500 to-indigo-600',
    name: 'Soar',
  },
  stratosphere: {
    icon: Rocket,
    color: 'bg-purple-100 text-purple-800 border-purple-200',
    gradient: 'from-purple-500 to-violet-600',
    name: 'Stratosphere',
  },
};

const sizeConfig = {
  sm: {
    badge: 'px-2 py-1 text-xs',
    icon: 'w-3 h-3',
  },
  md: {
    badge: 'px-3 py-1.5 text-sm',
    icon: 'w-4 h-4',
  },
  lg: {
    badge: 'px-4 py-2 text-base',
    icon: 'w-5 h-5',
  },
};

export function TierBadge({ userId = 1, showName = true, size = 'md', onClick }: TierBadgeProps) {
  const [tier, setTier] = useState<string>('nest');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTier = async () => {
      try {
        const data = await subscriptionAPI.getCurrentTier(userId);
        setTier(data.tier || 'nest');
      } catch (error) {
        console.error('Failed to fetch tier:', error);
        setTier('nest');
      } finally {
        setLoading(false);
      }
    };

    fetchTier();
  }, [userId]);

  if (loading) {
    return (
      <div className={`animate-pulse bg-gray-200 rounded-full ${sizeConfig[size].badge}`}>
        <span className="invisible">Loading</span>
      </div>
    );
  }

  const config = tierConfig[tier as keyof typeof tierConfig] || tierConfig.nest;
  const Icon = config.icon;
  const sizes = sizeConfig[size];

  return (
    <button
      onClick={onClick}
      className={`
        inline-flex items-center gap-1.5 rounded-full border font-medium
        transition-all hover:shadow-md hover:scale-105
        ${config.color} ${sizes.badge}
        ${onClick ? 'cursor-pointer' : 'cursor-default'}
      `}
    >
      <Icon className={sizes.icon} />
      {showName && <span>{config.name}</span>}
    </button>
  );
}

// Compact version for sidebar
export function TierBadgeCompact({ userId = 1, onClick }: { userId?: number; onClick?: () => void }) {
  const [tier, setTier] = useState<string>('nest');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTier = async () => {
      try {
        const data = await subscriptionAPI.getCurrentTier(userId);
        setTier(data.tier || 'nest');
      } catch (error) {
        setTier('nest');
      } finally {
        setLoading(false);
      }
    };
    fetchTier();
  }, [userId]);

  if (loading) return null;

  const config = tierConfig[tier as keyof typeof tierConfig] || tierConfig.nest;
  const Icon = config.icon;

  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-3 w-full px-4 py-3 rounded-xl
        bg-gradient-to-r ${config.gradient} text-white
        hover:shadow-lg transition-all
      `}
    >
      <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
        <Icon className="w-5 h-5" />
      </div>
      <div className="text-left">
        <div className="text-xs text-white/70">Current Plan</div>
        <div className="font-semibold">{config.name}</div>
      </div>
      {tier !== 'stratosphere' && (
        <div className="ml-auto text-xs bg-white/20 px-2 py-1 rounded-full">
          Upgrade
        </div>
      )}
    </button>
  );
}

export default TierBadge;
