/**
 * Ospra Intelligence - Email Dashboard
 * 
 * FULLY FUNCTIONAL:
 * - Real email list from Gmail
 * - Email sync
 * - Reply and ignore actions
 * - Email stats
 */

import { useState } from 'react';
import {
  Mail,
  Inbox,
  Send,
  Archive,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  User,
  ChevronRight,
  Search,
  Filter,
  MoreHorizontal,
  Reply,
  Trash2,
  Star,
  StarOff,
  X,
  ExternalLink,
} from 'lucide-react';

import {
  useEmails,
  useEmailStats,
} from '../hooks/useData';
import { emailAPI } from '../services/api';
import type { Email } from '../services/api';

// =============================================================================
// EMAIL CARD
// =============================================================================

interface EmailCardProps {
  email: Email;
  isSelected: boolean;
  onSelect: (email: Email) => void;
  onReply: (email: Email) => void;
  onIgnore: (email: Email) => void;
  isReplying: boolean;
  isIgnoring: boolean;
}

function EmailCard({ 
  email, 
  isSelected, 
  onSelect, 
  onReply, 
  onIgnore,
  isReplying,
  isIgnoring,
}: EmailCardProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'replied': return 'text-success bg-success/10';
      case 'pending': return 'text-warning bg-warning/10';
      case 'ignored': return 'text-tertiary bg-white/5';
      default: return 'text-tertiary bg-white/5';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'text-error bg-error/10';
      case 'medium': return 'text-warning bg-warning/10';
      case 'low': return 'text-info bg-cyan-500/10';
      default: return 'text-tertiary bg-white/5';
    }
  };

  const timestamp = email.timestamp || email.date 
    ? new Date(email.timestamp || email.date || '').toLocaleString()
    : 'Unknown';

  return (
    <div 
      className={`glass-card p-4 cursor-pointer transition-all ${
        isSelected ? 'ring-2 ring-accent' : 'hover:shadow-md'
      } ${!email.is_read ? 'border-l-4 border-l-accent' : ''}`}
      onClick={() => onSelect(email)}
    >
      <div className="flex items-start gap-4">
        {/* Avatar */}
        <div className="w-10 h-10 rounded-full bg-black/20 flex items-center justify-center flex-shrink-0">
          <User className="w-5 h-5 text-tertiary" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-sm font-medium ${!email.is_read ? 'text-primary' : 'text-secondary'}`}>
              {email.from}
            </span>
            {email.auto_replied && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-success/10 text-success">
                Auto-replied
              </span>
            )}
          </div>
          <h3 className={`text-sm ${!email.is_read ? 'font-medium text-primary' : 'text-secondary'} line-clamp-1`}>
            {email.subject}
          </h3>
          {email.preview && (
            <p className="text-xs text-tertiary line-clamp-1 mt-1">{email.preview}</p>
          )}
          <div className="flex items-center gap-2 mt-2">
            <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(email.status)}`}>
              {email.status}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${getPriorityColor(email.priority)}`}>
              {email.priority}
            </span>
            {email.category && (
              <span className="text-xs text-tertiary">{email.category}</span>
            )}
          </div>
        </div>

        {/* Timestamp & Actions */}
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <span className="text-xs text-tertiary">{timestamp}</span>
          <div className="flex items-center gap-1">
            {email.status === 'pending' && (
              <>
                <button
                  className="p-1.5 hover:bg-white/5 rounded-lg"
                  onClick={(e) => { e.stopPropagation(); onReply(email); }}
                  disabled={isReplying}
                  title="Reply"
                >
                  {isReplying ? (
                    <Loader2 className="w-4 h-4 animate-spin text-accent" />
                  ) : (
                    <Reply className="w-4 h-4 text-accent" />
                  )}
                </button>
                <button
                  className="p-1.5 hover:bg-white/5 rounded-lg"
                  onClick={(e) => { e.stopPropagation(); onIgnore(email); }}
                  disabled={isIgnoring}
                  title="Ignore"
                >
                  {isIgnoring ? (
                    <Loader2 className="w-4 h-4 animate-spin text-tertiary" />
                  ) : (
                    <Archive className="w-4 h-4 text-tertiary" />
                  )}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// EMAIL DETAIL PANEL
// =============================================================================

function EmailDetailPanel({ 
  email, 
  onClose,
  onReply,
  onIgnore,
  isReplying,
  isIgnoring,
}: { 
  email: Email | null; 
  onClose: () => void;
  onReply: (email: Email, message: string) => void;
  onIgnore: (email: Email) => void;
  isReplying: boolean;
  isIgnoring: boolean;
}) {
  const [replyText, setReplyText] = useState('');

  if (!email) {
    return (
      <div className="h-full flex items-center justify-center text-center p-8">
        <div>
          <Mail className="w-12 h-12 text-tertiary mx-auto mb-4" />
          <h3 className="text-lg font-medium text-primary mb-2">Select an Email</h3>
          <p className="text-sm text-secondary">
            Choose an email from the list to view its contents.
          </p>
        </div>
      </div>
    );
  }

  const handleReply = () => {
    if (!replyText.trim()) return;
    onReply(email, replyText);
    setReplyText('');
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h2 className="text-lg font-medium text-primary">{email.subject}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm text-secondary">{email.from}</span>
              {email.from_address && (
                <span className="text-xs text-tertiary">&lt;{email.from_address}&gt;</span>
              )}
            </div>
          </div>
          <button
            className="p-2 hover:bg-white/5 rounded-lg"
            onClick={onClose}
          >
            <ChevronRight className="w-5 h-5 text-tertiary" />
          </button>
        </div>
        <div className="flex items-center gap-2 text-xs text-tertiary">
          <Clock className="w-3.5 h-3.5" />
          <span>{email.timestamp || email.date}</span>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="prose prose-sm max-w-none prose-invert">
          {email.body ? (
            <div dangerouslySetInnerHTML={{ __html: email.body }} />
          ) : email.preview ? (
            <p>{email.preview}</p>
          ) : (
            <p className="text-tertiary">No content available.</p>
          )}
        </div>
      </div>

      {/* Reply Section */}
      {email.status === 'pending' && (
        <div className="p-4 border-t border-white/10">
          <textarea
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            placeholder="Write your reply..."
            className="w-full px-3 py-2 rounded-xl bg-black/20 border border-white/10 focus:border-accent outline-none text-sm resize-none text-primary"
            rows={3}
          />
          <div className="flex items-center justify-between mt-3">
            <button
              className="btn-ghost text-sm"
              onClick={() => onIgnore(email)}
              disabled={isIgnoring}
            >
              {isIgnoring ? <Loader2 className="w-4 h-4 animate-spin" /> : <Archive className="w-4 h-4" />}
              <span>Mark as Ignored</span>
            </button>
            <button
              className="btn-primary text-sm"
              onClick={handleReply}
              disabled={!replyText.trim() || isReplying}
            >
              {isReplying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              <span>Send Reply</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function EmailDashboard() {
  // State
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState('');
  const [replyingEmailId, setReplyingEmailId] = useState<string | null>(null);
  const [ignoringEmailId, setIgnoringEmailId] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [selectedInbox, setSelectedInbox] = useState<string>('primary');
  const [showAddAccountModal, setShowAddAccountModal] = useState(false);

  // Data hooks
  const { data: emails, isLoading: emailsLoading, refetch: refetchEmails } = useEmails(filterStatus);
  const { data: statsData, isLoading: statsLoading, refetch: refetchStats } = useEmailStats();

  // Filter emails by search
  const filteredEmails = (emails || []).filter(email => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      email.subject.toLowerCase().includes(query) ||
      email.from.toLowerCase().includes(query) ||
      (email.preview && email.preview.toLowerCase().includes(query))
    );
  });

  // Stats
  const stats = {
    total: statsData?.total || emails?.length || 0,
    pending: statsData?.pending || emails?.filter(e => e.status === 'pending').length || 0,
    replied: statsData?.replied || emails?.filter(e => e.status === 'replied').length || 0,
    ignored: statsData?.ignored || emails?.filter(e => e.status === 'ignored').length || 0,
    autoReplied: statsData?.auto_replied || emails?.filter(e => e.auto_replied).length || 0,
  };

  // Handlers
  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await emailAPI.sync();
      await refetchEmails();
      await refetchStats();
      alert('✅ Email sync completed!');
    } catch (error) {
      console.error('Sync failed:', error);
      alert('❌ Email sync failed. Check Gmail connection.');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleReply = async (email: Email, message: string) => {
    setReplyingEmailId(email.id);
    try {
      await emailAPI.reply(email.id, message);
      await refetchEmails();
      alert('✅ Reply sent successfully!');
      setSelectedEmail(null);
    } catch (error) {
      console.error('Reply failed:', error);
      alert('❌ Reply failed. Please try again.');
    } finally {
      setReplyingEmailId(null);
    }
  };

  const handleIgnore = async (email: Email) => {
    setIgnoringEmailId(email.id);
    try {
      await emailAPI.markAsIgnored(email.id);
      await refetchEmails();
      if (selectedEmail?.id === email.id) {
        setSelectedEmail(null);
      }
    } catch (error) {
      console.error('Ignore failed:', error);
      alert('❌ Failed to ignore email.');
    } finally {
      setIgnoringEmailId(null);
    }
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex">
      {/* Main List */}
      <div className="flex-1 flex flex-col border-r border-white/10">
        {/* Header */}
        <div className="p-4 border-b border-white/10">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Mail className="w-5 h-5 text-accent" />
              <h1 className="text-lg font-semibold text-primary">Email Automation</h1>
            </div>
            <div className="flex items-center gap-2">
              <button
                className="btn-ghost text-sm"
                onClick={() => setShowAddAccountModal(true)}
                title="Add Email Account"
              >
                <User className="w-4 h-4" />
                <span className="hidden sm:inline">Add Account</span>
              </button>
              <button
                className="btn-primary text-sm"
                onClick={handleSync}
                disabled={isSyncing}
              >
                {isSyncing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4" />
                )}
                <span>Sync</span>
              </button>
            </div>
          </div>

          {/* Inbox Selector & Search */}
          <div className="flex items-center gap-2 mb-3">
            <select
              value={selectedInbox}
              onChange={(e) => setSelectedInbox(e.target.value)}
              className="px-3 py-2 rounded-xl bg-black/20 border border-white/10 focus:border-accent outline-none text-sm font-medium text-primary"
            >
              <option value="primary">Primary</option>
              <option value="social">Social</option>
              <option value="promotions">Promotions</option>
              <option value="updates">Updates</option>
              <option value="forums">Forums</option>
              <option value="all">All Mail</option>
            </select>
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-tertiary" />
              <input
                type="text"
                placeholder="Search emails..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-xl bg-black/20 border border-white/10 focus:border-accent outline-none text-sm text-primary placeholder:text-tertiary"
              />
            </div>
          </div>

          {/* Filter Tabs */}
          <div className="flex items-center gap-2 mt-4">
            {[
              { value: undefined, label: 'All', count: stats.total },
              { value: 'pending', label: 'Pending', count: stats.pending },
              { value: 'replied', label: 'Replied', count: stats.replied },
              { value: 'ignored', label: 'Ignored', count: stats.ignored },
            ].map((tab) => (
              <button
                key={tab.label}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  filterStatus === tab.value 
                    ? 'bg-accent text-white' 
                    : 'bg-white/5 text-secondary hover:bg-white/10'
                }`}
                onClick={() => setFilterStatus(tab.value)}
              >
                {tab.label} ({tab.count})
              </button>
            ))}
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-4 gap-3 p-4 border-b border-white/10">
          <div className="text-center">
            <div className="text-xl font-bold text-primary">{stats.total}</div>
            <div className="text-xs text-tertiary">Total</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-warning">{stats.pending}</div>
            <div className="text-xs text-tertiary">Pending</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-success">{stats.replied}</div>
            <div className="text-xs text-tertiary">Replied</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-accent">{stats.autoReplied}</div>
            <div className="text-xs text-tertiary">Auto-replied</div>
          </div>
        </div>

        {/* Email List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {emailsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-accent animate-spin" />
            </div>
          ) : filteredEmails.length === 0 ? (
            <div className="text-center py-12">
              <Inbox className="w-12 h-12 text-tertiary mx-auto mb-4" />
              <h3 className="text-lg font-medium text-primary mb-2">No Emails</h3>
              <p className="text-sm text-secondary">
                {filterStatus 
                  ? `No ${filterStatus} emails found.` 
                  : 'Click "Sync Emails" to fetch your emails.'}
              </p>
            </div>
          ) : (
            filteredEmails.map((email) => (
              <EmailCard
                key={email.id}
                email={email}
                isSelected={selectedEmail?.id === email.id}
                onSelect={setSelectedEmail}
                onReply={(e) => handleReply(e, '')}
                onIgnore={handleIgnore}
                isReplying={replyingEmailId === email.id}
                isIgnoring={ignoringEmailId === email.id}
              />
            ))
          )}
        </div>
      </div>

      {/* Detail Panel */}
      <div className="w-[320px] hidden lg:block">
        <EmailDetailPanel
          email={selectedEmail}
          onClose={() => setSelectedEmail(null)}
          onReply={handleReply}
          onIgnore={handleIgnore}
          isReplying={replyingEmailId === selectedEmail?.id}
          isIgnoring={ignoringEmailId === selectedEmail?.id}
        />
      </div>

      {/* Add Account Modal */}
      {showAddAccountModal && (
        <>
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={() => setShowAddAccountModal(false)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="glass-card p-6 max-w-md w-full">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-primary">Add Email Account</h2>
                <button
                  onClick={() => setShowAddAccountModal(false)}
                  className="p-2 rounded-lg hover:bg-white/5 text-secondary"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <p className="text-sm text-secondary mb-6">
                Connect your email account to enable automation, smart replies, and inbox management.
              </p>

              <div className="space-y-3">
                {/* Gmail */}
                <button
                  className="w-full p-4 rounded-xl border border-white/10 hover:border-accent hover:bg-white/5 transition-all text-left flex items-center gap-3"
                  onClick={() => {
                    window.location.href = `http://localhost:8001/gmail/auth/start`;
                  }}
                >
                  <img src="https://cdn.simpleicons.org/gmail/EA4335" alt="Gmail" className="w-6 h-6" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-primary">Gmail</div>
                    <div className="text-xs text-secondary">Connect via Google OAuth</div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-secondary" />
                </button>

                {/* Outlook */}
                <button
                  className="w-full p-4 rounded-xl border border-white/10 hover:border-accent hover:bg-white/5 transition-all text-left flex items-center gap-3"
                  onClick={() => {
                    window.location.href = `http://localhost:8001/api/email-oauth/outlook/connect?user_id=1`;
                  }}
                >
                  <img src="https://cdn.simpleicons.org/microsoftoutlook/0078D4" alt="Outlook" className="w-6 h-6" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-primary">Outlook</div>
                    <div className="text-xs text-secondary">Connect via Microsoft OAuth</div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-secondary" />
                </button>

                {/* Yahoo */}
                <button
                  className="w-full p-4 rounded-xl border border-white/10 hover:border-accent hover:bg-white/5 transition-all text-left flex items-center gap-3"
                  onClick={() => {
                    alert('Yahoo Mail: Please contact support for IMAP setup instructions.');
                  }}
                >
                  <img src="https://cdn.simpleicons.org/yahoo/6001D2" alt="Yahoo" className="w-6 h-6" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-primary">Yahoo Mail</div>
                    <div className="text-xs text-secondary">IMAP/SMTP setup required</div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-secondary" />
                </button>

                {/* iCloud */}
                <button
                  className="w-full p-4 rounded-xl border border-white/10 hover:border-accent hover:bg-white/5 transition-all text-left flex items-center gap-3"
                  onClick={() => {
                    alert('iCloud Mail: Please contact support for app-specific password setup.');
                  }}
                >
                  <img src="https://cdn.simpleicons.org/icloud/3693F3" alt="iCloud" className="w-6 h-6" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-primary">iCloud Mail</div>
                    <div className="text-xs text-secondary">App-specific password required</div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-secondary" />
                </button>

                {/* Zoho */}
                <button
                  className="w-full p-4 rounded-xl border border-white/10 hover:border-accent hover:bg-white/5 transition-all text-left flex items-center gap-3"
                  onClick={() => {
                    alert('Zoho Mail: Please contact support for IMAP setup instructions.');
                  }}
                >
                  <img src="https://cdn.simpleicons.org/zoho/C8202E" alt="Zoho" className="w-6 h-6" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-primary">Zoho Mail</div>
                    <div className="text-xs text-secondary">IMAP/SMTP setup required</div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-secondary" />
                </button>

                {/* ProtonMail */}
                <button
                  className="w-full p-4 rounded-xl border border-white/10 hover:border-accent hover:bg-white/5 transition-all text-left flex items-center gap-3"
                  onClick={() => {
                    alert('ProtonMail: Requires ProtonMail Bridge. Please contact support for setup.');
                  }}
                >
                  <img src="https://cdn.simpleicons.org/protonmail/6D4AFF" alt="ProtonMail" className="w-6 h-6" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-primary">ProtonMail</div>
                    <div className="text-xs text-secondary">Bridge application required</div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-secondary" />
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
