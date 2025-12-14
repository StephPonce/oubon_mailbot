/**
 * Ospra Intelligence - A/B Testing Page
 * 
 * FULLY FUNCTIONAL:
 * - Real A/B test management
 * - Create, pause, resume tests
 * - View test results
 * - Statistical confidence tracking
 */

import { useState } from 'react';
import {
  FlaskConical,
  Play,
  Pause,
  CheckCircle2,
  TrendingUp,
  DollarSign,
  Plus,
  RefreshCw,
  Loader2,
  BarChart3,
  X,
  Target,
  AlertCircle,
  Clock,
  Eye,
} from 'lucide-react';

import {
  useABTests,
  useABTestResults,
} from '../hooks/useData';
import { abTestingAPI } from '../services/api';
import type { ABTest } from '../services/api';

// =============================================================================
// TEST CARD
// =============================================================================

interface TestCardProps {
  test: ABTest;
  onPause: (test: ABTest) => void;
  onResume: (test: ABTest) => void;
  onViewResults: (test: ABTest) => void;
  isPausing: boolean;
  isResuming: boolean;
}

function TestCard({ test, onPause, onResume, onViewResults, isPausing, isResuming }: TestCardProps) {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'running': return 'text-green-600 bg-green-500/100/10 border-green-500/20';
      case 'completed': return 'text-blue-600 bg-cyan-500/100/10 border-blue-500/20';
      case 'paused': return 'text-amber-600 bg-amber-500/10 border-amber-500/20';
      case 'draft': return 'text-secondary  0/10 border-gray-500/20';
      default: return 'text-secondary  0/10 border-gray-500/20';
    }
  };

  const conversionA = test.results?.variant_a?.conversion_rate || test.conversion_a || 0;
  const conversionB = test.results?.variant_b?.conversion_rate || test.conversion_b || 0;
  const confidence = test.results?.confidence || test.confidence || 0;
  const isWinnerB = conversionB > conversionA;
  const lift = conversionA > 0 ? ((conversionB - conversionA) / conversionA) * 100 : 0;

  return (
    <div className="glass-card p-5 hover:shadow-lg transition-all">
      <div className="flex items-center gap-6">
        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-lg font-medium text-primary">{test.name}</h3>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusBadge(test.status)}`}>
              {test.status}
            </span>
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-black/5 text-secondary">
              {test.type || 'price'}
            </span>
          </div>
          <div className="flex items-center gap-6 text-sm text-secondary">
            {test.product_name && <span>Product: {test.product_name}</span>}
            <span>{test.variant_count || 2} variants</span>
            {test.start_date && <span>Started: {new Date(test.start_date).toLocaleDateString()}</span>}
          </div>
          {test.description && (
            <p className="text-xs text-tertiary mt-2 line-clamp-1">{test.description}</p>
          )}
        </div>

        {/* Variant A */}
        <div className="text-center px-6 border-l border-black/10">
          <div className="text-xs text-tertiary mb-1">Variant A</div>
          <div className="text-xl font-semibold text-primary">{conversionA.toFixed(1)}%</div>
        </div>

        {/* Variant B */}
        <div className="text-center px-6 border-l border-black/10">
          <div className="text-xs text-tertiary mb-1">Variant B</div>
          <div className={`text-xl font-semibold ${isWinnerB ? 'text-green-600' : 'text-primary'}`}>
            {conversionB.toFixed(1)}%
            {isWinnerB && lift > 0 && (
              <span className="text-xs text-green-600 ml-1">+{lift.toFixed(0)}%</span>
            )}
          </div>
        </div>

        {/* Confidence */}
        <div className="text-center px-6 border-l border-black/10">
          <div className="text-xs text-tertiary mb-1">Confidence</div>
          <div className={`text-xl font-semibold ${confidence >= 95 ? 'text-green-600' : confidence >= 80 ? 'text-amber-600' : 'text-secondary'}`}>
            {confidence.toFixed(0)}%
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pl-6 border-l border-black/10">
          <button
            className="btn-ghost text-sm"
            onClick={() => onViewResults(test)}
          >
            <Eye className="w-4 h-4" />
          </button>
          {test.status === 'running' ? (
            <button
              className="p-2.5 rounded-xl bg-amber-500/10 text-amber-600 hover:bg-amber-500/20 transition-colors"
              onClick={() => onPause(test)}
              disabled={isPausing}
            >
              {isPausing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Pause className="w-5 h-5" />}
            </button>
          ) : test.status === 'paused' ? (
            <button
              className="p-2.5 rounded-xl bg-green-500/100/10 text-green-600 hover:bg-green-500/100/20 transition-colors"
              onClick={() => onResume(test)}
              disabled={isResuming}
            >
              {isResuming ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
            </button>
          ) : (
            <div className="p-2.5">
              <CheckCircle2 className="w-5 h-5 text-blue-600" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// CREATE TEST MODAL
// =============================================================================

interface CreateTestModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (data: any) => void;
  isCreating: boolean;
}

function CreateTestModal({ isOpen, onClose, onCreate, isCreating }: CreateTestModalProps) {
  const [formData, setFormData] = useState({
    name: '',
    type: 'price',
    product_id: '',
    variant_a: '',
    variant_b: '',
    description: '',
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onCreate(formData);
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
      <div className="glass-card max-w-lg w-full my-8">
        <div className="p-6 border-b border-black/10">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-primary">Create A/B Test</h2>
            <button onClick={onClose} className="p-2 hover:bg-black/5 rounded-lg">
              <X className="w-5 h-5 text-tertiary" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="text-sm font-medium text-primary mb-1 block">Test Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData(f => ({ ...f, name: e.target.value }))}
              placeholder="e.g., LED Lights Price Test"
              className="w-full px-3 py-2 rounded-xl bg-black/5 border border-black/10 focus:border-accent outline-none text-sm text-primary placeholder-text-tertiary"
              required
            />
          </div>

          <div>
            <label className="text-sm font-medium text-primary mb-1 block">Test Type</label>
            <select
              value={formData.type}
              onChange={(e) => setFormData(f => ({ ...f, type: e.target.value }))}
              className="w-full px-3 py-2 rounded-xl bg-black/5 border border-black/10 focus:border-accent outline-none text-sm text-primary"
            >
              <option value="price">Price Test</option>
              <option value="title">Title Test</option>
              <option value="image">Image Test</option>
              <option value="description">Description Test</option>
              <option value="ad">Ad Creative Test</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-primary mb-1 block">Variant A</label>
              <input
                type="text"
                value={formData.variant_a}
                onChange={(e) => setFormData(f => ({ ...f, variant_a: e.target.value }))}
                placeholder="e.g., $24.99"
                className="w-full px-3 py-2 rounded-xl bg-black/5 border border-black/10 focus:border-accent outline-none text-sm text-primary placeholder-text-tertiary"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-primary mb-1 block">Variant B</label>
              <input
                type="text"
                value={formData.variant_b}
                onChange={(e) => setFormData(f => ({ ...f, variant_b: e.target.value }))}
                placeholder="e.g., $29.99"
                className="w-full px-3 py-2 rounded-xl bg-black/5 border border-black/10 focus:border-accent outline-none text-sm text-primary placeholder-text-tertiary"
              />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-primary mb-1 block">Description (optional)</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData(f => ({ ...f, description: e.target.value }))}
              placeholder="Describe what you're testing..."
              className="w-full px-3 py-2 rounded-xl bg-black/5 border border-black/10 focus:border-accent outline-none text-sm text-primary placeholder-text-tertiary resize-none"
              rows={3}
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4">
            <button type="button" className="btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isCreating || !formData.name}>
              {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              <span>Create Test</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// =============================================================================
// RESULTS MODAL
// =============================================================================

interface ResultsModalProps {
  test: ABTest | null;
  onClose: () => void;
}

function ResultsModal({ test, onClose }: ResultsModalProps) {
  if (!test) return null;

  const conversionA = test.results?.variant_a?.conversion_rate || test.conversion_a || 0;
  const conversionB = test.results?.variant_b?.conversion_rate || test.conversion_b || 0;
  const confidence = test.results?.confidence || test.confidence || 0;
  const lift = conversionA > 0 ? ((conversionB - conversionA) / conversionA) * 100 : 0;
  const isSignificant = confidence >= 95;
  const winner = conversionB > conversionA ? 'B' : 'A';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="glass-card max-w-2xl w-full">
        <div className="p-6 border-b border-black/10">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-primary">{test.name}</h2>
              <p className="text-sm text-secondary mt-1">Test Results</p>
            </div>
            <button onClick={onClose} className="btn-ghost">Close</button>
          </div>
        </div>

        <div className="p-6">
          {/* Status */}
          <div className={`p-4 rounded-xl mb-6 ${isSignificant ? 'bg-green-500/100/10 border border-green-500/20' : 'bg-amber-500/10 border border-amber-500/20'}`}>
            <div className="flex items-center gap-2">
              {isSignificant ? (
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              ) : (
                <AlertCircle className="w-5 h-5 text-amber-600" />
              )}
              <span className={`font-medium ${isSignificant ? 'text-green-400' : 'text-amber-700'}`}>
                {isSignificant 
                  ? `Variant ${winner} is the winner with ${confidence.toFixed(0)}% confidence!`
                  : `Not yet significant (${confidence.toFixed(0)}% confidence). Keep running the test.`
                }
              </span>
            </div>
          </div>

          {/* Comparison */}
          <div className="grid grid-cols-2 gap-6 mb-6">
            <div className={`p-6 rounded-xl border ${winner === 'A' && isSignificant ? 'bg-green-500/100/5 border-green-500/20' : 'bg-black/5 border-black/10'}`}>
              <div className="text-sm text-secondary mb-2">Variant A (Control)</div>
              <div className="text-3xl font-bold text-primary">{conversionA.toFixed(2)}%</div>
              <div className="text-xs text-tertiary mt-1">Conversion Rate</div>
              {test.results?.variant_a?.visitors && (
                <div className="text-sm text-secondary mt-3">
                  {test.results.variant_a.visitors.toLocaleString()} visitors
                </div>
              )}
            </div>
            <div className={`p-6 rounded-xl border ${winner === 'B' && isSignificant ? 'bg-green-500/100/5 border-green-500/20' : 'bg-black/5 border-black/10'}`}>
              <div className="text-sm text-secondary mb-2">Variant B (Treatment)</div>
              <div className="text-3xl font-bold text-primary">{conversionB.toFixed(2)}%</div>
              <div className="text-xs text-tertiary mt-1">Conversion Rate</div>
              {lift !== 0 && (
                <div className={`text-sm font-medium mt-3 ${lift > 0 ? 'text-green-600' : 'text-red-500'}`}>
                  {lift > 0 ? '+' : ''}{lift.toFixed(1)}% vs Control
                </div>
              )}
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-primary">{confidence.toFixed(0)}%</div>
              <div className="text-xs text-tertiary">Confidence</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className={`text-2xl font-bold ${lift > 0 ? 'text-green-600' : lift < 0 ? 'text-red-500' : 'text-primary'}`}>
                {lift > 0 ? '+' : ''}{lift.toFixed(1)}%
              </div>
              <div className="text-xs text-tertiary">Lift</div>
            </div>
            <div className="text-center p-4 rounded-xl bg-black/5">
              <div className="text-2xl font-bold text-primary">{test.variant_count || 2}</div>
              <div className="text-xs text-tertiary">Variants</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function ABTestingPage() {
  // State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedTest, setSelectedTest] = useState<ABTest | null>(null);
  const [pausingId, setPausingId] = useState<string | null>(null);
  const [resumingId, setResumingId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  // Data hooks
  const { data: tests, isLoading: testsLoading, refetch: refetchTests } = useABTests();

  // Stats
  const activeTests = tests?.filter(t => t.status === 'running').length || 0;
  const completedTests = tests?.filter(t => t.status === 'completed').length || 0;
  const avgConfidence = tests?.length 
    ? (tests.reduce((sum, t) => sum + (t.confidence || 0), 0) / tests.length).toFixed(0)
    : '0';

  // Handlers
  const handleCreate = async (data: any) => {
    setIsCreating(true);
    try {
      await abTestingAPI.create(data);
      await refetchTests();
      setShowCreateModal(false);
      alert('✅ A/B Test created successfully!');
    } catch (error) {
      console.error('Failed to create test:', error);
      alert('❌ Failed to create test. Please try again.');
    } finally {
      setIsCreating(false);
    }
  };

  const handlePause = async (test: ABTest) => {
    setPausingId(test.id);
    try {
      await abTestingAPI.pause(test.id);
      await refetchTests();
    } catch (error) {
      console.error('Failed to pause test:', error);
      alert('❌ Failed to pause test.');
    } finally {
      setPausingId(null);
    }
  };

  const handleResume = async (test: ABTest) => {
    setResumingId(test.id);
    try {
      await abTestingAPI.resume(test.id);
      await refetchTests();
    } catch (error) {
      console.error('Failed to resume test:', error);
      alert('❌ Failed to resume test.');
    } finally {
      setResumingId(null);
    }
  };

  const handleViewResults = (test: ABTest) => {
    setSelectedTest(test);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary flex items-center gap-2">
            <FlaskConical className="w-6 h-6 text-accent" />
            A/B Testing
          </h1>
          <p className="text-sm text-secondary mt-1">
            Run experiments to optimize conversions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-ghost"
            onClick={() => refetchTests()}
            disabled={testsLoading}
          >
            <RefreshCw className={`w-4 h-4 ${testsLoading ? 'animate-spin' : ''}`} />
          </button>
          <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
            <Plus className="w-4 h-4" />
            <span>New Test</span>
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="glass-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-secondary mb-1">Active Tests</div>
              <div className="text-2xl font-semibold text-primary">{activeTests}</div>
            </div>
            <FlaskConical className="w-8 h-8 text-blue-500/30" />
          </div>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-secondary mb-1">Completed</div>
              <div className="text-2xl font-semibold text-primary">{completedTests}</div>
            </div>
            <CheckCircle2 className="w-8 h-8 text-green-500/30" />
          </div>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-secondary mb-1">Avg Confidence</div>
              <div className="text-2xl font-semibold text-primary">{avgConfidence}%</div>
            </div>
            <Target className="w-8 h-8 text-purple-500/30" />
          </div>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-secondary mb-1">Total Tests</div>
              <div className="text-2xl font-semibold text-primary">{tests?.length || 0}</div>
            </div>
            <BarChart3 className="w-8 h-8 text-cyan-500/30" />
          </div>
        </div>
      </div>

      {/* Tests List */}
      {testsLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
        </div>
      ) : !tests || tests.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <FlaskConical className="w-12 h-12 text-tertiary mx-auto mb-4" />
          <h3 className="text-lg font-medium text-primary mb-2">No A/B Tests Yet</h3>
          <p className="text-sm text-secondary mb-6">
            Create your first A/B test to start optimizing your conversions.
          </p>
          <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
            <Plus className="w-4 h-4" />
            <span>Create Test</span>
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {tests.map((test, index) => (
            <TestCard
              key={test.id}
              test={test}
              onPause={handlePause}
              onResume={handleResume}
              onViewResults={handleViewResults}
              isPausing={pausingId === test.id}
              isResuming={resumingId === test.id}
            />
          ))}
        </div>
      )}

      {/* Create Modal */}
      <CreateTestModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreate}
        isCreating={isCreating}
      />

      {/* Results Modal */}
      <ResultsModal
        test={selectedTest}
        onClose={() => setSelectedTest(null)}
      />
    </div>
  );
}
