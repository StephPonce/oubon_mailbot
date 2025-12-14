import { useState, useEffect } from 'react';
import { Lightbulb, AlertTriangle, CheckCircle2 } from 'lucide-react';

interface AnalysisDisplayProps {
  analysis: {
    score: number;
    recommendation: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'SELL';
    reasoning: string[];
    risks: string[];
    success_prediction: string;
    analysis?: string; // Raw text (don't display directly)
    source: string;
    timestamp: string;
  };
}

// AnimatedScore Component - Count-up animation for score
const AnimatedScore: React.FC<{ score: number }> = ({ score }) => {
  const [displayScore, setDisplayScore] = useState(0);

  useEffect(() => {
    const duration = 1000; // 1 second
    const steps = 20;
    const increment = score / steps;
    let current = 0;

    const timer = setInterval(() => {
      current += increment;
      if (current >= score) {
        setDisplayScore(score);
        clearInterval(timer);
      } else {
        setDisplayScore(current);
      }
    }, duration / steps);

    return () => clearInterval(timer);
  }, [score]);

  return <span>{displayScore.toFixed(1)}</span>;
};

export const AnalysisDisplay: React.FC<AnalysisDisplayProps> = ({ analysis }) => {
  const getRecommendationStyle = (rec: string) => {
    switch (rec) {
      case 'STRONG_BUY':
        return 'bg-gradient-to-r from-green-500 to-emerald-500 text-white';
      case 'BUY':
        return 'bg-cyan-500/100 text-white';
      case 'HOLD':
        return 'bg-amber-500 text-white';
      case 'SELL':
        return 'bg-red-500/100 text-white';
      default:
        return ' 0 text-white';
    }
  };

  return (
    <div className="space-y-6">
      {/* Hero Score Section */}
      <div className="flex items-center justify-between p-6 bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl">
        <div>
          <p className="text-tertiary text-sm mb-1">Ospra AI Score</p>
          <div className="flex items-baseline gap-2">
            <span className="text-5xl font-bold text-white">
              <AnimatedScore score={analysis.score} />
            </span>
            <span className="text-2xl text-tertiary">/10</span>
          </div>
          <p className="text-tertiary text-sm mt-2">{analysis.success_prediction}</p>
        </div>
        <div
          className={`px-6 py-3 rounded-xl font-bold text-lg ${getRecommendationStyle(
            analysis.recommendation
          )}`}
        >
          {analysis.recommendation.replace('_', ' ')}
        </div>
      </div>

      {/* Marketing Angles */}
      {analysis.reasoning?.length > 0 && (
        <div>
          <h4 className="flex items-center gap-2 text-lg font-semibold text-gray-200 mb-4">
            <Lightbulb className="w-5 h-5 text-yellow-400" />
            Why This Product Wins
          </h4>
          <div className="space-y-3">
            {analysis.reasoning.map((reason, i) => (
              <div
                key={i}
                className="flex gap-3 p-4 bg-green-500/100/10 border border-green-500/20 rounded-xl hover:bg-green-500/100/20 transition-colors duration-200"
              >
                <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                <p className="text-gray-300">{reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Risks */}
      {analysis.risks?.length > 0 && (
        <div>
          <h4 className="flex items-center gap-2 text-lg font-semibold text-gray-200 mb-4">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            Risks to Consider
          </h4>
          <div className="space-y-3">
            {analysis.risks.map((risk, i) => (
              <div
                key={i}
                className="flex gap-3 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl hover:bg-amber-500/20 transition-colors duration-200"
              >
                <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                <p className="text-gray-300">{risk}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-tertiary pt-4 border-t border-gray-700">
        <span>Source: {analysis.source}</span>
        <span>{new Date(analysis.timestamp).toLocaleString()}</span>
      </div>
    </div>
  );
};
