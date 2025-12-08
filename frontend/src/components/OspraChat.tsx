/**
 * Ospra Intelligence - AI Chat
 *
 * Real backend-connected AI chat using:
 * - useOspra hook for API integration
 * - useOspraChat for state management
 * - Liquid glass design from GlobalAIChat.tsx
 * - Proactive greeting with morning briefing
 */

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  X,
  Send,
  Minimize2,
  Maximize2,
  Loader2,
  Sparkles,
  ExternalLink,
} from 'lucide-react';
import { useOspraChat } from '../store/ospra.store';
import { useOspra, OSPRA_SUGGESTED_PROMPTS } from '../hooks/useOspra';
import { useOspraStore } from '../store/ospra.store';

// ============================================
// ANIMATION VARIANTS
// ============================================

const chatVariants = {
  hidden: {
    opacity: 0,
    scale: 0.95,
    y: 20,
  },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      type: 'spring',
      damping: 25,
      stiffness: 300,
    },
  },
  exit: {
    opacity: 0,
    scale: 0.95,
    y: 20,
    transition: {
      duration: 0.2,
    },
  },
};

const buttonVariants = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: {
      type: 'spring',
      damping: 20,
      stiffness: 300,
    },
  },
  exit: {
    opacity: 0,
    scale: 0.8,
    transition: { duration: 0.15 },
  },
};

// ============================================
// MAIN COMPONENT
// ============================================

export default function OspraChat() {
  const {
    isChatOpen,
    isChatMinimized,
    messages,
    isTyping,
    streamingContent,
    openChat,
    closeChat,
    minimizeChat,
    maximizeChat,
  } = useOspraChat();

  const {
    sendMessage,
    sendProactiveGreeting,
    checkBackendStatus,
  } = useOspra();

  const { backendStatus } = useOspraStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasGreetedRef = useRef(false);
  const [inputValue, setInputValue] = useState('');

  // ============================================
  // AUTO-SCROLL TO BOTTOM
  // ============================================

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  // ============================================
  // PROACTIVE GREETING
  // ============================================

  useEffect(() => {
    if (isChatOpen && messages.length === 0 && !hasGreetedRef.current) {
      hasGreetedRef.current = true;
      // Small delay for better UX
      setTimeout(() => {
        sendProactiveGreeting();
      }, 800);
    }
  }, [isChatOpen, messages.length, sendProactiveGreeting]);

  // ============================================
  // CHECK BACKEND STATUS ON MOUNT
  // ============================================

  useEffect(() => {
    checkBackendStatus();
    // Check every 30 seconds
    const interval = setInterval(checkBackendStatus, 30000);
    return () => clearInterval(interval);
  }, [checkBackendStatus]);

  // ============================================
  // FOCUS INPUT WHEN CHAT OPENS
  // ============================================

  useEffect(() => {
    if (isChatOpen && !isChatMinimized) {
      inputRef.current?.focus();
    }
  }, [isChatOpen, isChatMinimized]);

  // ============================================
  // MESSAGE HANDLERS
  // ============================================

  const handleSend = async () => {
    if (!inputValue.trim() || isTyping) return;

    const message = inputValue.trim();
    setInputValue('');

    await sendMessage(message);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestedPrompt = async (prompt: string) => {
    await sendMessage(prompt);
  };

  const handleActionClick = (action: { type: string; path?: string; payload?: Record<string, unknown> }) => {
    if (action.type === 'navigate' && action.path) {
      window.location.href = action.path;
    } else if (action.type === 'dismiss') {
      // Just close the action, no-op
    } else {
      console.log('[OspraChat] Action clicked:', action);
    }
  };

  // ============================================
  // STATUS DOT COLOR
  // ============================================

  const getStatusColor = () => {
    switch (backendStatus) {
      case 'online':
        return 'online';
      case 'checking':
        return 'processing';
      case 'offline':
        return 'offline';
      default:
        return 'processing';
    }
  };

  const getStatusText = () => {
    switch (backendStatus) {
      case 'online':
        return 'Online';
      case 'checking':
        return 'Checking...';
      case 'offline':
        return 'Offline';
      default:
        return 'Unknown';
    }
  };

  // ============================================
  // FLOATING BUTTON (CLOSED STATE)
  // ============================================

  if (!isChatOpen) {
    return (
      <AnimatePresence>
        <motion.button
          onClick={openChat}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-2xl flex items-center justify-center hover:scale-105 transition-all group"
          style={{
            background: 'rgba(255, 255, 255, 0.65)',
            backdropFilter: 'blur(40px) saturate(180%)',
            WebkitBackdropFilter: 'blur(40px) saturate(180%)',
            border: '1px solid rgba(255, 255, 255, 0.5)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.8)',
          }}
          variants={buttonVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          {/* Rainbow refraction border */}
          <div
            className="absolute inset-[-1px] rounded-2xl opacity-50 group-hover:opacity-80 transition-opacity pointer-events-none"
            style={{
              padding: '1.5px',
              background: 'linear-gradient(135deg, rgba(255,120,120,0.4) 0%, rgba(255,200,120,0.3) 25%, rgba(120,255,200,0.35) 50%, rgba(120,200,255,0.4) 75%, rgba(200,120,255,0.35) 100%)',
              WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
              WebkitMaskComposite: 'xor',
              maskComposite: 'exclude',
            }}
          />
          <Brain className="w-6 h-6 text-blue-600" />
        </motion.button>
      </AnimatePresence>
    );
  }

  // ============================================
  // CHAT PANEL (OPEN STATE)
  // ============================================

  return (
    <AnimatePresence>
      {isChatOpen && (
        <motion.div
          className={`fixed z-50 transition-all duration-300 ${
            isChatMinimized
              ? 'bottom-6 right-6 w-72'
              : 'bottom-6 right-6 w-96 h-[600px]'
          }`}
          variants={chatVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
        >
          <div
            className="h-full flex flex-col rounded-2xl overflow-hidden relative"
            style={{
              background: 'rgba(255, 255, 255, 0.75)',
              backdropFilter: 'blur(40px) saturate(180%)',
              WebkitBackdropFilter: 'blur(40px) saturate(180%)',
              border: '1px solid rgba(255, 255, 255, 0.5)',
              boxShadow: '0 8px 48px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.8)',
            }}
          >
            {/* Rainbow refraction border */}
            <div
              className="absolute inset-[-1px] rounded-2xl opacity-50 pointer-events-none"
              style={{
                padding: '1.5px',
                background: 'linear-gradient(135deg, rgba(255,120,120,0.35) 0%, rgba(255,200,120,0.25) 20%, rgba(120,255,200,0.3) 40%, rgba(120,200,255,0.35) 60%, rgba(200,120,255,0.3) 80%, rgba(255,120,200,0.25) 100%)',
                WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
                WebkitMaskComposite: 'xor',
                maskComposite: 'exclude',
              }}
            />

            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-black/5 relative z-10">
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-xl flex items-center justify-center"
                  style={{
                    background: 'linear-gradient(135deg, #0071E3 0%, #5856D6 100%)',
                  }}
                >
                  <Brain className="w-4 h-4 text-white" />
                </div>
                <div>
                  <h3 className="text-sm font-medium text-primary">Ospra</h3>
                  <div className="flex items-center gap-1.5">
                    <div className={`status-dot ${getStatusColor()}`} />
                    <span className="text-xs text-tertiary">{getStatusText()}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => isChatMinimized ? maximizeChat() : minimizeChat()}
                  className="p-2 rounded-lg hover:bg-black/5 text-secondary hover:text-primary transition-colors"
                  aria-label={isChatMinimized ? 'Maximize' : 'Minimize'}
                >
                  {isChatMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
                </button>
                <button
                  onClick={closeChat}
                  className="p-2 rounded-lg hover:bg-black/5 text-secondary hover:text-primary transition-colors"
                  aria-label="Close"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {!isChatMinimized && (
              <>
                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 relative z-10">
                  {/* Empty State with Suggested Prompts */}
                  {messages.length === 0 && !isTyping && (
                    <div className="text-center py-8 space-y-6">
                      <div
                        className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-3"
                        style={{
                          background: 'rgba(0, 113, 227, 0.1)',
                        }}
                      >
                        <Sparkles className="w-6 h-6 text-accent" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-primary mb-1">Hi, I'm Ospra</p>
                        <p className="text-xs text-secondary">Your AI-powered e-commerce intelligence</p>
                      </div>

                      {/* Suggested Prompts */}
                      <div className="grid grid-cols-2 gap-2 pt-4">
                        {OSPRA_SUGGESTED_PROMPTS.map((prompt) => (
                          <motion.button
                            key={prompt.id}
                            onClick={() => handleSuggestedPrompt(prompt.prompt)}
                            className="p-3 rounded-xl text-left text-xs transition-all hover:scale-[1.02]"
                            style={{
                              background: 'rgba(0, 0, 0, 0.03)',
                              border: '1px solid rgba(0, 0, 0, 0.06)',
                            }}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            <div className="font-medium text-primary mb-0.5">
                              {prompt.icon} {prompt.label}
                            </div>
                            <div className="text-tertiary line-clamp-2">{prompt.prompt}</div>
                          </motion.button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Message List */}
                  {messages.map((message) => (
                    <motion.div
                      key={message.id}
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3 }}
                    >
                      <div
                        className={`max-w-[85%] ${
                          message.role === 'user'
                            ? 'bg-accent text-white p-3 rounded-xl'
                            : 'space-y-2'
                        }`}
                      >
                        {/* Assistant Message Content */}
                        {message.role === 'assistant' && (
                          <div
                            className="p-3 rounded-xl text-sm text-primary"
                            style={{
                              background: 'rgba(255, 255, 255, 0.5)',
                              border: '1px solid rgba(0, 0, 0, 0.05)',
                            }}
                          >
                            {message.content}
                          </div>
                        )}

                        {/* User Message Content */}
                        {message.role === 'user' && (
                          <div className="text-sm">{message.content}</div>
                        )}

                        {/* Action Buttons */}
                        {message.role === 'assistant' && message.actions && message.actions.length > 0 && (
                          <div className="flex flex-wrap gap-2 pt-1">
                            {message.actions.map((action) => (
                              <motion.button
                                key={action.id}
                                onClick={() => handleActionClick(action)}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                                style={{
                                  background: 'rgba(0, 113, 227, 0.1)',
                                  color: 'var(--accent)',
                                }}
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                              >
                                {action.label}
                                {action.type === 'navigate' && <ExternalLink className="w-3 h-3" />}
                              </motion.button>
                            ))}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  ))}

                  {/* Streaming Content */}
                  {streamingContent && (
                    <motion.div
                      className="flex justify-start"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      <div
                        className="max-w-[85%] p-3 rounded-xl text-sm text-primary"
                        style={{
                          background: 'rgba(255, 255, 255, 0.5)',
                          border: '1px solid rgba(0, 0, 0, 0.05)',
                        }}
                      >
                        {streamingContent}
                        <span className="inline-block w-1 h-4 ml-1 bg-accent animate-pulse" />
                      </div>
                    </motion.div>
                  )}

                  {/* Typing Indicator */}
                  {isTyping && !streamingContent && (
                    <motion.div
                      className="flex justify-start"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      <div
                        className="p-3 rounded-xl"
                        style={{
                          background: 'rgba(255, 255, 255, 0.5)',
                          border: '1px solid rgba(0, 0, 0, 0.05)',
                        }}
                      >
                        <Loader2 className="w-4 h-4 animate-spin text-accent" />
                      </div>
                    </motion.div>
                  )}

                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <div className="p-4 border-t border-black/5 relative z-10">
                  <div className="flex items-center gap-2">
                    <input
                      ref={inputRef}
                      type="text"
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="Ask Ospra anything..."
                      disabled={isTyping}
                      className="flex-1 px-4 py-2.5 rounded-xl text-sm outline-none transition-all disabled:opacity-50"
                      style={{
                        background: 'rgba(0, 0, 0, 0.04)',
                        border: '1px solid rgba(0, 0, 0, 0.06)',
                      }}
                    />
                    <motion.button
                      onClick={handleSend}
                      disabled={!inputValue.trim() || isTyping}
                      className="p-2.5 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      aria-label="Send message"
                    >
                      <Send className="w-4 h-4 text-white" />
                    </motion.button>
                  </div>
                </div>
              </>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
