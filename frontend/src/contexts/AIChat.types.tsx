import { createContext } from 'react';

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export interface AIChatContextType {
  messages: Message[];
  isOpen: boolean;
  isMinimized: boolean;
  loading: boolean;
  addMessage: (message: Message) => void;
  setIsOpen: (isOpen: boolean) => void;
  setIsMinimized: (isMinimized: boolean) => void;
  clearMessages: () => void;
  sendMessage: (text: string) => Promise<void>;
}

export const AIChatContext = createContext<AIChatContextType>({
  messages: [],
  isOpen: false,
  isMinimized: false,
  loading: false,
  addMessage: () => {},
  setIsOpen: () => {},
  setIsMinimized: () => {},
  clearMessages: () => {},
  sendMessage: async () => {},
});
