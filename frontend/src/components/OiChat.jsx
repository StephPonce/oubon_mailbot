/**
 * OSPRA INTELLIGENCE - OI CHAT
 * Simplified and robust chat interface
 */

import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, Sparkles, Loader2
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { api } from '../services/api';
import { Sidebar } from './Layout';

function ChatMessage({ message, isUser }) {
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[80%] ${isUser ? 'order-2' : 'order-1'}`}>
        {!isUser && (
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
              <Sparkles className="w-3 h-3 text-white" />
            </div>
            <span className="text-white/60 text-sm">Oi</span>
          </div>
        )}
        <div className={`rounded-2xl px-4 py-3 ${
          isUser 
            ? 'bg-gradient-to-r from-purple-600 to-cyan-600 text-white' 
            : 'bg-white/10 text-white border border-white/10'
        }`}>
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>
        <div className={`text-xs text-white/40 mt-1 ${isUser ? 'text-right' : 'text-left'}`}>
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

function SuggestionChip({ text, onClick }) {
  return (
    <button
      onClick={() => onClick(text)}
      className="px-4 py-2 rounded-full bg-white/5 border border-white/10 text-white/80 text-sm hover:bg-purple-500/20 hover:border-purple-500/30 transition-all"
    >
      {text}
    </button>
  );
}

export function OiChat() {
  const { user } = useAuth();
  const [messages, setMessages] = useState([
    {
      id: 1,
      content: "Hey! I'm Oi, your AI e-commerce assistant. I can help you discover products, analyze trends, manage your store, and more. What would you like to do?",
      isUser: false,
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      id: Date.now(),
      content: input,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    const userInput = input;
    setInput('');
    setLoading(true);

    try {
      // Call the Oi chat API
      const response = await api.chat(userInput, { 
        user_tier: user?.tier 
      });
      
      // console.log('Oi response:', response);
      
      // Extract message from various response formats
      let aiContent = response.message 
        || response.response 
        || response.content 
        || response.text
        || response.answer
        || (typeof response === 'string' ? response : null);
      
      // If still no content, try to stringify
      if (!aiContent && response) {
        aiContent = JSON.stringify(response);
      }
      
      // Fallback message
      if (!aiContent) {
        aiContent = "I received your message but couldn't generate a response. Please try again.";
      }

      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        content: aiContent,
        isUser: false,
        timestamp: new Date(),
      }]);

    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        content: `Connection error: ${error.message}. Make sure the backend is running on localhost:8000.`,
        isUser: false,
        timestamp: new Date(),
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleSuggestion = (text) => {
    setInput(text);
    inputRef.current?.focus();
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const defaultSuggestions = [
    'Find trending products',
    'Show my pending actions',
    'What products should I sell?',
    'Analyze market trends',
    'Help me with pricing',
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
      {/* Static background orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10" />
      </div>

      <Sidebar />

      <main className="ml-64 flex flex-col h-screen">
        {/* Header */}
        <div className="backdrop-blur-xl bg-black/20 border-b border-white/10 px-6 py-4">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-white font-semibold">Chat with Oi</h2>
              <p className="text-white/40 text-sm">Your AI e-commerce assistant</p>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-green-400 text-sm">Online</span>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6">
          {messages.map(message => (
            <ChatMessage key={message.id} message={message} isUser={message.isUser} />
          ))}
          
          {loading && (
            <div className="flex items-center gap-2 text-white/60">
              <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
                <Loader2 className="w-3 h-3 text-white animate-spin" />
              </div>
              <span className="text-sm">Oi is thinking...</span>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestions - show only at start */}
        {messages.length === 1 && (
          <div className="px-6 py-4 border-t border-white/10">
            <p className="text-white/40 text-sm mb-3">Try these:</p>
            <div className="flex flex-wrap gap-2">
              {defaultSuggestions.map((suggestion, i) => (
                <SuggestionChip 
                  key={i} 
                  text={suggestion} 
                  onClick={handleSuggestion} 
                />
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="backdrop-blur-xl bg-black/20 border-t border-white/10 px-6 py-4">
          <div className="flex items-center gap-4">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask Oi anything..."
              disabled={loading}
              className="flex-1 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-white font-semibold hover:from-purple-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default OiChat;
