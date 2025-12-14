import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  Icon: LucideIcon;
  title: string;
  message: string;
  action?: {
    label: string;
    onClick: () => void;
    Icon?: LucideIcon;
  };
}

export function EmptyState({ Icon, title, message, action }: EmptyStateProps) {
  return (
    <div className="glass-card p-12 text-center flex flex-col items-center">
      <div className="w-16 h-16 rounded-full bg-black/20 flex items-center justify-center mb-4">
        <Icon className="w-8 h-8 text-tertiary" />
      </div>
      <h3 className="text-lg font-medium text-primary mb-1">{title}</h3>
      <p className="text-sm text-secondary max-w-xs mx-auto">{message}</p>
      {action && (
        <button className="btn-primary mt-6" onClick={action.onClick}>
          {action.Icon && <action.Icon className="w-4 h-4" />}
          <span>{action.label}</span>
        </button>
      )}
    </div>
  );
}
