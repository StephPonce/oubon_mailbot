import React, { useRef, useEffect } from 'react';
import { Send, Sparkles, X, Minimize2, Maximize2, Bot } from 'lucide-react';
import { useAIChat } from '../contexts/AIChatContext';

export default function GlobalAIChat() {
  const { messages, isOpen, isMinimized, loading, setIsOpen, setIsMinimized, clearMessages, sendMessage } = useAIChat();
  const [input, setInput] = React.useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const message = input.trim();
    setInput('');
    await sendMessage(message);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-12 h-12 rounded-full bg-white/10 backdrop-blur-md border border-white/20 shadow-lg flex items-center justify-center text-white transition-all z-50 group hover:bg-white/20"
      >
        <Sparkles className="w-6 h-6 transform group-hover:scale-110 transition-transform" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <div className={`bg-gray-950/80 backdrop-blur-2xl border border-gray-800 rounded-2xl shadow-2xl shadow-black/50 ${isMinimized ? 'w-80' : 'w-[32rem] h-[40rem]'} flex flex-col overflow-hidden transition-all duration-300`}>
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <Bot className="w-6 h-6 text-brand-blue" />
            <h3 className="font-semibold text-gray-200">AI Assistant</h3>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => clearMessages()} className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-md transition-colors" title="Clear">
              <X size={16} />
            </button>
            <button onClick={() => setIsMinimized(!isMinimized)} className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-md transition-colors">
              {isMinimized ? <Maximize2 size={16} /> : <Minimize2 size={16} />}
            </button>
            <button onClick={() => setIsOpen(false)} className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-md transition-colors">
              <X size={16} />
            </button>
          </div>
        </div>

        {!isMinimized && (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 mt-8">
                  <Sparkles className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>Ask me anything about this page!</p>
                </div>
              ) : (
                messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] p-3 rounded-lg ${
                        msg.role === 'user'
                          ? 'bg-brand-blue text-white'
                          : 'bg-gray-800 text-gray-200'
                      }`}
                    >
                      {msg.content}
                    </div>
                  </div>
                ))
              )}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-800 text-gray-400 p-3 rounded-lg">
                    Thinking...
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            <div className="p-4 border-t border-gray-800">
              <form onSubmit={handleSend} className="relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about this page..."
                  className="w-full bg-gray-800/70 border border-gray-700 rounded-lg pl-4 pr-12 py-3 text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-blue"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-full bg-brand-blue text-white hover:opacity-90 disabled:bg-gray-600 transition"
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
