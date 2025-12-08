/**
 * Ospra Intelligence - Global State Store
 * 
 * Central state management for:
 * - Onboarding flow
 * - Ospra AI chat
 * - User preferences
 * - Real-time notifications
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ============================================
// TYPES
// ============================================

export interface OspraMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  actions?: OspraAction[];
  isStreaming?: boolean;
}

export interface OspraAction {
  id: string;
  type: 'navigate' | 'deploy' | 'analyze' | 'discover' | 'dismiss';
  label: string;
  path?: string;
  payload?: Record<string, unknown>;
}

export interface OspraInsight {
  id: string;
  type: 'trending' | 'warning' | 'opportunity' | 'success';
  title: string;
  description: string;
  action?: OspraAction;
  priority: 'high' | 'medium' | 'low';
  createdAt: Date;
  read: boolean;
}

export interface OnboardingStep {
  id: string;
  title: string;
  completed: boolean;
}

export interface UserPreferences {
  selectedNiches: string[];
  selectedPlatform: 'shopify' | 'amazon' | 'woocommerce' | 'etsy' | null;
  autoDeployEnabled: boolean;
  notificationsEnabled: boolean;
  dailyBriefingEnabled: boolean;
  theme: 'light' | 'dark' | 'system';
}

// ============================================
// STORE STATE
// ============================================

interface OspraState {
  // Onboarding
  isOnboarded: boolean;
  onboardingStep: number;
  onboardingSteps: OnboardingStep[];
  showWelcomeModal: boolean;
  
  // Chat
  isChatOpen: boolean;
  isChatMinimized: boolean;
  messages: OspraMessage[];
  isTyping: boolean;
  streamingContent: string;
  
  // Insights & Notifications
  insights: OspraInsight[];
  unreadCount: number;
  lastBriefingDate: string | null;
  
  // User Preferences (persisted)
  preferences: UserPreferences;
  userName: string;
  
  // Connection Status
  isConnected: boolean;
  backendStatus: 'online' | 'offline' | 'checking';
}

interface OspraActions {
  // Onboarding
  setOnboarded: (value: boolean) => void;
  setOnboardingStep: (step: number) => void;
  completeOnboardingStep: (stepId: string) => void;
  setShowWelcomeModal: (show: boolean) => void;
  resetOnboarding: () => void;
  
  // Chat
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
  minimizeChat: () => void;
  maximizeChat: () => void;
  addMessage: (message: Omit<OspraMessage, 'id' | 'timestamp'>) => void;
  setTyping: (isTyping: boolean) => void;
  setStreamingContent: (content: string) => void;
  clearMessages: () => void;
  
  // Insights
  addInsight: (insight: Omit<OspraInsight, 'id' | 'createdAt' | 'read'>) => void;
  markInsightRead: (id: string) => void;
  clearInsights: () => void;
  setLastBriefingDate: (date: string) => void;
  
  // Preferences
  updatePreferences: (prefs: Partial<UserPreferences>) => void;
  setUserName: (name: string) => void;
  
  // Connection
  setConnected: (connected: boolean) => void;
  setBackendStatus: (status: 'online' | 'offline' | 'checking') => void;
}

// ============================================
// DEFAULT VALUES
// ============================================

const defaultOnboardingSteps: OnboardingStep[] = [
  { id: 'welcome', title: 'Meet Ospra', completed: false },
  { id: 'connect-shopify', title: 'Connect Shopify', completed: false },
  { id: 'select-niches', title: 'Choose Niches', completed: false },
  { id: 'enable-features', title: 'Enable Features', completed: false },
];

const defaultPreferences: UserPreferences = {
  selectedNiches: ['smart_home'],
  selectedPlatform: null,
  autoDeployEnabled: false,
  notificationsEnabled: true,
  dailyBriefingEnabled: true,
  theme: 'light',
};

// ============================================
// STORE
// ============================================

export const useOspraStore = create<OspraState & OspraActions>()(
  persist(
    (set, get) => ({
      // Initial State
      isOnboarded: false,
      onboardingStep: 0,
      onboardingSteps: defaultOnboardingSteps,
      showWelcomeModal: false,
      
      isChatOpen: false,
      isChatMinimized: false,
      messages: [],
      isTyping: false,
      streamingContent: '',
      
      insights: [],
      unreadCount: 0,
      lastBriefingDate: null,
      
      preferences: defaultPreferences,
      userName: '',
      
      isConnected: false,
      backendStatus: 'checking',
      
      // Onboarding Actions
      setOnboarded: (value) => set({ isOnboarded: value }),
      
      setOnboardingStep: (step) => set({ onboardingStep: step }),
      
      completeOnboardingStep: (stepId) => set((state) => ({
        onboardingSteps: state.onboardingSteps.map((s) =>
          s.id === stepId ? { ...s, completed: true } : s
        ),
      })),
      
      setShowWelcomeModal: (show) => set({ showWelcomeModal: show }),
      
      resetOnboarding: () => set({
        isOnboarded: false,
        onboardingStep: 0,
        onboardingSteps: defaultOnboardingSteps,
        showWelcomeModal: false,
      }),
      
      // Chat Actions
      openChat: () => set({ isChatOpen: true, isChatMinimized: false }),
      
      closeChat: () => set({ isChatOpen: false }),
      
      toggleChat: () => set((state) => ({ 
        isChatOpen: !state.isChatOpen,
        isChatMinimized: false,
      })),
      
      minimizeChat: () => set({ isChatMinimized: true }),
      
      maximizeChat: () => set({ isChatMinimized: false }),
      
      addMessage: (message) => set((state) => ({
        messages: [
          ...state.messages,
          {
            ...message,
            id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            timestamp: new Date(),
          },
        ],
      })),
      
      setTyping: (isTyping) => set({ isTyping }),
      
      setStreamingContent: (content) => set({ streamingContent: content }),
      
      clearMessages: () => set({ messages: [], streamingContent: '' }),
      
      // Insight Actions
      addInsight: (insight) => set((state) => ({
        insights: [
          {
            ...insight,
            id: `insight-${Date.now()}`,
            createdAt: new Date(),
            read: false,
          },
          ...state.insights,
        ],
        unreadCount: state.unreadCount + 1,
      })),
      
      markInsightRead: (id) => set((state) => ({
        insights: state.insights.map((i) =>
          i.id === id ? { ...i, read: true } : i
        ),
        unreadCount: Math.max(0, state.unreadCount - 1),
      })),
      
      clearInsights: () => set({ insights: [], unreadCount: 0 }),
      
      setLastBriefingDate: (date) => set({ lastBriefingDate: date }),
      
      // Preference Actions
      updatePreferences: (prefs) => set((state) => ({
        preferences: { ...state.preferences, ...prefs },
      })),
      
      setUserName: (name) => set({ userName: name }),
      
      // Connection Actions
      setConnected: (connected) => set({ isConnected: connected }),
      
      setBackendStatus: (status) => set({ backendStatus: status }),
    }),
    {
      name: 'ospra-storage',
      partialize: (state) => ({
        // Only persist these fields
        isOnboarded: state.isOnboarded,
        onboardingSteps: state.onboardingSteps,
        preferences: state.preferences,
        userName: state.userName,
        lastBriefingDate: state.lastBriefingDate,
      }),
    }
  )
);

// ============================================
// SELECTORS (for optimized re-renders)
// ============================================

export const selectIsOnboarded = (state: OspraState) => state.isOnboarded;
export const selectIsChatOpen = (state: OspraState) => state.isChatOpen;
export const selectMessages = (state: OspraState) => state.messages;
export const selectInsights = (state: OspraState) => state.insights;
export const selectUnreadCount = (state: OspraState) => state.unreadCount;
export const selectPreferences = (state: OspraState) => state.preferences;
export const selectUserName = (state: OspraState) => state.userName;
export const selectBackendStatus = (state: OspraState) => state.backendStatus;

// ============================================
// HELPER HOOKS
// ============================================

export function useOspraChat() {
  const {
    isChatOpen,
    isChatMinimized,
    messages,
    isTyping,
    streamingContent,
    openChat,
    closeChat,
    toggleChat,
    minimizeChat,
    maximizeChat,
    addMessage,
    setTyping,
    setStreamingContent,
    clearMessages,
  } = useOspraStore();
  
  return {
    isChatOpen,
    isChatMinimized,
    messages,
    isTyping,
    streamingContent,
    openChat,
    closeChat,
    toggleChat,
    minimizeChat,
    maximizeChat,
    addMessage,
    setTyping,
    setStreamingContent,
    clearMessages,
  };
}

export function useOspraOnboarding() {
  const {
    isOnboarded,
    onboardingStep,
    onboardingSteps,
    showWelcomeModal,
    setOnboarded,
    setOnboardingStep,
    completeOnboardingStep,
    setShowWelcomeModal,
    resetOnboarding,
  } = useOspraStore();
  
  return {
    isOnboarded,
    onboardingStep,
    onboardingSteps,
    showWelcomeModal,
    setOnboarded,
    setOnboardingStep,
    completeOnboardingStep,
    setShowWelcomeModal,
    resetOnboarding,
  };
}

export function useOspraInsights() {
  const {
    insights,
    unreadCount,
    addInsight,
    markInsightRead,
    clearInsights,
  } = useOspraStore();
  
  return {
    insights,
    unreadCount,
    addInsight,
    markInsightRead,
    clearInsights,
  };
}

export default useOspraStore;
