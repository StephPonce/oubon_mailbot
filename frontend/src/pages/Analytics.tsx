// 
// ANALYTICS - Deep Metrics (Placeholder)
// Detailed performance analytics and AI insights
// 

import { BarChart3, Construction } from 'lucide-react';

export default function Analytics() {
  return (
    <div className="animate-fade-in">
      <div className="glass-card-static p-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-green-500/10 flex items-center justify-center mx-auto mb-4">
          <BarChart3 className="w-8 h-8 text-green-400" />
        </div>
        <h1 className="text-xl font-semibold text-white mb-2">Analytics</h1>
        <p className="text-white/60 text-sm max-w-md mx-auto mb-6">
          Deep dive into performance metrics, trend analysis, and AI-powered projections.
        </p>
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500/10 text-amber-400 text-sm">
          <Construction className="w-4 h-4" />
          Coming Soon
        </div>
      </div>
    </div>
  );
}
