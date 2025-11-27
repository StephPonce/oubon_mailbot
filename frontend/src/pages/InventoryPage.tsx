import { useState, useEffect } from 'react';
import { Package, AlertTriangle, TrendingDown, ShoppingCart, RefreshCw, Filter, Search, X } from 'lucide-react';

interface InventoryProduct {
  product_id: string;
  product_name: string;
  sku: string;
  current_status: {
    stock_level: number;
    reserved: number;
    available: number;
    incoming: number;
    status: string;
    status_icon: string;
  };
  velocity: {
    daily_average: number;
    weekly_average: number;
    monthly_average: number;
    trend: string;
    trend_percentage: number;
    confidence: number;
  };
  forecast: {
    days_of_stock: number;
    stockout_date: string;
    units_needed_30d: number;
    units_needed_60d: number;
    units_needed_90d: number;
  };
  reorder: {
    reorder_point: number;
    should_reorder: boolean;
    reorder_urgency: string;
    recommended_quantity: number;
    recommended_order_date: string;
    estimated_cost: number;
    supplier_lead_time_days: number;
  };
  safety_stock: {
    recommended: number;
    current_buffer_days: number;
    service_level: number;
  };
  risk_assessment: {
    stockout_risk: string;
    risk_score: number;
    probability_30d: number;
    revenue_at_risk: number;
  };
}

interface InventoryResponse {
  success: boolean;
  count: number;
  products: InventoryProduct[];
}

export const InventoryPage = () => {
  const [inventory, setInventory] = useState<InventoryProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedProduct, setSelectedProduct] = useState<InventoryProduct | null>(null);

  useEffect(() => {
    fetchInventory();
  }, []);

  const fetchInventory = async () => {
    setLoading(true);
    try {
      // Use Shopify real inventory data instead of mock data
      const response = await fetch('http://localhost:8001/api/inventory/shopify/products');
      const data: InventoryResponse = await response.json();
      if (data.success) {
        setInventory(data.products);
      }
    } catch (error) {
      console.error('Failed to fetch inventory:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'HEALTHY': return 'text-green-400 bg-green-400/10';
      case 'LOW': return 'text-yellow-400 bg-yellow-400/10';
      case 'CRITICAL': return 'text-orange-400 bg-orange-400/10';
      case 'OUT_OF_STOCK': return 'text-red-400 bg-red-400/10';
      default: return 'text-gray-400 bg-gray-400/10';
    }
  };

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'CRITICAL': return 'bg-red-500';
      case 'URGENT': return 'bg-orange-500';
      case 'SOON': return 'bg-yellow-500';
      default: return 'bg-blue-500';
    }
  };

  // Calculate summary stats
  const stats = {
    total: inventory.length,
    healthy: inventory.filter(p => p.current_status.status === 'HEALTHY').length,
    low: inventory.filter(p => p.current_status.status === 'LOW').length,
    critical: inventory.filter(p => p.current_status.status === 'CRITICAL').length,
    outOfStock: inventory.filter(p => p.current_status.status === 'OUT_OF_STOCK').length,
    needReorder: inventory.filter(p => p.reorder.should_reorder).length,
  };

  // Filter products
  const filteredProducts = inventory.filter(product => {
    const matchesSearch = product.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         product.sku.toLowerCase().includes(searchTerm.toLowerCase());

    if (!matchesSearch) return false;

    if (filter === 'all') return true;
    if (filter === 'reorder') return product.reorder.should_reorder;
    return product.current_status.status === filter;
  });

  return (
    <div className="p-6 min-h-screen">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent mb-2">
              Inventory Management
            </h1>
            <p className="text-gray-400">Monitor stock levels, velocity, and reorder recommendations</p>
          </div>
          <button
            onClick={fetchInventory}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-blue-500/10 rounded-lg">
                <Package className="w-5 h-5 text-blue-400" />
              </div>
              <span className="text-2xl font-bold text-white">{stats.total}</span>
            </div>
            <p className="text-gray-400 text-sm">Total Products</p>
            <p className="text-green-400 text-xs mt-1">{stats.healthy} healthy</p>
          </div>

          <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-yellow-500/10 rounded-lg">
                <TrendingDown className="w-5 h-5 text-yellow-400" />
              </div>
              <span className="text-2xl font-bold text-white">{stats.low}</span>
            </div>
            <p className="text-gray-400 text-sm">Low Stock</p>
            <p className="text-yellow-400 text-xs mt-1">Needs attention</p>
          </div>

          <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-orange-500/10 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-orange-400" />
              </div>
              <span className="text-2xl font-bold text-white">{stats.critical}</span>
            </div>
            <p className="text-gray-400 text-sm">Critical Stock</p>
            <p className="text-orange-400 text-xs mt-1">Urgent reorder</p>
          </div>

          <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-red-500/10 rounded-lg">
                <ShoppingCart className="w-5 h-5 text-red-400" />
              </div>
              <span className="text-2xl font-bold text-white">{stats.outOfStock}</span>
            </div>
            <p className="text-gray-400 text-sm">Out of Stock</p>
            <p className="text-red-400 text-xs mt-1">{stats.needReorder} need reorder</p>
          </div>
        </div>

        {/* Filters and Search */}
        <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-4">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search products or SKU..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-gray-800/50 border border-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-400" />
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="px-4 py-2 bg-gray-800/50 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
              >
                <option value="all">All Products</option>
                <option value="HEALTHY">Healthy</option>
                <option value="LOW">Low Stock</option>
                <option value="CRITICAL">Critical</option>
                <option value="OUT_OF_STOCK">Out of Stock</option>
                <option value="reorder">Needs Reorder</option>
              </select>
            </div>
          </div>
        </div>

        {/* Inventory Table */}
        <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left p-4 text-gray-400 font-medium text-sm">Product</th>
                  <th className="text-left p-4 text-gray-400 font-medium text-sm">Status</th>
                  <th className="text-left p-4 text-gray-400 font-medium text-sm">Stock</th>
                  <th className="text-left p-4 text-gray-400 font-medium text-sm">Velocity</th>
                  <th className="text-left p-4 text-gray-400 font-medium text-sm">Days Left</th>
                  <th className="text-left p-4 text-gray-400 font-medium text-sm">Reorder</th>
                  <th className="text-left p-4 text-gray-400 font-medium text-sm">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-gray-400">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                      Loading inventory...
                    </td>
                  </tr>
                ) : filteredProducts.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-gray-400">
                      No products found
                    </td>
                  </tr>
                ) : (
                  filteredProducts.map((product) => (
                    <tr key={product.product_id} className="hover:bg-gray-800/50 transition-colors">
                      {/* Product */}
                      <td className="p-4">
                        <div>
                          <p className="text-white font-medium">{product.product_name}</p>
                          <p className="text-gray-400 text-sm">
                            SKU: {product.sku || <span className="text-orange-400">No SKU set</span>}
                          </p>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="p-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${getStatusColor(product.current_status.status)}`}>
                          <span>{product.current_status.status_icon}</span>
                          {product.current_status.status.replace('_', ' ')}
                        </span>
                      </td>

                      {/* Stock */}
                      <td className="p-4">
                        <div>
                          <p className="text-white font-medium">{product.current_status.stock_level}</p>
                          <p className="text-gray-400 text-xs">
                            {product.current_status.available} available
                            {product.current_status.reserved > 0 && ` · ${product.current_status.reserved} reserved`}
                          </p>
                        </div>
                      </td>

                      {/* Velocity */}
                      <td className="p-4">
                        <div>
                          {product.velocity.daily_average === 0 ? (
                            <>
                              <p className="text-gray-400">No sales yet</p>
                              <p className="text-gray-500 text-xs">New product</p>
                            </>
                          ) : (
                            <>
                              <p className="text-white">{product.velocity.daily_average.toFixed(1)}/day</p>
                              <p className="text-gray-400 text-xs">
                                {product.velocity.weekly_average.toFixed(0)}/week
                              </p>
                            </>
                          )}
                        </div>
                      </td>

                      {/* Days Left */}
                      <td className="p-4">
                        <div>
                          <p className={`font-medium ${
                            product.forecast.days_of_stock === 0 ? 'text-red-400' :
                            product.forecast.days_of_stock >= 999 ? 'text-gray-400' :
                            product.forecast.days_of_stock < 7 ? 'text-orange-400' :
                            product.forecast.days_of_stock < 14 ? 'text-yellow-400' :
                            'text-green-400'
                          }`}>
                            {product.forecast.days_of_stock === 0 ? 'Out' :
                             product.forecast.days_of_stock >= 999 ? 'Unlimited' :
                             `${Math.floor(product.forecast.days_of_stock)}d`}
                          </p>
                          {product.forecast.days_of_stock > 0 && product.forecast.days_of_stock < 999 && product.forecast.stockout_date && (
                            <p className="text-gray-400 text-xs">
                              {new Date(product.forecast.stockout_date).toLocaleDateString()}
                            </p>
                          )}
                        </div>
                      </td>

                      {/* Reorder */}
                      <td className="p-4">
                        {product.reorder.should_reorder ? (
                          <div>
                            <div className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium text-white ${getUrgencyColor(product.reorder.reorder_urgency)}`}>
                              {product.reorder.reorder_urgency}
                            </div>
                            <p className="text-gray-400 text-xs mt-1">
                              Order {product.reorder.recommended_quantity} units
                            </p>
                            <p className="text-gray-400 text-xs">
                              ${product.reorder.estimated_cost.toFixed(2)}
                            </p>
                          </div>
                        ) : (
                          <span className="text-gray-500 text-sm">No action needed</span>
                        )}
                      </td>

                      {/* Action */}
                      <td className="p-4">
                        <button
                          onClick={() => setSelectedProduct(product)}
                          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Summary Footer */}
        <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">
              Showing {filteredProducts.length} of {stats.total} products
            </span>
            {stats.needReorder > 0 && (
              <span className="text-orange-400 font-medium">
                {stats.needReorder} product{stats.needReorder !== 1 ? 's' : ''} need immediate reorder
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Product Details Modal */}
      {selectedProduct && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setSelectedProduct(null)}>
          <div className="bg-gray-900 border border-gray-800 rounded-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-800">
              <div>
                <h2 className="text-2xl font-bold text-white">{selectedProduct.product_name}</h2>
                <p className="text-gray-400 text-sm mt-1">
                  SKU: {selectedProduct.sku || <span className="text-orange-400">No SKU set</span>}
                </p>
              </div>
              <button
                onClick={() => setSelectedProduct(null)}
                className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-6">
              {/* Current Status */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-3">Current Status</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-800/50 rounded-lg p-4">
                    <p className="text-gray-400 text-sm">Stock Level</p>
                    <p className="text-2xl font-bold text-white mt-1">{selectedProduct.current_status.stock_level}</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-4">
                    <p className="text-gray-400 text-sm">Available</p>
                    <p className="text-2xl font-bold text-green-400 mt-1">{selectedProduct.current_status.available}</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-4">
                    <p className="text-gray-400 text-sm">Reserved</p>
                    <p className="text-2xl font-bold text-yellow-400 mt-1">{selectedProduct.current_status.reserved}</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-4">
                    <p className="text-gray-400 text-sm">Status</p>
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${getStatusColor(selectedProduct.current_status.status)} mt-1`}>
                      <span>{selectedProduct.current_status.status_icon}</span>
                      {selectedProduct.current_status.status}
                    </span>
                  </div>
                </div>
              </div>

              {/* Velocity */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-3">Sales Velocity</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-gray-800/50 rounded-lg p-4">
                    <p className="text-gray-400 text-sm">Daily</p>
                    <p className="text-xl font-bold text-white mt-1">{selectedProduct.velocity.daily_average.toFixed(1)}</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-4">
                    <p className="text-gray-400 text-sm">Weekly</p>
                    <p className="text-xl font-bold text-white mt-1">{selectedProduct.velocity.weekly_average.toFixed(1)}</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-4">
                    <p className="text-gray-400 text-sm">Monthly</p>
                    <p className="text-xl font-bold text-white mt-1">{selectedProduct.velocity.monthly_average.toFixed(1)}</p>
                  </div>
                </div>
              </div>

              {/* Forecast */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-3">Forecast</h3>
                <div className="bg-gray-800/50 rounded-lg p-4 space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Days of Stock</span>
                    <span className="text-white font-medium">
                      {selectedProduct.forecast.days_of_stock >= 999 ? 'Unlimited' : `${Math.floor(selectedProduct.forecast.days_of_stock)} days`}
                    </span>
                  </div>
                  {selectedProduct.forecast.stockout_date && selectedProduct.forecast.days_of_stock < 999 && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Est. Stockout Date</span>
                      <span className="text-orange-400 font-medium">
                        {new Date(selectedProduct.forecast.stockout_date).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-gray-400">Units Needed (30d)</span>
                    <span className="text-white font-medium">{selectedProduct.forecast.units_needed_30d}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Units Needed (60d)</span>
                    <span className="text-white font-medium">{selectedProduct.forecast.units_needed_60d}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Units Needed (90d)</span>
                    <span className="text-white font-medium">{selectedProduct.forecast.units_needed_90d}</span>
                  </div>
                </div>
              </div>

              {/* Reorder Info */}
              {selectedProduct.reorder.should_reorder && (
                <div>
                  <h3 className="text-lg font-semibold text-white mb-3">Reorder Recommendation</h3>
                  <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5 text-orange-400" />
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium text-white ${getUrgencyColor(selectedProduct.reorder.reorder_urgency)}`}>
                        {selectedProduct.reorder.reorder_urgency}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-300">Recommended Quantity</span>
                      <span className="text-white font-medium">{selectedProduct.reorder.recommended_quantity} units</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-300">Estimated Cost</span>
                      <span className="text-white font-medium">${selectedProduct.reorder.estimated_cost.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-300">Supplier Lead Time</span>
                      <span className="text-white font-medium">{selectedProduct.reorder.supplier_lead_time_days} days</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Risk Assessment */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-3">Risk Assessment</h3>
                <div className="bg-gray-800/50 rounded-lg p-4 space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Stockout Risk</span>
                    <span className={`font-medium ${
                      selectedProduct.risk_assessment.stockout_risk === 'CRITICAL' ? 'text-red-400' :
                      selectedProduct.risk_assessment.stockout_risk === 'HIGH' ? 'text-orange-400' :
                      selectedProduct.risk_assessment.stockout_risk === 'MEDIUM' ? 'text-yellow-400' :
                      'text-green-400'
                    }`}>
                      {selectedProduct.risk_assessment.stockout_risk}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Risk Score</span>
                    <span className="text-white font-medium">{selectedProduct.risk_assessment.risk_score.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Probability (30d)</span>
                    <span className="text-white font-medium">{(selectedProduct.risk_assessment.probability_30d * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Revenue at Risk</span>
                    <span className="text-red-400 font-medium">${selectedProduct.risk_assessment.revenue_at_risk.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
