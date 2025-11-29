import { useState, useEffect, useMemo, useCallback } from 'react';
import { Mail, Inbox, Star, Send, FileText, Trash2, Edit, Settings, X, Archive, Reply, Forward, StarOff, MailOpen, RefreshCw } from 'lucide-react';
import axios from 'axios';
import { GlassPanel } from '@/components/GlassPanel';

interface EmailStats {
  total_emails: number;
  unread_emails: number;
  starred_emails: number;
  important_emails: number;
  accounts: Array<{
    account_id: number;
    email_address: string;
    provider: string;
    total_emails: number;
    unread_emails: number;
    last_synced: string | null;
  }>;
}

interface Email {
  id: number;
  email_account_id?: number;
  from_address: string;
  from_name?: string;
  to_addresses?: string;
  subject?: string;
  snippet?: string;
  body_plain?: string;
  body_html?: string;
  received_at: string;
  is_read: boolean;
  is_starred: boolean;
  is_important: boolean;
  has_attachments: boolean;
  labels?: string[];
}

export default function EmailDashboard() {
  const [stats, setStats] = useState<EmailStats | null>(null);
  const [allEmails, setAllEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [selectedAccount] = useState<number | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<string>('Inbox');
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);
  const [showCompose, setShowCompose] = useState(false);
  const [composeTo, setComposeTo] = useState('');
  const [composeSubject, setComposeSubject] = useState('');
  const [composeBody, setComposeBody] = useState('');
  const [sending, setSending] = useState(false);

  // Filter emails based on selected folder
  const recentEmails = useMemo(() => {
    // Since we now filter at the API level, we can just return allEmails
    // The API already filtered by label based on selectedFolder
    // Only apply additional client-side filters that API doesn't handle
    if (selectedFolder === 'Starred') {
      return allEmails.filter(e => e.is_starred);
    }
    return allEmails;
  }, [allEmails, selectedFolder]);

  // Calculate folder counts dynamically
  // Only show count for unread inbox emails
  const folderCounts = useMemo(() => ({
    inbox: allEmails.filter(e => e.labels?.includes('INBOX') && !e.is_read).length,
    starred: 0,  // No badge
    sent: 0,     // No badge
    drafts: 0,   // No badge
    trash: 0,    // No badge
  }), [allEmails]);

  // Folder structure
  const folders = [
    { name: 'Inbox', icon: Inbox, count: folderCounts.inbox },
    { name: 'Starred', icon: Star, count: folderCounts.starred },
    { name: 'Sent', icon: Send, count: folderCounts.sent },
    { name: 'Drafts', icon: FileText, count: folderCounts.drafts },
    { name: 'Trash', icon: Trash2, count: folderCounts.trash },
  ];

  const fetchEmailData = useCallback(async () => {
    setLoading(true);
    try {
      const userId = 1;
      const statsRes = await axios.get(`http://localhost:8001/api/emails/stats/summary?user_id=${userId}`);
      const accountParam = selectedAccount ? `&account_id=${selectedAccount}` : '';

      // Use label filtering at API level to get the right emails for each folder
      let labelParam = '';
      if (selectedFolder === 'Inbox') {
        labelParam = '&label=INBOX';
      } else if (selectedFolder === 'Sent') {
        labelParam = '&label=SENT';
      } else if (selectedFolder === 'Trash') {
        labelParam = '&label=TRASH';
      } else if (selectedFolder === 'Drafts') {
        labelParam = '&label=DRAFT';
      }

      const emailsRes = await axios.get(`http://localhost:8001/api/emails/list?user_id=${userId}&limit=200${accountParam}${labelParam}`);

      setStats(statsRes.data);
      setAllEmails(emailsRes.data || []);
    } catch (err) {
      console.error('Error fetching email data:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedAccount, selectedFolder, setLoading, setStats, setAllEmails]);

  useEffect(() => {
    fetchEmailData();
  }, [fetchEmailData]);

  const syncEmails = async () => {
    if (syncing) return;
    setSyncing(true);
    try {
      const userId = 1;
      // Trigger sync for all accounts (last 30 days, up to 100 emails - fast sync)
      if (stats?.accounts && stats.accounts.length > 0) {
        await Promise.all(
          stats.accounts.map(account =>
            axios.post(`http://localhost:8001/api/emails/sync?user_id=${userId}&account_id=${account.account_id}&max_emails=100&days_back=30`)
          )
        );
      }
      // Refresh email list after sync
      await fetchEmailData();
    } catch (err) {
      console.error('Error syncing emails:', err);
    } finally {
      setSyncing(false);
    }
  };

  const openEmail = async (email: Email) => {
    try {
      const userId = 1;
      const res = await axios.get(`http://localhost:8001/api/emails/${email.id}?user_id=${userId}`);
      setSelectedEmail(res.data);
      if (!res.data.is_read) {
        await axios.post(`http://localhost:8001/api/emails/${email.id}/mark-read?user_id=${userId}&is_read=true`);
        // Optimistically update the UI
        setAllEmails(prev => prev.map(e => e.id === email.id ? { ...e, is_read: true } : e));
      }
    } catch (err) {
      console.error('Error fetching email details:', err);
    }
  };

  const sendComposeEmail = async () => {
    if (!composeTo || !composeBody) return;
    setSending(true);
    try {
        const userId = 1;
        await axios.post(`http://localhost:8001/api/emails/send?user_id=${userId}`, {
            to: composeTo,
            subject: composeSubject,
            message: composeBody,
        });
        alert('Email sent successfully!');
        setShowCompose(false);
        // Reset form
        setComposeTo('');
        setComposeSubject('');
        setComposeBody('');
    } catch (err) {
        console.error('Error sending email:', err);
        alert('Failed to send email.');
    } finally {
        setSending(false);
    }
  };

  const toggleStar = async (email: Email) => {
    try {
      const userId = 1;
      const newStarredState = !email.is_starred;
      await axios.post(`http://localhost:8001/api/emails/${email.id}/star?user_id=${userId}&is_starred=${newStarredState}`);

      // Update local state
      setAllEmails(prev => prev.map(e => e.id === email.id ? { ...e, is_starred: newStarredState } : e));
      if (selectedEmail?.id === email.id) {
        setSelectedEmail({ ...selectedEmail, is_starred: newStarredState });
      }
    } catch (err) {
      console.error('Error toggling star:', err);
    }
  };

  const toggleRead = async (email: Email) => {
    try {
      const userId = 1;
      const newReadState = !email.is_read;
      await axios.post(`http://localhost:8001/api/emails/${email.id}/mark-read?user_id=${userId}&is_read=${newReadState}`);

      // Update local state
      setAllEmails(prev => prev.map(e => e.id === email.id ? { ...e, is_read: newReadState } : e));
      if (selectedEmail?.id === email.id) {
        setSelectedEmail({ ...selectedEmail, is_read: newReadState });
      }
    } catch (err) {
      console.error('Error toggling read status:', err);
    }
  };

  const archiveEmail = async (email: Email) => {
    try {
      const userId = 1;
      await axios.post(`http://localhost:8001/api/emails/${email.id}/archive?user_id=${userId}`);

      // Remove from list
      setAllEmails(prev => prev.filter(e => e.id !== email.id));
      if (selectedEmail?.id === email.id) {
        setSelectedEmail(null);
      }
      alert('Email archived successfully!');
    } catch (err) {
      console.error('Error archiving email:', err);
      alert('Failed to archive email. API endpoint may not be implemented yet.');
    }
  };

  const deleteEmail = async (email: Email) => {
    if (!confirm('Are you sure you want to delete this email?')) return;

    try {
      const userId = 1;
      await axios.delete(`http://localhost:8001/api/emails/${email.id}?user_id=${userId}`);

      // Remove from list
      setAllEmails(prev => prev.filter(e => e.id !== email.id));
      if (selectedEmail?.id === email.id) {
        setSelectedEmail(null);
      }
      alert('Email deleted successfully!');
    } catch (err) {
      console.error('Error deleting email:', err);
      alert('Failed to delete email.');
    }
  };

  const replyToEmail = (email: Email) => {
    setComposeTo(email.from_address);
    setComposeSubject(`Re: ${email.subject || ''}`);
    setComposeBody(`\n\n--- Original Message ---\nFrom: ${email.from_name || email.from_address}\nDate: ${new Date(email.received_at).toLocaleString()}\nSubject: ${email.subject}\n\n${email.body_plain || ''}`);
    setShowCompose(true);
  };

  const forwardEmail = (email: Email) => {
    setComposeTo('');
    setComposeSubject(`Fwd: ${email.subject || ''}`);
    setComposeBody(`\n\n--- Forwarded Message ---\nFrom: ${email.from_name || email.from_address}\nDate: ${new Date(email.received_at).toLocaleString()}\nSubject: ${email.subject}\n\n${email.body_plain || ''}`);
    setShowCompose(true);
  };

  // Sanitize and format email content
  const formatEmailContent = (email: Email) => {
    // Use plain text if available, otherwise strip HTML tags from body_html
    if (email.body_plain) {
      return email.body_plain.split('\n').map((line, idx) => (
        <p key={idx} className="mb-2">{line || '\u00A0'}</p>
      ));
    } else if (email.body_html) {
      // Simple HTML sanitization - remove scripts and styles
      const cleanHtml = email.body_html
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
        .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '');
      return <div dangerouslySetInnerHTML={{ __html: cleanHtml }} className="prose max-w-none" />;
    }
    return <p className="text-gray-500">No content available</p>;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-12 flex items-center justify-center" style={{ perspective: '1500px' }}>
        <GlassPanel depth={60} delay={0}>
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto mb-4"></div>
            <p className="text-gray-600 font-light">Loading Emails...</p>
          </div>
        </GlassPanel>
      </div>
    );
  }

  return (
    <>
      <div className="min-h-screen bg-gray-50 p-8" style={{ perspective: '1500px' }}>
      <div className="max-w-[1800px] mx-auto">
        <div className="flex gap-6 h-[calc(100vh-8rem)]">
          {/* Column 1: Navigation */}
          <div className="w-64 flex-shrink-0">
            <GlassPanel depth={80} delay={0.1} className="h-full flex flex-col gap-4 p-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-light text-gray-900">Mailbox</h2>
                <button
                  onClick={syncEmails}
                  disabled={syncing || !stats?.accounts || stats.accounts.length === 0}
                  className="p-1.5 rounded-lg hover:bg-gray-900/10 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Sync emails"
                >
                  <RefreshCw size={16} className={`text-gray-600 ${syncing ? 'animate-spin' : ''}`} />
                </button>
              </div>
              <div className="space-y-1">
                {folders.map(folder => (
                  <button
                    key={folder.name}
                    onClick={() => setSelectedFolder(folder.name)}
                    className={`w-full flex justify-between items-center px-3 py-2 rounded-lg font-light text-sm transition ${
                      selectedFolder === folder.name
                        ? 'bg-gray-900 text-white shadow-lg'
                        : 'text-gray-700 hover:bg-gray-200/50'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <folder.icon size={16} />
                      <span>{folder.name}</span>
                    </div>
                    {folder.count > 0 && <span className="text-xs bg-gray-900 text-white rounded-full px-2 py-0.5">{folder.count}</span>}
                  </button>
                ))}
              </div>
              <div className="mt-auto space-y-2">
                <button onClick={() => setShowCompose(true)} className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-gray-900 text-white rounded-lg text-sm font-light hover:bg-gray-800 transition">
                  <Edit size={14}/> Compose
                </button>
                <a href="/settings" className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-white/50 border border-gray-200 text-gray-700 rounded-lg text-sm font-light hover:bg-white transition">
                  <Settings size={14}/> Settings
                </a>
              </div>
            </GlassPanel>
          </div>

          {/* Column 2: Email List */}
          <div className="w-96 flex-shrink-0">
            <GlassPanel depth={70} delay={0.2} className="h-full flex flex-col p-0 overflow-hidden">
              <div className="p-4 border-b border-gray-200">
                <input type="search" placeholder="Search emails..." className="w-full bg-white/50 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900" />
              </div>
              <div className="flex-1 overflow-y-auto">
                {recentEmails.map(email => (
                  <div
                    key={email.id}
                    onClick={() => openEmail(email)}
                    className={`p-4 border-b border-gray-200 cursor-pointer transition ${selectedEmail?.id === email.id ? 'bg-gray-900/10' : 'hover:bg-gray-900/5'} ${!email.is_read ? 'bg-gray-100/50' : ''}`}
                  >
                    <div className="flex justify-between items-start mb-1">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        {email.is_starred && <Star size={12} fill="currentColor" className="text-yellow-500 flex-shrink-0" />}
                        <p className={`text-sm truncate ${!email.is_read ? 'font-semibold text-gray-900' : 'font-light text-gray-700'}`}>{email.from_name || email.from_address}</p>
                      </div>
                      <p className="text-xs text-gray-500 flex-shrink-0 ml-2">{new Date(email.received_at).toLocaleDateString()}</p>
                    </div>
                    <p className={`text-sm truncate ${!email.is_read ? 'font-medium text-gray-900' : 'font-light text-gray-700'}`}>{email.subject}</p>
                    <p className="text-xs text-gray-500 mt-1 truncate">{email.snippet}</p>
                  </div>
                ))}
              </div>
            </GlassPanel>
          </div>

          {/* Column 3: Email Content */}
          <div className="hidden xl:flex flex-1">
            <GlassPanel depth={60} delay={0.3} className="w-full flex flex-col p-0 overflow-hidden">
              {selectedEmail ? (
                <>
                  {/* Email Header */}
                  <div className="px-8 py-6 border-b border-gray-200 bg-gradient-to-b from-white/30 to-transparent">
                    <div>
                      <div className="mb-4">
                        <h1 className="text-2xl font-light text-gray-900 mb-3">{selectedEmail.subject || '(No Subject)'}</h1>
                        <div className="flex items-center gap-3 text-sm">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-full bg-gray-900/10 flex items-center justify-center text-gray-900 font-medium">
                              {(selectedEmail.from_name || selectedEmail.from_address).charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <p className="font-medium text-gray-900">{selectedEmail.from_name || 'Unknown Sender'}</p>
                              <p className="text-xs text-gray-500">&lt;{selectedEmail.from_address}&gt;</p>
                            </div>
                          </div>
                          <span className="text-gray-400 mx-2">•</span>
                          <p className="text-gray-600">
                            {new Date(selectedEmail.received_at).toLocaleString()}
                          </p>
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center justify-between gap-2 pt-3 border-t border-gray-200">
                        <div className="flex items-center gap-2 flex-wrap">
                          <button
                            onClick={() => replyToEmail(selectedEmail)}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition text-sm font-light"
                          >
                            <Reply size={14} />
                            Reply
                          </button>
                          <button
                            onClick={() => forwardEmail(selectedEmail)}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/50 border border-gray-200 text-gray-700 rounded-lg hover:bg-white transition text-sm font-light"
                          >
                            <Forward size={14} />
                            Forward
                          </button>
                          <button
                            onClick={() => toggleStar(selectedEmail)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition text-sm font-light ${
                              selectedEmail.is_starred
                                ? 'bg-yellow-500/20 text-yellow-600 hover:bg-yellow-500/30'
                                : 'bg-white/50 border border-gray-200 text-gray-700 hover:bg-white'
                            }`}
                          >
                            {selectedEmail.is_starred ? <Star size={14} fill="currentColor" /> : <StarOff size={14} />}
                            {selectedEmail.is_starred ? 'Starred' : 'Star'}
                          </button>
                          <button
                            onClick={() => toggleRead(selectedEmail)}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/50 border border-gray-200 text-gray-700 rounded-lg hover:bg-white transition text-sm font-light"
                          >
                            <MailOpen size={14} />
                            Mark {selectedEmail.is_read ? 'Unread' : 'Read'}
                          </button>
                          <button
                            onClick={() => archiveEmail(selectedEmail)}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/50 border border-gray-200 text-gray-700 rounded-lg hover:bg-white transition text-sm font-light"
                          >
                            <Archive size={14} />
                            Archive
                          </button>
                        </div>
                        <button
                          onClick={() => deleteEmail(selectedEmail)}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/20 text-red-600 rounded-lg hover:bg-red-500/30 transition text-sm font-light"
                        >
                          <Trash2 size={14} />
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Email Body */}
                  <div className="flex-1 overflow-y-auto overflow-x-auto">
                    <div className="px-8 py-6">
                      <div className="text-gray-900 leading-relaxed text-base break-words">
                        {formatEmailContent(selectedEmail)}
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-gray-500">
                  <Mail size={64} className="mb-4 opacity-30" />
                  <p className="text-xl font-light text-gray-600">Select an email to read</p>
                  <p className="text-sm mt-2 text-gray-500">Choose an email from the list to view its contents</p>
                </div>
              )}
            </GlassPanel>
          </div>
        </div>
      </div>
      </div>

      {/* Compose Modal */}
      {showCompose && (
        <div className="fixed inset-0 bg-gray-900/40 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setShowCompose(false)}>
          <div className="glass p-8 max-w-2xl w-full" style={{ boxShadow: '0 40px 120px rgba(0, 0, 0, 0.25)' }} onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-light text-gray-900">New Message</h2>
              <button onClick={() => setShowCompose(false)} className="p-1.5 rounded-full hover:bg-gray-900/10 text-gray-500 hover:text-gray-900 transition">
                <X size={20}/>
              </button>
            </div>
            <div className="space-y-4">
              <input type="email" value={composeTo} onChange={e => setComposeTo(e.target.value)} placeholder="To" className="w-full bg-white/50 border border-gray-200 rounded-lg px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900" />
              <input type="text" value={composeSubject} onChange={e => setComposeSubject(e.target.value)} placeholder="Subject" className="w-full bg-white/50 border border-gray-200 rounded-lg px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900" />
              <textarea value={composeBody} onChange={e => setComposeBody(e.target.value)} placeholder="Message..." rows={10} className="w-full bg-white/50 border border-gray-200 rounded-lg px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900 resize-none"></textarea>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowCompose(false)} className="px-5 py-2 text-gray-700 font-light rounded-lg hover:bg-gray-900/5 transition">
                Cancel
              </button>
              <button onClick={sendComposeEmail} disabled={sending} className="px-5 py-2 bg-gray-900 text-white font-light rounded-lg hover:bg-gray-800 disabled:bg-gray-400 transition">
                {sending ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
