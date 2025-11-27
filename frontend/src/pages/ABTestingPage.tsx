import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  FlaskConical,
  Plus,
  RefreshCw,
  Play,
  Pause,
  Square,
  TrendingUp,
  TrendingDown,
  Minus,
  BarChart3,
  DollarSign,
  Image as ImageIcon,
  FileText,
  Megaphone
} from 'lucide-react';
import { CreateTestModal } from '../components/CreateTestModal';

const API_BASE = 'http://localhost:8001';

interface ABTest {
  id: number;
  name: string;
  test_type: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  scheduled_end: string | null;
  winner_variant_id: number | null;
  product_id: string;
  store_id: string;
  min_sample_size: number;
  confidence_level: number;
}

interface Variant {
  id: number;
  name: string;
  impressions: number;
  conversions: number;
  revenue: number;
  conversion_rate: number;
  is_control: boolean;
  is_significant?: boolean;
  confidence_interval?: [number, number];
  p_value?: number;
}

interface TestDetails extends ABTest {
  variants: Variant[];
  winner_variant?: Variant;
}

export const ABTestingPage: React.FC = () => {
  const [tests, setTests] = useState<ABTest[]>([]);
  const [selectedTest, setSelectedTest] = useState<TestDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    fetchTests();
    const interval = setInterval(fetchTests, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [statusFilter, typeFilter]);

  const fetchTests = async () => {
    try {
      const params: any = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (typeFilter !== 'all') params.test_type = typeFilter;

      const response = await axios.get(`${API_BASE}/api/abtesting/tests`, { params });
      setTests(response.data.tests || []);
    } catch (error) {
      console.error('Failed to fetch tests:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTestDetails = async (testId: number) => {
    try {
      const response = await axios.get(`${API_BASE}/api/abtesting/tests/${testId}?include_results=true`);
      setSelectedTest(response.data);
    } catch (error) {
      console.error('Failed to fetch test details:', error);
    }
  };

  const handleTestAction = async (testId: number, action: 'start' | 'pause' | 'resume' | 'end') => {
    try {
      await axios.post(`${API_BASE}/api/abtesting/tests/${testId}/${action}`);
      fetchTests();
      if (selectedTest?.id === testId) {
        fetchTestDetails(testId);
      }
    } catch (error) {
      console.error(`Failed to ${action} test:`, error);
    }
  };

  const getTestTypeIcon = (type: string) => {
    switch (type) {
      case 'price':
        return <DollarSign className="w-4 h-4" />;
      case 'product_title':
      case 'product_description':
        return <FileText className="w-4 h-4" />;
      case 'product_image':
        return <ImageIcon className="w-4 h-4" />;
      case 'ad_creative':
      case 'ad_copy':
        return <Megaphone className="w-4 h-4" />;
      default:
        return <FlaskConical className="w-4 h-4" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
      draft: { bg: 'bg-gray-100', text: 'text-gray-700', label: 'Draft' },
      running: { bg: 'bg-green-100', text: 'text-green-700', label: 'Running' },
      paused: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Paused' },
      ended: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Ended' }
    };

    const config = statusConfig[status] || statusConfig.draft;

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
        {config.label}
      </span>
    );
  };

  const getSignificanceBadge = (variant: Variant) => {
    if (!variant.is_significant) {
      return <span className="text-xs text-gray-500">Not significant</span>;
    }

    if (variant.p_value && variant.p_value < 0.01) {
      return (
        <span className="px-2 py-1 rounded bg-green-100 text-green-700 text-xs font-medium">
          Highly Significant (p &lt; 0.01)
        </span>
      );
    }

    return (
      <span className="px-2 py-1 rounded bg-blue-100 text-blue-700 text-xs font-medium">
        Significant (p &lt; 0.05)
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-8 h-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <FlaskConical className="w-8 h-8 text-purple-600" />
              A/B Testing
            </h1>
            <p className="text-gray-600 mt-1">
              Optimize your products with data-driven testing
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            <Plus className="w-5 h-5" />
            Create Test
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-4 mt-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              <option value="all">All Status</option>
              <option value="draft">Draft</option>
              <option value="running">Running</option>
              <option value="paused">Paused</option>
              <option value="ended">Ended</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Test Type</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              <option value="all">All Types</option>
              <option value="price">Price</option>
              <option value="product_title">Title</option>
              <option value="product_description">Description</option>
              <option value="product_image">Image</option>
              <option value="ad_creative">Ad Creative</option>
              <option value="ad_copy">Ad Copy</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={fetchTests}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Test List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {tests.length === 0 ? (
          <div className="col-span-2 text-center py-12">
            <FlaskConical className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No tests found</h3>
            <p className="text-gray-600 mb-4">
              Create your first A/B test to start optimizing
            </p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
            >
              Create Test
            </button>
          </div>
        ) : (
          tests.map((test) => (
            <div
              key={test.id}
              className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => fetchTestDetails(test.id)}
            >
              {/* Test Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-100 rounded-lg">
                    {getTestTypeIcon(test.test_type)}
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{test.name}</h3>
                    <p className="text-sm text-gray-600 capitalize">
                      {test.test_type.replace(/_/g, ' ')}
                    </p>
                  </div>
                </div>
                {getStatusBadge(test.status)}
              </div>

              {/* Test Info */}
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Product ID:</span>
                  <span className="font-medium text-gray-900">{test.product_id}</span>
                </div>
                {test.started_at && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Started:</span>
                    <span className="font-medium text-gray-900">
                      {new Date(test.started_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
                {test.scheduled_end && test.status === 'running' && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Ends:</span>
                    <span className="font-medium text-gray-900">
                      {new Date(test.scheduled_end).toLocaleDateString()}
                    </span>
                  </div>
                )}
                {test.winner_variant_id && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Winner:</span>
                    <span className="font-medium text-green-600">Variant #{test.winner_variant_id}</span>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-2 mt-4 pt-4 border-t border-gray-100">
                {test.status === 'draft' && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleTestAction(test.id, 'start');
                    }}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700"
                  >
                    <Play className="w-3 h-3" />
                    Start
                  </button>
                )}
                {test.status === 'running' && (
                  <>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleTestAction(test.id, 'pause');
                      }}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm bg-yellow-600 text-white rounded hover:bg-yellow-700"
                    >
                      <Pause className="w-3 h-3" />
                      Pause
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleTestAction(test.id, 'end');
                      }}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                    >
                      <Square className="w-3 h-3" />
                      End
                    </button>
                  </>
                )}
                {test.status === 'paused' && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleTestAction(test.id, 'resume');
                    }}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700"
                  >
                    <Play className="w-3 h-3" />
                    Resume
                  </button>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    fetchTestDetails(test.id);
                  }}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50"
                >
                  <BarChart3 className="w-3 h-3" />
                  Details
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Test Details Modal */}
      {selectedTest && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200 sticky top-0 bg-white">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">{selectedTest.name}</h2>
                  <p className="text-gray-600 capitalize">
                    {selectedTest.test_type.replace(/_/g, ' ')} Test
                  </p>
                </div>
                <button
                  onClick={() => setSelectedTest(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <Square className="w-6 h-6" />
                </button>
              </div>
            </div>

            <div className="p-6">
              {/* Test Stats */}
              <div className="grid grid-cols-4 gap-4 mb-6">
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">
                    {selectedTest.variants.length}
                  </div>
                  <div className="text-sm text-gray-600">Variants</div>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">
                    {selectedTest.variants.reduce((sum, v) => sum + v.impressions, 0).toLocaleString()}
                  </div>
                  <div className="text-sm text-gray-600">Total Impressions</div>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">
                    {selectedTest.variants.reduce((sum, v) => sum + v.conversions, 0).toLocaleString()}
                  </div>
                  <div className="text-sm text-gray-600">Total Conversions</div>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">
                    ${selectedTest.variants.reduce((sum, v) => sum + v.revenue, 0).toLocaleString()}
                  </div>
                  <div className="text-sm text-gray-600">Total Revenue</div>
                </div>
              </div>

              {/* Variants */}
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Variant Performance</h3>
              <div className="space-y-4">
                {selectedTest.variants.map((variant) => (
                  <div
                    key={variant.id}
                    className={`p-4 rounded-lg border-2 ${
                      variant.id === selectedTest.winner_variant_id
                        ? 'border-green-500 bg-green-50'
                        : variant.is_control
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold text-gray-900">{variant.name}</h4>
                        {variant.is_control && (
                          <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">
                            Control
                          </span>
                        )}
                        {variant.id === selectedTest.winner_variant_id && (
                          <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded">
                            Winner
                          </span>
                        )}
                      </div>
                      {getSignificanceBadge(variant)}
                    </div>

                    <div className="grid grid-cols-4 gap-4 text-sm">
                      <div>
                        <div className="text-gray-600">Impressions</div>
                        <div className="text-lg font-semibold text-gray-900">
                          {variant.impressions.toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-600">Conversions</div>
                        <div className="text-lg font-semibold text-gray-900">
                          {variant.conversions.toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-600">Conversion Rate</div>
                        <div className="text-lg font-semibold text-gray-900">
                          {variant.conversion_rate.toFixed(2)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-600">Revenue</div>
                        <div className="text-lg font-semibold text-gray-900">
                          ${variant.revenue.toLocaleString()}
                        </div>
                      </div>
                    </div>

                    {variant.confidence_interval && (
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <div className="text-xs text-gray-600">
                          95% Confidence Interval: {variant.confidence_interval[0].toFixed(2)}% - {variant.confidence_interval[1].toFixed(2)}%
                        </div>
                        {variant.p_value && (
                          <div className="text-xs text-gray-600 mt-1">
                            p-value: {variant.p_value.toFixed(4)}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Test Modal */}
      <CreateTestModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onTestCreated={fetchTests}
      />
    </div>
  );
};
