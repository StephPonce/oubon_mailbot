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

export function useAnalyticsOverview() {
  return useQuery({
    queryKey: ['analytics', 'overview'],
    queryFn: async () => {
      const response = await api.get('/api/portfolio/overview');
      return response.data;
    },
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes
  });
}

export function usePortfolioRankings() {
  return useQuery({
    queryKey: ['portfolio', 'rankings'],
    queryFn: async () => {
      const response = await api.get('/api/portfolio/rankings');
      return response.data;
    },
  });
}

export function useNiches() {
  return useQuery({
    queryKey: ['niches'],
    queryFn: async () => {
      const response = await api.get('/api/dashboard/v2/niches');
      return response.data;
    },
    staleTime: 1000 * 60 * 10, // 10 minutes
  });
}

export function useInventory() {
  return useQuery({
    queryKey: ['inventory'],
    queryFn: async () => {
      const response = await api.get('/api/inventory');
      return response.data;
    },
    refetchInterval: 1000 * 60 * 2, // Refetch every 2 minutes
  });
}

export function useDailyAnalytics() {
  return useQuery({
    queryKey: ['analytics', 'daily'],
    queryFn: async () => {
      const response = await api.get('/analytics/daily');
      return response.data;
    },
  });
}
