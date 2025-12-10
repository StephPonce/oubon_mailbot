import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: number;
  email: string;
  name: string;
  subscription_tier: string;
  created_at?: string;
  last_login?: string;
}

interface AppState {
  // User
  user: User | null;
  setUser: (user: User | null) => void;

  // Active Store (multi-store support)
  activeStoreId: string | null;
  setActiveStore: (storeId: string) => void;

  // Theme
  theme: 'light' | 'dark' | 'system';
  setTheme: (theme: 'light' | 'dark' | 'system') => void;

  // Ospra Chat
  isChatOpen: boolean;
  toggleChat: () => void;

  // Sidebar
  isSidebarCollapsed: boolean;
  toggleSidebar: () => void;

  // Notifications
  notifications: Array<{ id: string; message: string; type: 'success' | 'error' | 'info' }>;
  addNotification: (notification: { message: string; type: 'success' | 'error' | 'info' }) => void;
  removeNotification: (id: string) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      setUser: (user) => set({ user }),

      activeStoreId: null,
      setActiveStore: (storeId) => set({ activeStoreId: storeId }),

      theme: 'dark',
      setTheme: (theme) => set({ theme }),

      isChatOpen: false,
      toggleChat: () => set((state) => ({ isChatOpen: !state.isChatOpen })),

      isSidebarCollapsed: false,
      toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),

      notifications: [],
      addNotification: (notification) => set((state) => ({
        notifications: [
          ...state.notifications,
          { ...notification, id: Math.random().toString(36).substr(2, 9) }
        ]
      })),
      removeNotification: (id) => set((state) => ({
        notifications: state.notifications.filter(n => n.id !== id)
      })),
    }),
    {
      name: 'ospra-storage',
      partialize: (state) => ({
        theme: state.theme,
        activeStoreId: state.activeStoreId,
        isSidebarCollapsed: state.isSidebarCollapsed,
      }),
    }
  )
);
