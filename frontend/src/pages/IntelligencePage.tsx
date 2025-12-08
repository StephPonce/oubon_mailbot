/**
 * Ospra Intelligence - Ospra Intelligence Page
 *
 * FULLY FUNCTIONAL:
 * - Real Claude AI chat
 * - Dashboard context awareness
 * - AI insights and briefings
 * - Actionable recommendations
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Brain,
  Send,
  Loader2,
  Sparkles,
  Package,
  TrendingUp,
  Mail,
  Target,
  BarChart3,
  RefreshCw,
  Trash2,
  Copy,
  CheckCircle2,
  AlertCircle,
  Zap,
  MessageSquare,
  Lightbulb,
  ArrowRight,
  X,
} from 'lucide-react';

import {
  useOiChat,
  useOiInsights,
  useDashboardMetrics,
  useSystemServices,
} from '../hooks/useData';
import { intelligenceAPI } from '../services/api';

// =============================================================================
// SUGGESTED PROMPTS
// =============================================================================

const SUGGESTED_PROMPTS = [
  {
    icon: Package,
    label: 'Find winning products',
    prompt: 'What are the best products to sell right now based on current trends?',
  },
  {
    icon: TrendingUp,
    label: 'Analyze trends',
    prompt: 'What niches are trending up and which ones should I avoid?',
  },
  {
    icon: Target,
    label: 'Optimize strategy',
    prompt: 'How can I improve my conversion rate and increase sales?',
  },
  {
    icon: Mail,
    label: 'Email performance',
    prompt: 'How is my email automation performing? Any issues I should address?',
  },
  {
    icon: BarChart3,
    label: 'Daily briefing',
    prompt: 'Give me a complete briefing on my store performance today.',
  },
  {
    icon: Lightbulb,
    label: 'Product ideas',
    prompt: 'Suggest 5 product ideas for the smart home niche with profit analysis.',
  },
];

// =============================================================================
// MESSAGE COMPONENT
// =============================================================================

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  onCopy: () => void;
}

function ChatMessage({ role, content, timestamp, onCopy }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy();
  };

  return (
    <div className={`flex gap-3 ${role === 'user' ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
        role === 'assistant' 
          ? 'bg-gradient-to-br from-blue-500 to-purple-600' 
          : 'bg-black/10'
      }`}>
        {role === 'assistant' ? (
          <Brain className="w-4 h-4 text-white" />
        ) : (
          <MessageSquare className="w-4 h-4 text-tertiary" />
        )}
      </div>

      {/* Content */}
      <div className={`flex-1 max-w-[80%] ${role === 'user' ? 'text-right' : ''}`}>
        <div className={`inline-block p-4 rounded-2xl ${
          role === 'assistant'
            ? 'bg-white/60 border border-black/5 text-left'
            : 'bg-accent text-white'
        }`}>
          <div className="text-sm whitespace-pre-wrap">{content}</div>
        </div>
        
        {/* Footer */}
        <div className={`flex items-center gap-2 mt-1 text-xs text-tertiary ${
          role === 'user' ? 'justify-end' : ''
        }`}>
          <span>{timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          {role === 'assistant' && (
            <button
              onClick={handleCopy}
              className="p-1 hover:bg-black/5 rounded"
            >
              {copied ? (
                <CheckCircle2 className="w-3 h-3 text-green-500" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// INSIGHT CARD
// =============================================================================

interface InsightCardProps {
  insight: {
    id: string;
    type: 'opportunity' | 'warning' | 'success' | 'trend';
    title: string;
    description: string;
    action?: string;
  };
  onAction?: () => void;
}

function InsightCard({ insight, onAction }: InsightCardProps) {
  const typeConfig = {
    opportunity: { icon: Sparkles, color: 'blue' },
    warning: { icon: AlertCircle, color: 'amber' },
    success: { icon: CheckCircle2, color: 'green' },
    trend: { icon: TrendingUp, color: 'purple' },
  };

  const config = typeConfig[insight.type] || typeConfig.opportunity;
  const Icon = config.icon;

  return (
    <div className={`p-4 rounded-xl bg-${config.color}-500/8 border border-${config.color}-500/15`}>
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg bg-white/50 text-${config.color}-600`}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-medium text-primary">{insight.title}</h4>
          <p className="text-xs text-secondary mt-1">{insight.description}</p>
          {insight.action && onAction && (
            <button
              onClick={onAction}
              className={`mt-2 text-xs font-medium text-${config.color}-600 hover:underline flex items-center gap-1`}
            >
              {insight.action}
              <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function IntelligencePage() {
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // State
  const [inputValue, setInputValue] = useState('');
  const [isGeneratingBriefing, setIsGeneratingBriefing] = useState(false);

  // Hooks
  const { messages, isLoading, streamingContent, sendMessage, clearMessages } = useOiChat();
  const { data: insightsData, isLoading: insightsLoading, isError: insightsError, error: insightsErrorObj, refetch: refetchInsights } = useOiInsights();
  const { data: metricsData } = useDashboardMetrics();
  const { data: servicesData } = useSystemServices();

  const insights = insightsData?.insights || [];

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Build context for AI
  const buildContext = () => ({
    metrics: metricsData,
    services: servicesData,
    timestamp: new Date().toISOString(),
  });

  // Handlers
  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;
    
    const message = inputValue.trim();
    setInputValue('');
    
    await sendMessage(message, buildContext());
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestedPrompt = (prompt: string) => {
    setInputValue(prompt);
    inputRef.current?.focus();
  };

  const handleGenerateBriefing = async () => {
    setIsGeneratingBriefing(true);
    try {
      await sendMessage('Give me a complete morning briefing on my business.', buildContext());
    } finally {
      setIsGeneratingBriefing(false);
    }
  };

  const handleInsightAction = (insight: { type: string }) => {
    switch (insight.type) {
      case 'opportunity':
        navigate('/products');
        break;
      case 'warning':
        navigate('/inventory');
        break;
      default:
        navigate('/');
    }
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-black/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Brain className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-primary">Ospra Intelligence</h1>
                <p className="text-xs text-secondary">Your AI-powered business assistant</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                className="btn-ghost text-sm"
                onClick={handleGenerateBriefing}
                disabled={isGeneratingBriefing}
              >
                {isGeneratingBriefing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Zap className="w-4 h-4" />
                )}
                <span>Morning Briefing</span>
              </button>
              <button
                className="btn-ghost text-sm"
                onClick={clearMessages}
                disabled={messages.length === 0}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {insightsError && messages.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <div className="glass-card p-12 text-center max-w-md">
                <X className="w-16 h-16 text-red-500 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-primary mb-2">Connection Error</h3>
                <p className="text-sm text-secondary mb-6">
                  {insightsErrorObj?.message || 'Unable to connect to Ospra Intelligence. Backend might be offline.'}
                </p>
                <button
                  className="btn-primary"
                  onClick={() => refetchInsights()}
                  disabled={insightsLoading}
                >
                  {insightsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  <span>Retry Connection</span>
                </button>
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mb-4">
                <Brain className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-xl font-semibold text-primary mb-2">
                How can I help you today?
              </h2>
              <p className="text-sm text-secondary mb-8 max-w-md">
                I can help you discover winning products, analyze trends, optimize your strategy, and manage your e-commerce business.
              </p>

              {/* Suggested Prompts */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-w-2xl">
                {SUGGESTED_PROMPTS.map((item, index) => (
                  <button
                    key={index}
                    className="flex items-center gap-2 p-3 rounded-xl bg-white/50 border border-black/5 hover:border-accent hover:bg-white/80 transition-all text-left"
                    onClick={() => handleSuggestedPrompt(item.prompt)}
                  >
                    <item.icon className="w-4 h-4 text-accent flex-shrink-0" />
                    <span className="text-sm text-primary">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  role={message.role}
                  content={message.content}
                  timestamp={message.timestamp}
                  onCopy={() => {}}
                />
              ))}

              {/* Streaming indicator */}
              {streamingContent && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                    <Brain className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex-1 max-w-[80%]">
                    <div className="inline-block p-4 rounded-2xl bg-white/60 border border-black/5">
                      <div className="text-sm whitespace-pre-wrap">{streamingContent}</div>
                      <Loader2 className="w-4 h-4 animate-spin mt-2 text-accent" />
                    </div>
                  </div>
                </div>
              )}

              {/* Loading indicator */}
              {isLoading && !streamingContent && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                    <Brain className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex items-center gap-2 p-4 rounded-2xl bg-white/60 border border-black/5">
                    <Loader2 className="w-4 h-4 animate-spin text-accent" />
                    <span className="text-sm text-secondary">Thinking...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-black/5">
          <div className="flex items-end gap-3">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask Ospra anything about your business..."
                className="w-full px-4 py-3 pr-12 rounded-xl bg-white/50 border border-black/10 focus:border-accent focus:ring-2 focus:ring-accent/20 outline-none text-sm resize-none"
                rows={1}
                style={{ minHeight: '48px', maxHeight: '120px' }}
              />
            </div>
            <button
              className="btn-primary h-12 px-4"
              onClick={handleSend}
              disabled={!inputValue.trim() || isLoading}
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-xs text-tertiary mt-2 text-center">
            Ospra has full context of your dashboard. Press Enter to send, Shift+Enter for new line.
          </p>
        </div>
      </div>

      {/* Sidebar - Insights */}
      <div className="w-80 border-l border-black/5 p-4 overflow-y-auto hidden lg:block">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-600" />
            <h2 className="text-sm font-medium text-primary">AI Insights</h2>
          </div>
          <button
            className="p-1.5 hover:bg-black/5 rounded-lg"
            onClick={() => refetchInsights()}
          >
            <RefreshCw className={`w-4 h-4 text-tertiary ${insightsLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {insights.length === 0 ? (
          <div className="text-sm text-tertiary text-center py-8">
            No insights yet. Start chatting with Ospra to get personalized recommendations.
          </div>
        ) : (
          <div className="space-y-3">
            {insights.map((insight) => (
              <InsightCard
                key={insight.id}
                insight={insight}
                onAction={() => handleInsightAction(insight)}
              />
            ))}
          </div>
        )}

        {/* Quick Stats */}
        {metricsData && (
          <div className="mt-6 p-4 rounded-xl bg-black/5">
            <h3 className="text-xs font-medium text-secondary mb-3">Quick Stats</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-tertiary">Revenue</span>
                <span className="font-medium text-primary">
                  ${(metricsData.total_revenue || 0).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-tertiary">Products</span>
                <span className="font-medium text-primary">
                  {metricsData.active_products || 0}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-tertiary">Conversion</span>
                <span className="font-medium text-primary">
                  {(metricsData.conversion_rate || 0).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
