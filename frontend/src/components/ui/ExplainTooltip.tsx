import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { HelpCircle, Brain, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react';

interface ExplainTooltipProps {
  rationale: string;
  confidence?: number;  // 0-100
  factors?: {
    label: string;
    value: number;
    icon?: 'trend' | 'warning' | 'success';
  }[];
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export function ExplainTooltip({
  rationale,
  confidence,
  factors,
  position = 'top'
}: ExplainTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);

  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  const getConfidenceColor = (conf: number) => {
    if (conf >= 80) return 'text-green-400';
    if (conf >= 60) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getFactorIcon = (icon?: string) => {
    switch (icon) {
      case 'trend': return <TrendingUp className="w-3 h-3" />;
      case 'warning': return <AlertTriangle className="w-3 h-3" />;
      case 'success': return <CheckCircle className="w-3 h-3" />;
      default: return null;
    }
  };

  return (
    <div className="relative inline-block">
      <button
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300 text-xs transition-colors"
      >
        <Brain className="w-3 h-3" />
        <span className="underline underline-offset-2">Why?</span>
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className={`absolute z-50 w-80 ${positionClasses[position]}`}
          >
            <div className="bg-slate-900/95 backdrop-blur-xl border border-cyan-500/30 rounded-xl p-4 shadow-xl shadow-cyan-500/10">
              {/* Header with confidence */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Brain className="w-4 h-4 text-cyan-400" />
                  <span className="text-xs font-medium text-white">Ospra's Analysis</span>
                </div>
                {confidence !== undefined && (
                  <div className={`text-xs font-bold ${getConfidenceColor(confidence)}`}>
                    {confidence}% confident
                  </div>
                )}
              </div>

              {/* Rationale */}
              <p className="text-xs text-slate-300 leading-relaxed mb-3">
                {rationale}
              </p>

              {/* Factors breakdown */}
              {factors && factors.length > 0 && (
                <div className="border-t border-slate-700/50 pt-3 mt-3">
                  <div className="text-xs text-slate-400 mb-2">Key Factors:</div>
                  <div className="space-y-1.5">
                    {factors.map((factor, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-1.5 text-slate-300">
                          {getFactorIcon(factor.icon)}
                          {factor.label}
                        </div>
                        <div className="font-medium text-white">
                          {factor.value > 0 ? '+' : ''}{factor.value}%
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Arrow pointer */}
              <div className={`absolute w-2 h-2 bg-slate-900 border-cyan-500/30 rotate-45 ${
                position === 'top' ? 'bottom-[-5px] left-1/2 -translate-x-1/2 border-r border-b' :
                position === 'bottom' ? 'top-[-5px] left-1/2 -translate-x-1/2 border-l border-t' :
                position === 'left' ? 'right-[-5px] top-1/2 -translate-y-1/2 border-t border-r' :
                'left-[-5px] top-1/2 -translate-y-1/2 border-b border-l'
              }`} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
