import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { productsAPI } from '../services/api';
import type { Product } from '../services/api';

interface ProductsContextType {
  products: Product[];
  isLoading: boolean;
  error: string | null;
  selectedProduct: Product | null;
  setSelectedProduct: (product: Product | null) => void;
  refreshProducts: (filters?: any) => Promise<void>;
  discoverProducts: (niches?: string[], maxPerNiche?: number) => Promise<void>;
  totalCount: number;
}

const ProductsContext = createContext<ProductsContextType | undefined>(undefined);

export function ProductsProvider({ children }: { children: ReactNode }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [totalCount, setTotalCount] = useState(0);

  // Fetch products from database
  const refreshProducts = useCallback(async (filters?: any) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await productsAPI.getAll(filters);
      const productList = response?.products || response || [];
      setProducts(productList);
      setTotalCount(response?.total || productList.length);
    } catch (err) {
      console.error('Failed to fetch products:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch products');
      setProducts([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Discover NEW products from APIs (AliExpress, TikTok, etc.)
  const discoverProducts = useCallback(async (
    niches: string[] = ['smart_home', 'fitness', 'kitchen'],
    maxPerNiche: number = 10
  ) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await productsAPI.discover(niches, maxPerNiche);
      const discoveredProducts = response?.products || [];
      
      // Merge discovered products with existing
      setProducts(prev => {
        const existingIds = new Set(prev.map(p => p.id));
        const newProducts = discoveredProducts.filter((p: Product) => !existingIds.has(p.id));
        return [...newProducts, ...prev];
      });
      
      setTotalCount(prev => prev + discoveredProducts.length);
      
      return response;
    } catch (err) {
      console.error('Failed to discover products:', err);
      setError(err instanceof Error ? err.message : 'Failed to discover products');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load products on mount
  useEffect(() => {
    refreshProducts();
  }, [refreshProducts]);

  return (
    <ProductsContext.Provider value={{ 
      products, 
      isLoading,
      error,
      selectedProduct, 
      setSelectedProduct,
      refreshProducts,
      discoverProducts,
      totalCount,
    }}>
      {children}
    </ProductsContext.Provider>
  );
}

export function useProductsContext() {
  const context = useContext(ProductsContext);
  if (!context) {
    throw new Error('useProductsContext must be used within a ProductsProvider');
  }
  return context;
}

// Legacy export for backwards compatibility
export const useProducts = useProductsContext;

export default ProductsContext;
