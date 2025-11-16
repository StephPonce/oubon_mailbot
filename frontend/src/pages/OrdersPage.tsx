import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Order {
  id: number;
  shopify_order_id: string;
  shopify_order_number: string;
  customer_email: string;
  customer_name: string;
  product_name: string;
  quantity: number;
  total_price: number;
  order_status: string;
  fulfillment_status: string;
  created_at: string;
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

      alert('✅ Tracking added! Shopify updated & customer emailed.');
      setSelectedOrder(null);
      setTrackingNumber('');
      setTrackingUrl('');
      setTrackingCompany('Other');
      fetchOrders();
    } catch (error) {
      console.error('Failed to add tracking:', error);
      alert('❌ Failed to add tracking');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'shipped': return 'bg-blue-100 text-blue-800';
      case 'unfulfilled': return 'bg-yellow-100 text-yellow-800';
      case 'delivered': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-xl text-gray-600">Loading orders...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-800">Orders</h1>
        <p className="text-gray-600 mt-2">Manage customer orders and fulfillment</p>
      </div>

      {orders.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-6xl mb-4">📦</div>
          <h2 className="text-2xl font-semibold text-gray-700 mb-2">No orders yet</h2>
          <p className="text-gray-500">Orders will appear here when customers purchase from your store</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Order #
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Customer
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Product
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Total
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {orders.map((order) => (
                <tr key={order.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">
                      #{order.shopify_order_number}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-900">{order.customer_name}</div>
                    <div className="text-sm text-gray-500">{order.customer_email}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-900">{order.product_name}</div>
                    <div className="text-sm text-gray-500">Qty: {order.quantity}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-semibold text-gray-900">
                      ${order.total_price.toFixed(2)}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(order.fulfillment_status)}`}>
                      {order.fulfillment_status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(order.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {order.fulfillment_status === 'unfulfilled' ? (
                      <button
                        onClick={() => setSelectedOrder(order)}
                        className="text-blue-600 hover:text-blue-900 font-semibold"
                      >
                        Add Tracking
                      </button>
                    ) : (
                      <span className="text-green-600">✓ Shipped</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Tracking Modal */}
      {selectedOrder && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 max-w-md w-full">
            <h2 className="text-2xl font-bold mb-4">Add Tracking Information</h2>

            <div className="mb-4">
              <p className="text-sm text-gray-600 mb-2">
                Order #{selectedOrder.shopify_order_number}
              </p>
              <p className="text-sm font-semibold">{selectedOrder.product_name}</p>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Tracking Number
              </label>
              <input
                type="text"
                value={trackingNumber}
                onChange={(e) => setTrackingNumber(e.target.value)}
                placeholder="1Z999AA10123456784"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Tracking URL
              </label>
              <input
                type="url"
                value={trackingUrl}
                onChange={(e) => setTrackingUrl(e.target.value)}
                placeholder="https://track.aftership.com/..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Carrier
              </label>
              <select
                value={trackingCompany}
                onChange={(e) => setTrackingCompany(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="Other">Other</option>
                <option value="USPS">USPS</option>
                <option value="UPS">UPS</option>
                <option value="FedEx">FedEx</option>
                <option value="DHL">DHL</option>
                <option value="China Post">China Post</option>
                <option value="ePacket">ePacket</option>
              </select>
            </div>

            <div className="flex gap-3">
              <button
                onClick={addTracking}
                disabled={submitting}
                className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 font-semibold disabled:bg-gray-400"
              >
                {submitting ? 'Adding...' : 'Add Tracking'}
              </button>
              <button
                onClick={() => {
                  setSelectedOrder(null);
                  setTrackingNumber('');
                  setTrackingUrl('');
                  setTrackingCompany('Other');
                }}
                className="flex-1 bg-gray-200 text-gray-800 py-2 px-4 rounded-md hover:bg-gray-300 font-semibold"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
