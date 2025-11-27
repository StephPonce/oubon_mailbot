import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ShoppingCart, Package, User, Calendar, X, DollarSign, Clock, CheckCircle, TrendingUp } from 'lucide-react';

interface Order {
  id: number;
  shopify_order_id: string;
  shopify_order_number: string;
  customer_name: string;
  product_name: string;
  quantity: number;
  total_price: number;
  fulfillment_status: 'fulfilled' | 'unfulfilled' | 'shipped' | 'delivered';
  created_at: string; // Or Date
}

export const OrdersPage: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [trackingNumber, setTrackingNumber] = useState('');
  const [trackingUrl, setTrackingUrl] = useState('');
  const [trackingCompany, setTrackingCompany] = useState('Other');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchOrders();
  }, []);

  const fetchOrders = async () => {
    try {
      const response = await axios.get('http://127.0.0.1:8000/api/dashboard/v2/orders');
      setOrders(response.data.orders);
    } catch (error) {
      console.error('Failed to fetch orders:', error);
    } finally {
      setLoading(false);
    }
  };

  const addTracking = async () => {
    if (!selectedOrder || !trackingNumber || !trackingUrl) {
      alert('Please fill in all tracking fields');
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(
        `http://127.0.0.1:8000/api/dashboard/v2/orders/${selectedOrder.shopify_order_id}/tracking`,
        null,
        {
          params: {
            tracking_number: trackingNumber,
            tracking_url: trackingUrl,
            tracking_company: trackingCompany
          }
        }
      );
      alert('Tracking added! Shopify updated & customer emailed.');
      setSelectedOrder(null);
      setTrackingNumber('');
      setTrackingUrl('');
      setTrackingCompany('Other');
      fetchOrders();
    } catch (error) {
      console.error('Failed to add tracking:', error);
      alert('Failed to add tracking');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'shipped': return 'bg-blue-500/20 text-blue-300';
      case 'unfulfilled': return 'bg-yellow-500/20 text-yellow-300';
      case 'delivered': return 'bg-success-green/20 text-success-green';
      default: return 'bg-gray-500/20 text-gray-300';
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-[calc(100vh-10rem)]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-blue mx-auto"></div>
          <p className="mt-4 text-gray-400">Loading orders...</p>
        </div>
      </div>
    );
  }

  // Calculate stats
  const stats = {
    total: orders.length,
    pending: orders.filter(o => o.fulfillment_status === 'unfulfilled').length,
    shipped: orders.filter(o => o.fulfillment_status === 'shipped' || o.fulfillment_status === 'delivered').length,
    revenue: orders.reduce((sum, o) => sum + o.total_price, 0),
  };

  return (
    <div className="space-y-6 px-8 py-6">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent mb-2">
          Order Management
        </h2>
        <p className="text-gray-400">Track and fulfill customer orders</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <ShoppingCart className="w-5 h-5 text-blue-400" />
            </div>
            <span className="text-2xl font-bold text-white">{stats.total}</span>
          </div>
          <p className="text-gray-400 text-sm">Total Orders</p>
          <p className="text-blue-400 text-xs mt-1">All time</p>
        </div>

        <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2 bg-yellow-500/10 rounded-lg">
              <Clock className="w-5 h-5 text-yellow-400" />
            </div>
            <span className="text-2xl font-bold text-white">{stats.pending}</span>
          </div>
          <p className="text-gray-400 text-sm">Pending Orders</p>
          <p className="text-yellow-400 text-xs mt-1">Need fulfillment</p>
        </div>

        <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2 bg-green-500/10 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-400" />
            </div>
            <span className="text-2xl font-bold text-white">{stats.shipped}</span>
          </div>
          <p className="text-gray-400 text-sm">Shipped</p>
          <p className="text-green-400 text-xs mt-1">Completed</p>
        </div>

        <div className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2 bg-purple-500/10 rounded-lg">
              <DollarSign className="w-5 h-5 text-purple-400" />
            </div>
            <span className="text-2xl font-bold text-white">${stats.revenue.toFixed(2)}</span>
          </div>
          <p className="text-gray-400 text-sm">Total Revenue</p>
          <p className="text-purple-400 text-xs mt-1">From all orders</p>
        </div>
      </div>

      {orders.length === 0 ? (
        <div className="text-center py-20 bg-gray-900/50 border-2 border-dashed border-gray-800 rounded-xl">
          <ShoppingCart className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-400">No Orders Yet</h3>
          <p className="text-gray-500 mt-1">New orders from your stores will appear here.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <div key={order.id} className="bg-gray-900/50 backdrop-blur-lg border border-gray-800 rounded-xl p-4 md:p-6 hover:border-gray-700 transition-all">
              <div className="grid grid-cols-1 md:grid-cols-6 gap-4 items-center">
                <div className="md:col-span-2">
                  <p className="font-bold text-lg text-gray-200">#{order.shopify_order_number}</p>
                  <p className="text-sm text-gray-400 flex items-center gap-2"><User size={14}/> {order.customer_name}</p>
                </div>
                <div className="md:col-span-2">
                  <p className="font-medium text-gray-300 flex items-center gap-2"><Package size={14} /> {order.product_name}</p>
                  <p className="text-sm text-gray-500">Qty: {order.quantity}</p>
                </div>
                <div className="text-lg font-semibold text-gray-200">
                  ${order.total_price.toFixed(2)}
                </div>
                <div className="flex flex-col items-start md:items-end gap-2">
                  <span className={`px-3 py-1 text-xs font-semibold rounded-full ${getStatusColor(order.fulfillment_status)}`}>
                    {order.fulfillment_status}
                  </span>
                  <p className="text-xs text-gray-500 flex items-center gap-1"><Calendar size={12} /> {new Date(order.created_at).toLocaleDateString()}</p>
                </div>
                <div className="md:text-right">
                  {order.fulfillment_status === 'unfulfilled' ? (
                    <button
                      onClick={() => setSelectedOrder(order)}
                      className="px-4 py-2 bg-brand-blue text-white rounded-lg font-semibold hover:opacity-90 transition text-sm"
                    >
                      Add Tracking
                    </button>
                  ) : (
                    <span className="text-sm font-semibold text-success-green">✓ Shipped</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Tracking Modal */}
      {selectedOrder && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setSelectedOrder(null)}>
          <div className="bg-gray-950/80 backdrop-blur-xl border border-gray-800 rounded-2xl p-8 max-w-md w-full shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-gray-100">Add Tracking</h2>
              <button onClick={() => setSelectedOrder(null)} className="p-1 rounded-full hover:bg-white/10 text-gray-500 hover:text-white transition"><X size={20}/></button>
            </div>

            <div className="mb-6 bg-gray-800/50 p-4 rounded-lg">
              <p className="text-sm text-gray-400">Order #{selectedOrder.shopify_order_number}</p>
              <p className="font-semibold text-gray-200">{selectedOrder.product_name}</p>
            </div>

            <div className="space-y-4">
              {/* Inputs with labels */}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Tracking Number</label>
                <input
                  type="text"
                  value={trackingNumber}
                  onChange={(e) => setTrackingNumber(e.target.value)}
                  placeholder="e.g., 1Z999AA10123456784"
                  className="w-full bg-gray-800/70 border border-gray-700 rounded-lg px-4 py-2 text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-blue"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Tracking URL</label>
                <input
                  type="url"
                  value={trackingUrl}
                  onChange={(e) => setTrackingUrl(e.target.value)}
                  placeholder="e.g., https://track.aftership.com/..."
                  className="w-full bg-gray-800/70 border border-gray-700 rounded-lg px-4 py-2 text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-blue"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Carrier</label>
                <select
                  value={trackingCompany}
                  onChange={(e) => setTrackingCompany(e.target.value)}
                  className="w-full bg-gray-800/70 border border-gray-700 rounded-lg px-4 py-2 text-gray-200 appearance-none focus:outline-none focus:ring-2 focus:ring-brand-blue"
                >
                  <option>Other</option>
                  <option>USPS</option>
                  <option>UPS</option>
                  <option>FedEx</option>
                  <option>DHL</option>
                  <option>China Post</option>
                  <option>ePacket</option>
                </select>
              </div>
            </div>

            <div className="flex gap-4 mt-8">
              <button
                onClick={() => setSelectedOrder(null)}
                className="flex-1 bg-gray-800/70 text-gray-300 py-2.5 px-4 rounded-lg hover:bg-gray-700/80 font-semibold transition"
              >
                Cancel
              </button>
              <button
                onClick={addTracking}
                disabled={submitting}
                className="flex-1 bg-brand-blue text-white py-2.5 px-4 rounded-lg hover:opacity-90 font-semibold disabled:bg-gray-600"
              >
                {submitting ? 'Adding...' : 'Add & Notify'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
