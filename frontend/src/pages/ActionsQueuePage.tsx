import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle, XCircle, Edit3, Zap,
  Package, Mail, DollarSign, TrendingDown,
  PlayCircle, PauseCircle, RefreshCw,
  Brain, AlertTriangle, ChevronDown,
  Loader2
} from 'lucide-react';
import { ExplainTooltip } from '../components/ui/ExplainTooltip';

// Action types
type ActionType =
  | 'deploy_product'
  | 'adjust_price'
  | 'pause_ad'
  | 'resume_ad'
  | 'drop_product'
  | 'send_refund'
  | 'reply_email'
  | 'restock_alert';

type ActionStatus = 'pending' | 'approved' | 'executed' | 'skipped' | 'failed';

interface Action {
  id: string;
  type: ActionType;
  title: string;
  description: string;
  payload: Record<string, any>;
  confidence: number;
  rationale: string;
  factors: { label: string; value: number; icon?: string }[];
  status: ActionStatus;
  created_at: string;
  executed_at?: string;
  product_image?: string;
  estimated_impact?: string;
}

// Icon mapping
const actionIcons: Record<ActionType, typeof Package> = {
  deploy_product: Package,
  adjust_price: DollarSign,
  pause_ad: PauseCircle,
  resume_ad: PlayCircle,
  drop_product: TrendingDown,
  send_refund: RefreshCw,
  reply_email: Mail,
  restock_alert: AlertTriangle,
};

// Color mapping (using existing design tokens)
const actionColors: Record<ActionType, string> = {
  deploy_product: 'blue',
  adjust_price: 'amber',
  pause_ad: 'orange',
  resume_ad: 'green',
  drop_product: 'red',
  send_refund: 'purple',
  reply_email: 'blue',
  restock_alert: 'yellow',
};

function ActionCard({
  action,
  onApprove,
  onSkip,
  onEdit
}: {
  action: Action;
  onApprove: (id: string) => void;
  onSkip: (id: string) => void;
  onEdit: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const Icon = actionIcons[action.type];
  const color = actionColors[action.type];

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 85) return 'bg-green-500/10 text-green-600 border-green-500/20';
    if (confidence >= 70) return 'bg-amber-500/10 text-amber-600 border-amber-500/20';
    return 'bg-red-500/10 text-red-600 border-red-500/20';
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="glass-card p-4 hover:shadow-md transition-all"
    >
      {/* Main Row */}
      <div className="flex items-center gap-4">
        {/* Icon */}
        <div className={`stat-card-icon ${color}`}>
          <Icon className="w-5 h-5" />
        </div>

        {/* Product Image */}
        {action.product_image && (
          <img
            src={action.product_image}
            alt=""
            className="w-12 h-12 rounded-lg object-cover flex-shrink-0 border border-black/5"
          />
        )}

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-primary truncate">{action.title}</h3>
            <span className={`px-2 py-0.5 text-xs rounded-full border font-medium ${getConfidenceBadge(action.confidence)}`}>
              {action.confidence}%
            </span>
          </div>
          <p className="text-sm text-secondary truncate">{action.description}</p>
          {action.estimated_impact && (
            <p className="text-xs text-green-600 mt-1">{action.estimated_impact}</p>
          )}
        </div>

        {/* Explain Tooltip */}
        <ExplainTooltip
          rationale={action.rationale}
          confidence={action.confidence}
          factors={action.factors}
          position="left"
        />

        {/* Expand Button */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-2 text-secondary hover:text-primary hover:bg-black/5 rounded-lg transition-colors"
        >
          <ChevronDown className={`w-5 h-5 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </button>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => onSkip(action.id)}
            className="p-2 rounded-lg text-secondary hover:text-red-600 hover:bg-red-500/10 transition-all"
            title="Skip"
          >
            <XCircle className="w-5 h-5" />
          </button>
          <button
            onClick={() => onEdit(action.id)}
            className="p-2 rounded-lg text-secondary hover:text-amber-600 hover:bg-amber-500/10 transition-all"
            title="Edit"
          >
            <Edit3 className="w-5 h-5" />
          </button>
          <button
            onClick={() => onApprove(action.id)}
            className="px-4 py-2 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-all flex items-center gap-2"
          >
            <CheckCircle className="w-4 h-4" />
            Approve
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-4 pt-4 border-t border-black/5"
          >
            <div className="grid grid-cols-2 gap-6">
              {/* Payload Details */}
              <div>
                <h4 className="text-xs text-tertiary uppercase mb-3 font-medium">Action Details</h4>
                <div className="space-y-2">
                  {Object.entries(action.payload).map(([key, value]) => (
                    <div key={key} className="flex justify-between text-sm">
                      <span className="text-secondary capitalize">{key.replace(/_/g, ' ')}</span>
                      <span className="text-primary font-medium">
                        {typeof value === 'number' && key.includes('price')
                          ? `$${value.toFixed(2)}`
                          : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Factors */}
              <div>
                <h4 className="text-xs text-tertiary uppercase mb-3 font-medium">Key Factors</h4>
                <div className="space-y-2">
                  {action.factors.map((factor, i) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="text-secondary">{factor.label}</span>
                      <span className={factor.value > 0 ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
                        {factor.value > 0 ? '+' : ''}{factor.value}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function ActionsQueuePage() {
  const [actions, setActions] = useState<Action[]>([
    // Demo data
    {
      id: '1',
      type: 'deploy_product',
      title: 'Deploy: Premium Yoga Mat',
      description: 'Deploy to Shopify at $129.99 (42% margin)',
      payload: {
        product_name: 'Premium Yoga Mat',
        source_price: 78.00,
        sell_price: 129.99,
        margin: 42,
        niche: 'fitness'
      },
      confidence: 89,
      rationale: 'High velocity score (87), low saturation in fitness niche, excellent margin potential. Similar products converted at 3.2% on your store.',
      factors: [
        { label: 'Velocity Score', value: 18, icon: 'trend' },
        { label: 'Profit Margin', value: 15, icon: 'success' },
        { label: 'Low Competition', value: 12, icon: 'success' },
      ],
      status: 'pending',
      created_at: new Date().toISOString(),
      product_image: 'https://via.placeholder.com/100',
      estimated_impact: '+$520 projected monthly profit'
    },
    {
      id: '2',
      type: 'pause_ad',
      title: 'Pause Ad: Wireless Earbuds Campaign',
      description: 'ROAS dropped to 0.8x over 7 days',
      payload: {
        campaign_name: 'Wireless Earbuds - Meta',
        platform: 'meta',
        current_roas: 0.8,
        spend_last_7d: 156.00,
        conversions: 2
      },
      confidence: 94,
      rationale: 'Campaign ROAS fell below 1.0x threshold. Spending $22/day with only 2 conversions in 7 days. Recommend pausing to prevent further loss.',
      factors: [
        { label: 'ROAS Below Target', value: -25, icon: 'warning' },
        { label: 'High CPA', value: -15, icon: 'warning' },
        { label: 'Declining CTR', value: -8, icon: 'warning' },
      ],
      status: 'pending',
      created_at: new Date(Date.now() - 3600000).toISOString(),
      estimated_impact: 'Save $154/week in ad spend'
    },
    {
      id: '3',
      type: 'adjust_price',
      title: 'Price Adjustment: LED Strip Lights',
      description: 'Supplier price increased 12% - adjust to maintain margin',
      payload: {
        product_name: 'LED Strip Lights 5M',
        current_price: 34.99,
        new_price: 39.99,
        old_supplier_price: 12.50,
        new_supplier_price: 14.00,
        new_margin: 65
      },
      confidence: 82,
      rationale: 'Supplier price increased from $12.50 to $14.00. Recommended price adjustment maintains 65% margin while staying competitive.',
      factors: [
        { label: 'Margin Protection', value: 20, icon: 'success' },
        { label: 'Competitor Pricing', value: 5, icon: 'trend' },
      ],
      status: 'pending',
      created_at: new Date(Date.now() - 7200000).toISOString(),
    },
  ]);

  const [filter, setFilter] = useState<ActionType | 'all'>('all');
  const [isApproving, setIsApproving] = useState(false);

  const pendingActions = actions.filter(a =>
    a.status === 'pending' && (filter === 'all' || a.type === filter)
  );

  const handleApprove = async (id: string) => {
    setActions(prev => prev.map(a =>
      a.id === id ? { ...a, status: 'approved' as ActionStatus } : a
    ));
  };

  const handleSkip = async (id: string) => {
    setActions(prev => prev.map(a =>
      a.id === id ? { ...a, status: 'skipped' as ActionStatus } : a
    ));
  };

  const handleEdit = (id: string) => {
    console.log('Edit action:', id);
  };

  const handleApproveAll = async () => {
    setIsApproving(true);
    const highConfidence = pendingActions.filter(a => a.confidence >= 85);
    for (const action of highConfidence) {
      await handleApprove(action.id);
      await new Promise(r => setTimeout(r, 300));
    }
    setIsApproving(false);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-primary flex items-center gap-3">
            <Zap className="w-6 h-6 text-blue-500" />
            Pending Actions
          </h1>
          <p className="text-sm text-secondary mt-1">
            {pendingActions.length} actions waiting for your approval
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Filter */}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as ActionType | 'all')}
            className="px-4 py-2 bg-white border border-black/10 rounded-lg text-primary text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Actions</option>
            <option value="deploy_product">Deploy Product</option>
            <option value="adjust_price">Price Adjustments</option>
            <option value="pause_ad">Pause Ads</option>
            <option value="drop_product">Drop Products</option>
            <option value="reply_email">Email Replies</option>
          </select>

          {/* Approve All */}
          <button
            onClick={handleApproveAll}
            disabled={isApproving || pendingActions.filter(a => a.confidence >= 85).length === 0}
            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:text-gray-500 text-white rounded-lg font-medium transition-all flex items-center gap-2"
          >
            {isApproving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            Approve All High Confidence
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4">
        <div className="glass-card p-4">
          <div className="text-xs text-tertiary mb-1">Pending</div>
          <div className="text-2xl font-bold text-blue-500">{actions.filter(a => a.status === 'pending').length}</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-xs text-tertiary mb-1">Approved Today</div>
          <div className="text-2xl font-bold text-green-500">{actions.filter(a => a.status === 'approved').length}</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-xs text-tertiary mb-1">Skipped</div>
          <div className="text-2xl font-bold text-gray-400">{actions.filter(a => a.status === 'skipped').length}</div>
        </div>
        <div className="glass-card p-4">
          <div className="text-xs text-tertiary mb-1">Avg Confidence</div>
          <div className="text-2xl font-bold text-amber-500">
            {Math.round(pendingActions.reduce((sum, a) => sum + a.confidence, 0) / (pendingActions.length || 1))}%
          </div>
        </div>
      </div>

      {/* Actions List */}
      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {pendingActions.length > 0 ? (
            pendingActions.map(action => (
              <ActionCard
                key={action.id}
                action={action}
                onApprove={handleApprove}
                onSkip={handleSkip}
                onEdit={handleEdit}
              />
            ))
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="glass-card p-12 text-center"
            >
              <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
              <h3 className="text-xl font-medium text-primary mb-2">All caught up!</h3>
              <p className="text-secondary">No pending actions. Ospra will notify you when decisions need approval.</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
