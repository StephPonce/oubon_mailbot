import { GlassPanel } from '@/components/GlassPanel';
import { Search } from 'lucide-react';

export default function CompetitiveIntelPage() {
  return (
    <div className="min-h-screen bg-gray-50 p-12" style={{ perspective: '1500px' }}>
      <div className="max-w-7xl mx-auto space-y-8">
        <GlassPanel depth={80} delay={0.1}>
          <h1 className="text-3xl font-light text-gray-900 mb-2">Competitive Intelligence</h1>
          <p className="text-gray-600">Track competitors and analyze market trends</p>
        </GlassPanel>

        <GlassPanel depth={60} delay={0.2}>
          <div className="p-12 text-center">
            <Search className="w-16 h-16 mx-auto mb-4 text-gray-400 opacity-30" />
            <p className="text-gray-600 text-lg font-light">Competitor tracking and market intelligence coming soon...</p>
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
