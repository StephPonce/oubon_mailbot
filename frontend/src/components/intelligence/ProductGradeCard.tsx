import React, { useState, useEffect } from 'react';

interface GradeBreakdown {
  factor: string;
  score: number;
  max_points: number;
  percentage: number;
}

interface ProductGrade {
  grade: string;
  score: number;
  breakdown: GradeBreakdown[];
  strengths: string[];
  weaknesses: string[];
  recommendation: string;
}

interface ProductGradeCardProps {
  productId: number;
}

export const ProductGradeCard: React.FC<ProductGradeCardProps> = ({ productId }) => {
  const [gradeData, setGradeData] = useState<ProductGrade | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchGrade = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `http://localhost:8001/api/intelligence/grade/product/${productId}`
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        setGradeData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch grade');
      } finally {
        setLoading(false);
      }
    };

    if (productId) {
      fetchGrade();
    }
  }, [productId]);

  const getGradeColor = (grade: string) => {
    if (grade.startsWith('A')) return 'text-green-600 bg-green-50';
    if (grade.startsWith('B')) return 'text-blue-600 bg-blue-50';
    if (grade.startsWith('C')) return 'text-yellow-600 bg-yellow-50';
    if (grade.startsWith('D')) return 'text-orange-600 bg-orange-50';
    return 'text-red-600 bg-red-50';
  };

  const getScoreColor = (percentage: number) => {
    if (percentage >= 80) return 'bg-green-500';
    if (percentage >= 60) return 'bg-blue-500';
    if (percentage >= 40) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
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

  if (!gradeData) {
    return null;
  }

  return (
    <div className="bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Header with Grade */}
      <div className={`p-6 ${getGradeColor(gradeData.grade)}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium opacity-75">Product Grade</p>
            <p className="text-5xl font-bold mt-1">{gradeData.grade}</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium opacity-75">Score</p>
            <p className="text-3xl font-bold">{gradeData.score}/100</p>
          </div>
        </div>
      </div>

      {/* Breakdown */}
      <div className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Score Breakdown</h3>
        <div className="space-y-3">
          {gradeData.breakdown.map((item, index) => (
            <div key={index}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-700">{item.factor}</span>
                <span className="text-sm text-gray-600">
                  {item.score.toFixed(1)}/{item.max_points} ({item.percentage.toFixed(0)}%)
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${getScoreColor(item.percentage)}`}
                  style={{ width: `${item.percentage}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>

        {/* Strengths */}
        {gradeData.strengths.length > 0 && (
          <div className="mt-6">
            <h4 className="text-sm font-semibold text-gray-900 mb-2">Strengths</h4>
            <ul className="space-y-1">
              {gradeData.strengths.map((strength, index) => (
                <li key={index} className="flex items-start text-sm text-gray-700">
                  <span className="text-green-500 mr-2">✓</span>
                  {strength}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Weaknesses */}
        {gradeData.weaknesses.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-gray-900 mb-2">Weaknesses</h4>
            <ul className="space-y-1">
              {gradeData.weaknesses.map((weakness, index) => (
                <li key={index} className="flex items-start text-sm text-gray-700">
                  <span className="text-red-500 mr-2">✗</span>
                  {weakness}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Recommendation */}
        {gradeData.recommendation && (
          <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-blue-900 mb-1">Recommendation</h4>
            <p className="text-sm text-blue-800">{gradeData.recommendation}</p>
          </div>
        )}
      </div>
    </div>
  );
};
