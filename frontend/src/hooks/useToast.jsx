/**
 * OSPRA INTELLIGENCE - TOAST NOTIFICATIONS
 * =========================================
 *
 * Tiny in-house toast system (task #51a) — replaces window.alert() calls.
 * No external deps: a context provider renders a stacked container in the
 * bottom-right, styled to match the app's glassmorphism look.
 *
 * Usage:
 *   const toast = useToast();
 *   toast.success('Product deployed to Shopify!');
 *   toast.error('Deploy failed: ' + err.message);
 *   toast.info('Enhancement queued');
 *
 * Mount <ToastProvider> once near the app root (see App.jsx).
 */

import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

// Errors linger longer — the user may need to read a failure reason.
const DURATION_MS = { success: 5000, info: 5000, error: 8000 };

const STYLES = {
  success: {
    border: 'border-emerald-400/30',
    icon: <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />,
  },
  error: {
    border: 'border-red-400/30',
    icon: <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />,
  },
  info: {
    border: 'border-cyan-400/30',
    icon: <Info className="w-5 h-5 text-cyan-400 shrink-0" />,
  },
};

function ToastItem({ toast, onDismiss }) {
  const style = STYLES[toast.type] || STYLES.info;
  return (
    <div
      role="status"
      className={`flex items-start gap-3 w-80 p-4 rounded-xl border ${style.border} backdrop-blur-xl bg-slate-900/90 shadow-lg shadow-black/40 animate-[toast-in_0.2s_ease-out]`}
    >
      {style.icon}
      <p className="flex-1 text-sm text-white/90 break-words">{toast.message}</p>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-white/40 hover:text-white transition-colors shrink-0"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (type, message) => {
      const id = ++nextId.current;
      setToasts((current) => [...current.slice(-4), { id, type, message: String(message) }]);
      setTimeout(() => dismiss(id), DURATION_MS[type] || 5000);
      return id;
    },
    [dismiss]
  );

  const api = useMemo(
    () => ({
      success: (message) => push('success', message),
      error: (message) => push('error', message),
      info: (message) => push('info', message),
      dismiss,
    }),
    [push, dismiss]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      {/* z-index above FloatingOiChat (z-50) so toasts are never buried */}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            <ToastItem toast={toast} onDismiss={dismiss} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used inside <ToastProvider>');
  }
  return context;
}
