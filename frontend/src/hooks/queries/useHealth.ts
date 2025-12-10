import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ospra_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function useSystemHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await api.get('/api/health');
      return response.data;
    },
    refetchInterval: 1000 * 30, // Check health every 30 seconds
  });
}

export function useDetailedHealth() {
  return useQuery({
    queryKey: ['health', 'detailed'],
    queryFn: async () => {
      const response = await api.get('/api/health/detailed');
      return response.data;
    },
    refetchInterval: 1000 * 60, // Check every minute
  });
}
