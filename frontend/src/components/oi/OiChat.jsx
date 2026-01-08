/**
 * OSPRA INTELLIGENCE - OI CHAT COMPONENT
 * =======================================
 * 
 * The AI brain of Ospra - conversational interface to Oi.
 * 
 * @author OspraOS
 * @date December 2024
 */

import React, { useState, useRef, useEffect } from 'react';
import { useAuthenticatedFetch } from '../../hooks/useAuth';

function MessageBubble({ message, isUser }) {
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center mr-3 flex-shrink-0">
          <span className="text-sm"></span>
        </div>
      )}
      
      <div className={`max-w-[80%] px-4 py-3 rounded-2xl ${
        isUser
          ? 'bg-gradient-to-r from-purple-600 to-cyan-600 text-white'
          : 'bg-white/10 border border-white/10 text-white/90'
      }`}>
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        <p className="text-xs text-white/40 mt-2">
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
      
      {isUser && (
        <div className="w-8 h-8 rounded-xl bg-white/10 border border-white/10 flex items-center justify-center ml-3 flex-shrink-0">
          <span className="text-sm"></span>
        </div>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-4">
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center mr-3">
        <span className="text-sm"></span>
      </div>
      <div className="bg-white/10 border border-white/10 px-4 py-3 rounded-2xl">
        <div className="flex space-x-1">
          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    </div>
  );
}

function QuickActions({ onAction }) {
  const actions = [
    { label: '[STATS] Store Status', command: "What's my store status?" },
    { label: '[HOT] Trending', command: "What's trending right now?" },
    { label: '[PACKAGE] Top Products', command: 'Show me the top 5 products' },
    { label: '[PRICE] Revenue', command: "How's my revenue this week?" },
  ];

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {actions.map((action, i) => (
        <button
          key={i}
          onClick={() => onAction(action.command)}
          className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-white/70 text-xs hover:bg-white/10 hover:text-white transition-all"
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}

export function OiChat({ className = '', minimized = false }) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      content: "Hey! I'm Oi, your e-commerce intelligence assistant. I can help you find trending products, manage your store, and automate your business. What would you like to do?",
      isUser: false,
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isExpanded, setIsExpanded] = useState(!minimized);
  
  const messagesEndRef = useRef(null);
  const { post, loading } = useAuthenticatedFetch();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const sendMessage = async (content) => {
    if (!content.trim()) return;

    const userMessage = {
      id: Date.now(),
      content: content.trim(),
      isUser: true,
      timestamp: new Date().toISOString(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await post('/api/oi/chat', {
        message: content,
        context: {
          recent_messages: messages.slice(-5).map(m => ({
            role: m.isUser ? 'user' : 'assistant',
            content: m.content,
          })),
        },
      });

      const oiMessage = {
        id: Date.now() + 1,
        content: response.response || response.message || "I'm processing that request...",
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      
      setMessages(prev => [...prev, oiMessage]);
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        content: `Sorry, I encountered an error: ${error.message}. Please try again.`,
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className={`fixed bottom-6 right-6 w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-600 to-cyan-600 shadow-lg shadow-purple-500/25 flex items-center justify-center hover:scale-110 transition-transform z-50 ${className}`}
      >
        <span className="text-2xl"></span>
      </button>
    );
  }

  return (
    <div className={`flex flex-col bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-purple-600/20 to-cyan-600/20 border-b border-white/10">
        <div className="flex items-center">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center mr-3">
            <span className="text-sm"></span>
          </div>
          <div>
            <h3 className="text-white font-semibold text-sm">Oi Assistant</h3>
            <p className="text-white/50 text-xs">Ospra Intelligence</p>
          </div>
        </div>
        
        {minimized && (
          <button onClick={() => setIsExpanded(false)} className="w-8 h-8 rounded-lg hover:bg-white/10 flex items-center justify-center text-white/60 hover:text-white transition-colors">
            
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 min-h-[300px] max-h-[500px]">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} isUser={message.isUser} />
        ))}
        {isTyping && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Actions */}
      <div className="px-4">
        <QuickActions onAction={sendMessage} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-white/10">
        <div className="flex items-center space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Oi anything..."
            disabled={loading || isTyping}
            className="flex-1 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:border-purple-500/50 transition-all text-sm"
          />
          <button
            type="submit"
            disabled={loading || isTyping || !input.trim()}
            className="px-4 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white hover:from-purple-500 hover:to-cyan-500 disabled:opacity-50 transition-all"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
}

export default OiChat;
