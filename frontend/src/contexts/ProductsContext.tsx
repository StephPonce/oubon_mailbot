import { createContext, useContext, useState, ReactNode } from 'react';

interface Product {
  id: string;
  name: string;
  image: string;
  score: number;
  price: number;
  cost: number;
  profit: number;
  profitMargin: number;
  trend: 'up' | 'down' | 'stable';
  trendValue: string;
  source: string;
  niche: string;
  niches: string[];
  saturationLevel: 'low' | 'medium' | 'high';
  salesVelocity: number;
  socialMentions: number;
  aiReason: string;
  lastUpdated: string;
  rank: number;
  previousRank: number;
}

interface ProductsContextType {
  products: Product[];
  isLoading: boolean;
  selectedProduct: Product | null;
  setSelectedProduct: (product: Product | null) => void;
  refreshProducts: () => Promise<void>;
}

const ProductsContext = createContext<ProductsContextType | undefined>(undefined);

export function ProductsProvider({ children }: { children: ReactNode }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  const refreshProducts = async () => {
    setIsLoading(true);
    // Simulate API call
    setTimeout(() => {
      setProducts([]);
      setIsLoading(false);
    }, 1000);
  };

  return (
    <ProductsContext.Provider value={{ 
      products, 
      isLoading, 
      selectedProduct, 
      setSelectedProduct,
      refreshProducts 
    }}>
      {children}
    </ProductsContext.Provider>
  );
}

export function useProducts() {
  const context = useContext(ProductsContext);
  if (!context) {
    throw new Error('useProducts must be used within a ProductsProvider');
  }
  return context;
}

export default ProductsContext;
