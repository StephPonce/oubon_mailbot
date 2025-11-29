import React from 'react';
import { IntelligenceBriefing } from '../components/intelligence/IntelligenceBriefing';
import { ProductGradeCard } from '../components/intelligence/ProductGradeCard';
import { ProductProgressTracker } from '../components/intelligence/ProductProgressTracker';
import { GlassPanel } from '../components/GlassPanel';

const IntelligencePage: React.FC = () => {
  // For demo purposes, using product ID 1
  // In production, this would come from selected product or route params
  const selectedProductId = 1;

  return (
    <div className="min-h-screen bg-gray-50 p-12" style={{ perspective: '1500px' }}>
      <div className="max-w-7xl mx-auto space-y-12">
        {/* Header */}
        <GlassPanel depth={80} delay={0.2}>
          <h1 className="text-3xl font-light text-gray-900">Intelligence Core</h1>
          <p className="text-gray-600 mt-2">
            AI-powered insights, briefings, and product intelligence
          </p>
        </GlassPanel>

        {/* Intelligence Briefing */}
        <IntelligenceBriefing />

        {/* Product Info Cards - Temporarily disabled until API endpoints are implemented */}
        {/*
        <div className="space-y-12">
          <ProductGradeCard productId={selectedProductId} />
          <ProductProgressTracker productId={selectedProductId} />
        </div>
        */}
      </div>
    </div>
  );
};

export default IntelligencePage;
