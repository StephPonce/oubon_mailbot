import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

interface Product {
  id: string;
  name: string;
  image_url?: string;
  price: number;
  cost?: number;
  trend_score?: number;
  velocity_score?: number;
  score?: number;
  sales_rank?: number;
  orders?: number;
  competition_score?: number;
  profit_margin?: number;
  estimated_profit?: number;
  supplier_url?: string;
  niche?: string;
  discovered_at?: string;
  commission_rate?: number;
  tier?: string;
  rating?: number;
  original_price?: number;
  aliexpress_cost?: number;
  shipping_cost?: number;
  source?: string;
}

interface ProductsContextType {
  products: Product[];
  setProducts: (products: Product[]) => void;
  dataSource: string;
  setDataSource: (source: string) => void;
  lastRefresh: Date | null;
  setLastRefresh: (date: Date | null) => void;
  currentNiche: string;
  setCurrentNiche: (niche: string) => void;
  clearProducts: () => void;
}

const ProductsContext = createContext<ProductsContextType | undefined>(undefined);

export function ProductsProvider({ children }: { children: ReactNode }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [dataSource, setDataSource] = useState('');
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [currentNiche, setCurrentNiche] = useState('smart_home');

  const clearProducts = () => {
    setProducts([]);
    setDataSource('');
    setLastRefresh(null);
  };

  return (
    <ProductsContext.Provider
      value={{
        products,
        setProducts,
        dataSource,
        setDataSource,
        lastRefresh,
        setLastRefresh,
        currentNiche,
        setCurrentNiche,
        clearProducts,
      }}
    >
      {children}
    </ProductsContext.Provider>
  );
}

export function useProducts() {
  const context = useContext(ProductsContext);
  if (!context) {
    throw new Error('useProducts must be used within ProductsProvider');
  }
  return context;
}
