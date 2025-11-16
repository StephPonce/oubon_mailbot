import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Analytics {
  total_orders: number;
  total_revenue: number;
  average_order_value: number;
  orders_by_status: { [key: string]: number };
  top_products: Array<{ name: string; orders: number; revenue: number }>;
  revenue_by_day: Array<{ date: string; revenue: number }>;
  deployed_products: number;
  conversion_rate: number;
  unfulfilled_orders: number;
  shipped_orders: number;
}

export const AnalyticsPage: React.FC = () => {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const response = await axios.get('http://127.0.0.1:8000/api/dashboard/v2/analytics');
      setAnalytics(response.data.analytics);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-xl text-gray-600">Loading analytics...</div>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="text-center py-16">
        <div className="text-6xl mb-4">📊</div>
        <h2 className="text-2xl font-semibold text-gray-700 mb-2">No analytics data available</h2>
        <p className="text-gray-500">Analytics will appear once you have orders</p>
      </div>
    );
  }

  const maxRevenue = Math.max(...analytics.revenue_by_day.map(d => d.revenue), 1);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-800">Analytics</h1>
        <p className="text-gray-600 mt-2">Business performance metrics and insights</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-2">Total Revenue</div>
          <div className="text-3xl font-bold text-green-600">
            ${analytics.total_revenue.toFixed(2)}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-2">Total Orders</div>
          <div className="text-3xl font-bold text-blue-600">
            {analytics.total_orders}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-2">Average Order Value</div>
          <div className="text-3xl font-bold text-purple-600">
            ${analytics.average_order_value.toFixed(2)}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-2">Conversion Rate</div>
          <div className="text-3xl font-bold text-orange-600">
            {analytics.conversion_rate.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {analytics.total_orders} orders / {analytics.deployed_products} products
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Order Status */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Order Status</h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-700">Unfulfilled</span>
              <span className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full font-semibold">
                {analytics.unfulfilled_orders}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-700">Shipped</span>
              <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full font-semibold">
                {analytics.shipped_orders}
              </span>
            </div>
          </div>
        </div>

        {/* Top Products */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Top Products</h2>
          {analytics.top_products.length === 0 ? (
            <p className="text-gray-500">No product sales yet</p>
          ) : (
            <div className="space-y-3">
              {analytics.top_products.map((product, index) => (
                <div key={index} className="flex justify-between items-center">
                  <div>
                    <div className="font-medium text-gray-800">{product.name}</div>
                    <div className="text-sm text-gray-500">{product.orders} orders</div>
                  </div>
                  <div className="text-green-600 font-semibold">
                    ${product.revenue.toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Revenue Trend */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Revenue Trend (Last 30 Days)</h2>
        {analytics.revenue_by_day.length === 0 ? (
          <p className="text-gray-500">No revenue data yet</p>
        ) : (
          <div className="h-64 flex items-end space-x-2">
            {analytics.revenue_by_day.map((day, index) => {
              const height = (day.revenue / maxRevenue) * 100;
              return (
                <div
                  key={index}
                  className="flex-1 flex flex-col items-center group relative"
                >
                  <div
                    className="w-full bg-blue-500 hover:bg-blue-600 transition-all rounded-t cursor-pointer"
                    style={{ height: `${height}%`, minHeight: '4px' }}
                  >
                    {/* Tooltip */}
                    <div className="hidden group-hover:block absolute bottom-full mb-2 left-1/2 transform -translate-x-1/2 bg-gray-800 text-white text-xs rounded py-1 px-2 whitespace-nowrap">
                      ${day.revenue.toFixed(2)}
                      <div className="text-gray-300">{new Date(day.date).toLocaleDateString()}</div>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 mt-2 transform rotate-45 origin-left">
                    {new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
