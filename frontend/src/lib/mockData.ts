import type { EmailMetrics } from '../types';

export const mockEmailMetrics: EmailMetrics = {
  total_processed: 247,
  auto_replied: 198,
  pending: 12,
  response_rate: 80.2,
  categories: [
    { name: 'Order Inquiries', count: 89 },
    { name: 'Shipping Questions', count: 64 },
    { name: 'Product Questions', count: 42 },
    { name: 'Returns/Refunds', count: 31 },
    { name: 'General Support', count: 21 },
  ],
};