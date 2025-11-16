import React, { useState, useEffect } from 'react';
import { Mail, TrendingUp, Clock, CheckCircle } from 'lucide-react';

interface EmailStats {
  summary?: {
    processed_today?: number;
    processed_week?: number;
    auto_replied_today?: number;
  };
  response_rate?: number;
}

interface Email {
  from: string;
  subject: string;
  category: string;
  date?: string;
  auto_replied?: boolean;
}

export default function EmailDashboard() {
  const [stats, setStats] = useState<EmailStats | null>(null);
  const [recentEmails, setRecentEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEmailData();
  }, []);

  const fetchEmailData = async () => {
    try {
      // Fetch email stats
      const statsRes = await fetch('http://localhost:8000/api/dashboard/emails');
      const statsData = await statsRes.json();

      // Fetch recent emails
      const emailsRes = await fetch('http://localhost:8000/api/emails/recent?limit=20');
      const emailsData = await emailsRes.json();

      setStats(statsData);
      setRecentEmails(emailsData.emails || []);
    } catch (err) {
      console.error('Error fetching email data:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading email data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">Email Dashboard</h2>
        <p className="text-gray-600">Monitor email automation and customer support metrics</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg p-6 border border-gray-200 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Mail className="w-5 h-5 text-blue-600" />
            </div>
            <h3 className="text-gray-600 text-sm font-medium">Today</h3>
          </div>
          <p className="text-3xl font-bold text-gray-800">
            {stats?.summary?.processed_today || 0}
          </p>
          <p className="text-sm text-gray-500 mt-1">Emails processed</p>
        </div>

        <div className="bg-white rounded-lg p-6 border border-gray-200 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-green-100 rounded-lg">
              <TrendingUp className="w-5 h-5 text-green-600" />
            </div>
            <h3 className="text-gray-600 text-sm font-medium">This Week</h3>
          </div>
          <p className="text-3xl font-bold text-gray-800">
            {stats?.summary?.processed_week || 0}
          </p>
          <p className="text-sm text-gray-500 mt-1">Total processed</p>
        </div>

        <div className="bg-white rounded-lg p-6 border border-gray-200 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-100 rounded-lg">
              <CheckCircle className="w-5 h-5 text-purple-600" />
            </div>
            <h3 className="text-gray-600 text-sm font-medium">Auto-Replied</h3>
          </div>
          <p className="text-3xl font-bold text-gray-800">
            {stats?.summary?.auto_replied_today || 0}
          </p>
          <p className="text-sm text-gray-500 mt-1">Automated today</p>
        </div>

        <div className="bg-white rounded-lg p-6 border border-gray-200 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-orange-100 rounded-lg">
              <Clock className="w-5 h-5 text-orange-600" />
            </div>
            <h3 className="text-gray-600 text-sm font-medium">Response Rate</h3>
          </div>
          <p className="text-3xl font-bold text-gray-800">
            {stats?.response_rate?.toFixed(1) || 0}%
          </p>
          <p className="text-sm text-gray-500 mt-1">Auto-reply success</p>
        </div>
      </div>

      {/* Recent Emails Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-800">Recent Emails</h2>
          <p className="text-sm text-gray-600 mt-1">Latest customer communications</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  From
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Subject
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Category
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {recentEmails.length > 0 ? (
                recentEmails.map((email, idx) => (
                  <tr key={idx} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {email.from}
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-gray-800">
                      {email.subject}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800 border border-blue-200">
                        {email.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {email.date ? new Date(email.date).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="px-6 py-4 text-center">
                      {email.auto_replied ? (
                        <span className="inline-flex px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">
                          Auto-replied
                        </span>
                      ) : (
                        <span className="inline-flex px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-600">
                          Manual
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                    <Mail className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                    <p className="text-lg font-medium text-gray-600">No emails yet</p>
                    <p className="text-sm text-gray-500 mt-1">Email data will appear here once processed</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
