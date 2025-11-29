import React, { useState, useEffect } from 'react';

interface Milestone {
  name: string;
  completed: boolean;
  date: string | null;
}

interface StageHistoryItem {
  stage: string;
  entered_at: string;
  duration_days: number;
}

interface ProgressData {
  current_stage: string;
  progress_percentage: number;
  days_in_stage: number;
  next_milestone: string;
  next_milestone_date: string | null;
  stage_history: StageHistoryItem[];
  milestones: Milestone[];
}

interface ProductProgressTrackerProps {
  productId: number;
}

export const ProductProgressTracker: React.FC<ProductProgressTrackerProps> = ({ productId }) => {
  const [progressData, setProgressData] = useState<ProgressData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProgress = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `http://localhost:8001/api/intelligence/progress/product/${productId}`
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        setProgressData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch progress');
      } finally {
        setLoading(false);
      }
    };

    if (productId) {
      fetchProgress();
    }
  }, [productId]);

  const stages = ['discovery', 'analysis', 'deploy', 'active', 'review', 'dropped'];

  const getStageIndex = (stage: string) => stages.indexOf(stage);

  const getStageColor = (stage: string) => {
    const colors: Record<string, string> = {
      discovery: 'bg-purple-500',
      analysis: 'bg-blue-500',
      deploy: 'bg-yellow-500',
      active: 'bg-green-500',
      review: 'bg-orange-500',
      dropped: 'bg-red-500',
    };
    return colors[stage] || 'bg-gray-500';
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-2/3"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">Error: {error}</p>
      </div>
    );
  }

  if (!progressData) {
    return null;
  }

  const currentStageIndex = getStageIndex(progressData.current_stage);

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h3 className="text-xl font-bold text-gray-900 mb-6">Product Lifecycle Progress</h3>

      {/* Current Stage & Progress */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <div>
            <span className="text-sm text-gray-600">Current Stage:</span>
            <span className="ml-2 font-semibold text-gray-900 capitalize">
              {progressData.current_stage}
            </span>
          </div>
          <div className="text-sm text-gray-600">
            {progressData.days_in_stage} days in stage
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 rounded-full h-3 mb-2">
          <div
            className={`h-3 rounded-full transition-all ${getStageColor(progressData.current_stage)}`}
            style={{ width: `${progressData.progress_percentage}%` }}
          ></div>
        </div>
        <div className="text-right text-sm font-medium text-gray-700">
          {progressData.progress_percentage}% Complete
        </div>
      </div>

      {/* Stage Timeline */}
      <div className="mb-6">
        <h4 className="text-sm font-semibold text-gray-900 mb-3">Lifecycle Stages</h4>
        <div className="relative">
          <div className="flex items-center justify-between">
            {stages.map((stage, index) => (
              <div key={stage} className="flex flex-col items-center flex-1">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    index <= currentStageIndex
                      ? getStageColor(stage)
                      : 'bg-gray-300'
                  } text-white font-bold text-sm transition-all`}
                >
                  {index <= currentStageIndex ? '✓' : index + 1}
                </div>
                <span className="text-xs text-gray-600 mt-2 capitalize text-center">
                  {stage}
                </span>
              </div>
            ))}
          </div>
          {/* Connecting Line */}
          <div className="absolute top-4 left-0 right-0 h-0.5 bg-gray-300 -z-10"></div>
        </div>
      </div>

      {/* Next Milestone */}
      {progressData.next_milestone && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-900">Next Milestone</p>
              <p className="text-sm text-blue-800">{progressData.next_milestone}</p>
            </div>
            {progressData.next_milestone_date && (
              <div className="text-sm text-blue-700">
                {new Date(progressData.next_milestone_date).toLocaleDateString()}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Milestones Checklist */}
      {progressData.milestones && progressData.milestones.length > 0 && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Milestones</h4>
          <div className="space-y-2">
            {progressData.milestones.map((milestone, index) => (
              <div
                key={index}
                className={`flex items-center justify-between p-2 rounded ${
                  milestone.completed ? 'bg-green-50' : 'bg-gray-50'
                }`}
              >
                <div className="flex items-center">
                  <span
                    className={`w-5 h-5 rounded-full flex items-center justify-center mr-3 ${
                      milestone.completed
                        ? 'bg-green-500 text-white'
                        : 'bg-gray-300 text-gray-600'
                    }`}
                  >
                    {milestone.completed ? '✓' : ''}
                  </span>
                  <span className={`text-sm ${milestone.completed ? 'text-gray-700' : 'text-gray-500'}`}>
                    {milestone.name}
                  </span>
                </div>
                {milestone.completed && milestone.date && (
                  <span className="text-xs text-gray-500">
                    {new Date(milestone.date).toLocaleDateString()}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stage History */}
      {progressData.stage_history && progressData.stage_history.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Stage History</h4>
          <div className="space-y-2">
            {progressData.stage_history.map((item, index) => (
              <div
                key={index}
                className="flex items-center justify-between text-sm border-l-4 pl-3 py-1"
                style={{ borderColor: getStageColor(item.stage).replace('bg-', '#') }}
              >
                <span className="capitalize text-gray-700">{item.stage}</span>
                <div className="flex items-center gap-4 text-gray-600">
                  <span>{item.duration_days} days</span>
                  <span className="text-xs">
                    {new Date(item.entered_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
