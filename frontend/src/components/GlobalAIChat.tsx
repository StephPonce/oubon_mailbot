import React, { useRef, useEffect } from 'react';
import { Send, Sparkles, X, Minimize2, Maximize2 } from 'lucide-react';
import { useAIChat } from '../contexts/AIChatContext';

export default function GlobalAIChat() {
  const {
    messages,
    isOpen,
    isMinimized,
    loading,
    setIsOpen,
    setIsMinimized,
    clearMessages,
    sendMessage
  } = useAIChat();

  const [input, setInput] = React.useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const text = input;
    setInput('');
    await sendMessage(text);
  };

  const quickPrompts = [
    "What's on this page?",
    "Analyze current data",
    "Suggest improvements",
    "What should I focus on?",
  ];

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-full px-6 py-4 shadow-2xl transition-all z-50 flex items-center gap-3 group"
      >
        <Sparkles className="w-6 h-6 group-hover:scale-110 transition-transform" />
        <span className="font-semibold">Ask Claude AI</span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <div className={`bg-gray-900 rounded-2xl shadow-2xl border border-gray-800 ${isMinimized ? 'w-80' : 'w-[28rem] h-[600px]'} flex flex-col overflow-hidden`}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-blue-600 to-purple-600 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-white" />
            <h3 className="font-semibold text-white">Claude AI Assistant</h3>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => clearMessages()}
              className="text-white/70 hover:text-white text-xs px-2 py-1 hover:bg-white/10 rounded transition-colors"
              title="Clear conversation"
            >
              Clear
            </button>
            <button
              onClick={() => setIsMinimized(!isMinimized)}
              className="text-white/70 hover:text-white p-1 hover:bg-white/10 rounded transition-colors"
            >
              {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="text-white/70 hover:text-white p-1 hover:bg-white/10 rounded transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {!isMinimized && (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-950">
              {messages.length === 0 && (
                <div className="text-center py-8">
                  <Sparkles className="w-12 h-12 text-blue-500 mx-auto mb-4 animate-pulse" />
                  <p className="text-gray-400 mb-4">Hi! I can see everything on this page.</p>
                  <p className="text-gray-500 text-sm mb-4">Try asking about:</p>
                  <div className="space-y-2">
                    {quickPrompts.map((prompt, idx) => (
                      <button
                        key={idx}
                        onClick={() => sendMessage(prompt)}
                        className="w-full text-left px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 transition-colors"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-xl px-4 py-3 ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800 text-gray-100 border border-gray-700'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    <p className="text-xs opacity-60 mt-2">
                      {msg.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-gray-800 bg-gray-900">
              <form onSubmit={handleSend} className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about this page..."
                  className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-xl text-white transition-colors"
                >
                  <Send className="w-5 h-5" />
                </button>
              </form>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
