import { Mail, Send, Clock, CheckCircle2, AlertCircle, Inbox, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useEmailMetrics } from '../../hooks/useData';

interface EmailOverviewProps {
  delay?: number;
}

export function EmailOverview({ delay = 0 }: EmailOverviewProps) {
  const navigate = useNavigate();
  const { data: emailData, isLoading, isError } = useEmailMetrics();

  if (isLoading) {
    return (
      <div className="glass-card p-6 animate-fadeIn" style={{ animationDelay: `${delay}ms` }}>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
        </div>
      </div>
    );
  }

  if (isError || !emailData) {
    return (
      <div className="glass-card p-6 animate-fadeIn" style={{ animationDelay: `${delay}ms` }}>
        <div className="flex items-center gap-3 mb-4">
          <Mail className="w-5 h-5 text-accent" />
          <h3 className="text-lg font-semibold text-primary">Email Automation</h3>
        </div>
        <div className="flex items-center gap-2 text-tertiary">
          <AlertCircle className="w-4 h-4" />
          <span className="text-sm">Unable to load email metrics</span>
        </div>
      </div>
    );
  }

  const { stats, performance, recentEmails } = emailData;
  const processedToday = stats?.summary?.processed_today || 0;
  const autoRepliedToday = stats?.summary?.auto_replied_today || 0;
  const responseRate = stats?.response_rate || 0;
  const avgResponseTime = performance?.avg_response_time_ms || 0;

  // Determine operating status
  const currentHour = new Date().getHours();
  const isOperatingHours = currentHour >= 9 && currentHour < 18; // 9 AM - 6 PM
  const statusColor = isOperatingHours ? 'text-green-600 bg-green-500/100/10' : 'text-amber-600 bg-amber-500/10';
  const statusText = isOperatingHours ? 'Operating Hours' : 'Quiet Hours';

  return (
    <div
      className="glass-card p-6 animate-fadeIn"
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="stat-card-icon bg-accent/10">
            <Mail className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-primary">Email Automation</h3>
            <p className="text-xs text-tertiary">AI-powered inbox management</p>
          </div>
        </div>
        <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${statusColor}`}>
          <div className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
          {statusText}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {/* Emails Received Today */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Inbox className="w-4 h-4 text-tertiary" />
            <span className="text-xs text-tertiary">Received Today</span>
          </div>
          <div className="text-2xl font-bold text-primary">{processedToday}</div>
        </div>

        {/* Auto-Replies Sent */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Send className="w-4 h-4 text-tertiary" />
            <span className="text-xs text-tertiary">Auto-Replies</span>
          </div>
          <div className="text-2xl font-bold text-accent">{autoRepliedToday}</div>
        </div>

        {/* Response Rate */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-tertiary" />
            <span className="text-xs text-tertiary">Response Rate</span>
          </div>
          <div className="text-2xl font-bold text-green-600">{responseRate.toFixed(1)}%</div>
        </div>

        {/* Avg Response Time */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-tertiary" />
            <span className="text-xs text-tertiary">Avg Time</span>
          </div>
          <div className="text-2xl font-bold text-primary">
            {avgResponseTime < 1000
              ? `${avgResponseTime.toFixed(0)}ms`
              : `${(avgResponseTime / 1000).toFixed(1)}s`}
          </div>
        </div>
      </div>

      {/* Recent Emails */}
      {recentEmails && recentEmails.length > 0 && (
        <div className="border-t border-black/5 pt-4 mb-4">
          <div className="text-xs font-medium text-secondary mb-3">Recent Activity</div>
          <div className="space-y-2">
            {recentEmails.map((email: any, idx: number) => (
              <div
                key={email.id || idx}
                className="flex items-center justify-between p-2 rounded-lg hover:bg-black/5 transition-colors cursor-pointer"
                onClick={() => navigate('/emails')}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-primary truncate">
                    {email.subject || 'No Subject'}
                  </div>
                  <div className="text-xs text-tertiary truncate">
                    {email.from || 'Unknown Sender'}
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-2">
                  {email.category && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-black/5 text-secondary">
                      {email.category}
                    </span>
                  )}
                  {email.auto_replied && (
                    <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="flex items-center gap-2 border-t border-black/5 pt-4">
        <button
          className="btn-ghost text-sm flex-1"
          onClick={() => navigate('/emails')}
        >
          <Inbox className="w-4 h-4" />
          <span>View Inbox</span>
        </button>
        <button
          className="btn-primary text-sm flex-1"
          onClick={() => navigate('/emails')}
        >
          <span>Manage Rules</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
