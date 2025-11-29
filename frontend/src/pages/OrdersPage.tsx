import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ShoppingCart, Package, User, Calendar, X, DollarSign, Clock, CheckCircle, TrendingUp } from 'lucide-react';
import { GlassPanel } from '@/components/GlassPanel';

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
      case 'shipped': return 'bg-blue-500/20 text-blue-600';
      case 'unfulfilled': return 'bg-yellow-500/20 text-yellow-600';
      case 'delivered': return 'bg-green-500/20 text-green-600';
      default: return 'bg-gray-500/20 text-gray-700';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-12 flex items-center justify-center" style={{ perspective: '1500px' }}>
        <GlassPanel depth={60} delay={0}>
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto mb-4"></div>
            <p className="text-gray-600 font-light">Loading orders...</p>
          </div>
        </GlassPanel>
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
    <div className="min-h-screen bg-gray-50 p-12" style={{ perspective: '1500px' }}>
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <GlassPanel depth={80} delay={0.1}>
          <div>
            <h2 className="text-3xl font-light text-gray-900 mb-2">
              Order Management
            </h2>
            <p className="text-gray-600">Track and fulfill customer orders</p>
          </div>
        </GlassPanel>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <GlassPanel depth={70} delay={0.15}>
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-blue-500/10 rounded-lg">
                <ShoppingCart className="w-5 h-5 text-blue-600" />
              </div>
              <span className="text-2xl font-light text-gray-900">{stats.total}</span>
            </div>
            <p className="text-gray-600 text-sm">Total Orders</p>
            <p className="text-blue-600 text-xs mt-1">All time</p>
          </GlassPanel>

          <GlassPanel depth={70} delay={0.2}>
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-yellow-500/10 rounded-lg">
                <Clock className="w-5 h-5 text-yellow-600" />
              </div>
              <span className="text-2xl font-light text-gray-900">{stats.pending}</span>
            </div>
            <p className="text-gray-600 text-sm">Pending Orders</p>
            <p className="text-yellow-600 text-xs mt-1">Need fulfillment</p>
          </GlassPanel>

          <GlassPanel depth={70} delay={0.25}>
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-green-500/10 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-600" />
              </div>
              <span className="text-2xl font-light text-gray-900">{stats.shipped}</span>
            </div>
            <p className="text-gray-600 text-sm">Shipped</p>
            <p className="text-green-600 text-xs mt-1">Completed</p>
          </GlassPanel>

          <GlassPanel depth={70} delay={0.3}>
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 bg-purple-500/10 rounded-lg">
                <DollarSign className="w-5 h-5 text-purple-600" />
              </div>
              <span className="text-2xl font-light text-gray-900">${stats.revenue.toFixed(2)}</span>
            </div>
            <p className="text-gray-600 text-sm">Total Revenue</p>
            <p className="text-purple-600 text-xs mt-1">From all orders</p>
          </GlassPanel>
        </div>

        {orders.length === 0 ? (
          <GlassPanel depth={60} delay={0.4}>
            <div className="text-center py-20">
              <ShoppingCart className="w-16 h-16 text-gray-400 mx-auto mb-4 opacity-30" />
              <h3 className="text-xl font-light text-gray-600">No Orders Yet</h3>
              <p className="text-gray-500 mt-1">New orders from your stores will appear here.</p>
            </div>
          </GlassPanel>
        ) : (
          <div className="space-y-4">
            {orders.map((order, idx) => (
              <GlassPanel key={order.id} depth={55} delay={0.35 + idx * 0.02}>
                <div className="grid grid-cols-1 md:grid-cols-6 gap-4 items-center">
                  <div className="md:col-span-2">
                    <p className="font-light text-lg text-gray-900">#{order.shopify_order_number}</p>
                    <p className="text-sm text-gray-600 flex items-center gap-2"><User size={14}/> {order.customer_name}</p>
                  </div>
                  <div className="md:col-span-2">
                    <p className="font-light text-gray-900 flex items-center gap-2"><Package size={14} /> {order.product_name}</p>
                    <p className="text-sm text-gray-500">Qty: {order.quantity}</p>
                  </div>
                  <div className="text-lg font-light text-gray-900">
                    ${order.total_price.toFixed(2)}
                  </div>
                  <div className="flex flex-col items-start md:items-end gap-2">
                    <span className={`px-3 py-1 text-xs font-light rounded-full ${getStatusColor(order.fulfillment_status)}`}>
                      {order.fulfillment_status}
                    </span>
                    <p className="text-xs text-gray-500 flex items-center gap-1"><Calendar size={12} /> {new Date(order.created_at).toLocaleDateString()}</p>
                  </div>
                  <div className="md:text-right">
                    {order.fulfillment_status === 'unfulfilled' ? (
                      <button
                        onClick={() => setSelectedOrder(order)}
                        className="px-4 py-2 bg-gray-900 text-white rounded-lg font-light hover:bg-gray-800 transition text-sm"
                      >
                        Add Tracking
                      </button>
                    ) : (
                      <span className="text-sm font-light text-green-600">✓ Shipped</span>
                    )}
                  </div>
                </div>
              </GlassPanel>
            ))}
          </div>
        )}

        {/* Add Tracking Modal */}
        {selectedOrder && (
          <div className="fixed inset-0 bg-gray-900/40 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setSelectedOrder(null)}>
            <div className="glass p-8 max-w-md w-full" style={{ boxShadow: '0 40px 120px rgba(0, 0, 0, 0.25)' }} onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-light text-gray-900">Add Tracking</h2>
                <button onClick={() => setSelectedOrder(null)} className="p-1.5 rounded-full hover:bg-gray-900/10 text-gray-500 hover:text-gray-900 transition">
                  <X size={20}/>
                </button>
              </div>

              <div className="mb-6 bg-gray-100/50 p-4 rounded-lg">
                <p className="text-sm text-gray-600">Order #{selectedOrder.shopify_order_number}</p>
                <p className="font-light text-gray-900">{selectedOrder.product_name}</p>
              </div>

              <div className="space-y-4">
                {/* Inputs with labels */}
                <div>
                  <label className="block text-sm font-light text-gray-700 mb-2">Tracking Number</label>
                  <input
                    type="text"
                    value={trackingNumber}
                    onChange={(e) => setTrackingNumber(e.target.value)}
                    placeholder="e.g., 1Z999AA10123456784"
                    className="w-full bg-white/50 border border-gray-200 rounded-lg px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900"
                  />
                </div>
                <div>
                  <label className="block text-sm font-light text-gray-700 mb-2">Tracking URL</label>
                  <input
                    type="url"
                    value={trackingUrl}
                    onChange={(e) => setTrackingUrl(e.target.value)}
                    placeholder="e.g., https://track.aftership.com/..."
                    className="w-full bg-white/50 border border-gray-200 rounded-lg px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900"
                  />
                </div>
                <div>
                  <label className="block text-sm font-light text-gray-700 mb-2">Carrier</label>
                  <select
                    value={trackingCompany}
                    onChange={(e) => setTrackingCompany(e.target.value)}
                    className="w-full bg-white/50 border border-gray-200 rounded-lg px-4 py-2.5 text-gray-900 appearance-none focus:outline-none focus:ring-2 focus:ring-gray-900"
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

              <div className="flex gap-3 mt-8">
                <button
                  onClick={() => setSelectedOrder(null)}
                  className="flex-1 text-gray-700 py-2.5 px-4 rounded-lg hover:bg-gray-900/5 font-light transition"
                >
                  Cancel
                </button>
                <button
                  onClick={addTracking}
                  disabled={submitting}
                  className="flex-1 bg-gray-900 text-white py-2.5 px-4 rounded-lg hover:bg-gray-800 font-light disabled:bg-gray-400 transition"
                >
                  {submitting ? 'Adding...' : 'Add & Notify'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
