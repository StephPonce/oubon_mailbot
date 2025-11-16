import axios from 'axios';
import type { Product, DashboardStats, Niche } from '../types';

const API_BASE_URL = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const productAPI = {
  async getProducts(niche: string, page: number = 1, perPage: number = 20) {
    try {
      const response = await api.get('/api/dashboard/v2/products', {
        params: { niche, page, per_page: perPage },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch products:', error);
      throw error;
    }
  },

  async getStats(niche: string): Promise<DashboardStats> {
    try {
      const response = await api.get('/api/dashboard/v2/overview', {
        params: { niche },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      throw error;
    }
  },

  async getNiches(): Promise<{ niches: Niche[] }> {
    try {
      const response = await api.get('/api/dashboard/v2/niches');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch niches:', error);
      throw error;
    }
  },
};

export default api;