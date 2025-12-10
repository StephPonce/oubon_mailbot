import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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

interface ProductFilters {
  niche?: string;
  limit?: number;
  page?: number;
}

export function useProducts(filters?: ProductFilters) {
  return useQuery({
    queryKey: ['products', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters?.niche) params.append('niche', filters.niche);
      if (filters?.limit) params.append('per_page', filters.limit.toString());
      if (filters?.page) params.append('page', filters.page.toString());

      const response = await api.get(`/api/products?${params}`);
      return response.data;
    },
  });
}

export function useProductsByNiche(niche: string) {
  return useQuery({
    queryKey: ['products', 'niche', niche],
    queryFn: async () => {
      const response = await api.get(`/api/dashboard/v2/products?niche=${niche}`);
      return response.data;
    },
    enabled: !!niche,
  });
}

export function useDeployProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (productId: string) => {
      const response = await api.post(`/api/shopify/deploy`, { product_id: productId });
      return response.data;
    },
    onSuccess: () => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
}

export function useAnalyzeProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (productId: string) => {
      const response = await api.post(`/api/products/${productId}/analyze`);
      return response.data;
    },
    onSuccess: (_, productId) => {
      queryClient.invalidateQueries({ queryKey: ['products', productId] });
    },
  });
}
