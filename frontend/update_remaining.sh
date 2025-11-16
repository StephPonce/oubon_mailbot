#!/bin/bash

# ProductCard.tsx
cat > src/components/products/ProductCard.tsx << 'EOFCARD'
import { FiTrendingUp, FiExternalLink } from 'react-icons/fi';
import type { Product } from '../../types';

interface ProductCardProps {
  product: Product;
  onClick: () => void;
}

export default function ProductCard({ product, onClick }: ProductCardProps) {
  const netProfit = product.price - product.cost;
  
  return (
    <div onClick={onClick} className="bg-white rounded-lg shadow hover:shadow-xl transition-shadow p-6 cursor-pointer border-2 border-transparent hover:border-blue-500">
      <div className="mb-4 rounded-lg overflow-hidden bg-gray-100">
        <img 
          src={product.image_url || `https://placehold.co/400x400/2563EB/white?text=${encodeURIComponent(product.name)}`}
          alt={product.name}
          className="w-full h-48 object-cover"
        />
      </div>
      
      <h3 className="font-bold text-lg text-gray-900 mb-2 line-clamp-2">{product.name}</h3>
      
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">Price:</span>
          <span className="font-bold text-green-600">${product.price.toFixed(2)}</span>
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">Net Profit:</span>
          <span className="font-bold text-blue-600">${netProfit.toFixed(2)}</span>
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">AI Score:</span>
          <span className="font-bold text-purple-600">{product.score}/10</span>
        </div>
      </div>
      
      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center text-sm text-gray-600">
          <FiTrendingUp className="mr-1" />
          <span>{product.profit_margin.toFixed(1)}% margin</span>
        </div>
        <FiExternalLink className="text-gray-400" />
      </div>
    </div>
  );
}
EOFCARD

# NicheSelector.tsx
cat > src/components/products/NicheSelector.tsx << 'EOFNICHE'
import { FiChevronDown } from 'react-icons/fi';

interface Niche {
  key: string;
  name: string;
  product_count: number;
  target_audience: string;
}

interface NicheSelectorProps {
  niches: Niche[];
  selectedNiche: string;
  onNicheChange: (nicheKey: string) => void;
}

export default function NicheSelector({ niches, selectedNiche, onNicheChange }: NicheSelectorProps) {
  return (
    <div className="relative inline-block">
      <select
        value={selectedNiche}
        onChange={(e) => onNicheChange(e.target.value)}
        className="appearance-none bg-white border-2 border-blue-500 rounded-lg px-4 py-2 pr-10 font-semibold text-gray-900 cursor-pointer hover:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {niches.map(niche => (
          <option key={niche.key} value={niche.key}>
            {niche.name}
          </option>
        ))}
      </select>
      <FiChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-600 pointer-events-none" size={20} />
    </div>
  );
}
EOFNICHE

# ProfitFilter.tsx  
cat > src/components/products/ProfitFilter.tsx << 'EOFPROFIT'
import { FiDollarSign } from 'react-icons/fi';

export const profitRanges: Record<string, { label: string; min: number; max: number }> = {
  all: { label: 'All Products', min: 0, max: Infinity },
  low: { label: '$0-$5', min: 0, max: 5 },
  medium: { label: '$5-$10', min: 5, max: 10 },
  high: { label: '$10-$15', min: 10, max: 15 },
  very_high: { label: '$15+', min: 15, max: Infinity },
};

interface ProfitFilterProps {
  selectedRange: string;
  onRangeChange: (rangeKey: string) => void;
}

export default function ProfitFilter({ selectedRange, onRangeChange }: ProfitFilterProps) {
  return (
    <div className="relative inline-block">
      <select
        value={selectedRange}
        onChange={(e) => onRangeChange(e.target.value)}
        className="appearance-none bg-white border border-gray-300 rounded-lg px-4 py-2 pr-10 text-sm font-medium text-gray-700 cursor-pointer hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {Object.entries(profitRanges).map(([key, range]) => (
          <option key={key} value={key}>
            {range.label}
          </option>
        ))}
      </select>
      <FiDollarSign className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 pointer-events-none" size={16} />
    </div>
  );
}
EOFPROFIT

# SortFilter.tsx
cat > src/components/products/SortFilter.tsx << 'EOFSORT'
import { FiArrowUpDown } from 'react-icons/fi';

const sortOptions = [
  { key: 'default', label: 'Default Order' },
  { key: 'net_profit_high', label: 'Net Profit (High to Low)' },
  { key: 'net_profit_low', label: 'Net Profit (Low to High)' },
  { key: 'score_high', label: 'AI Score (High to Low)' },
  { key: 'score_low', label: 'AI Score (Low to High)' },
  { key: 'margin_high', label: 'Profit Margin (High to Low)' },
  { key: 'margin_low', label: 'Profit Margin (Low to High)' },
  { key: 'price_high', label: 'Price (High to Low)' },
  { key: 'price_low', label: 'Price (Low to High)' },
];

interface SortFilterProps {
  selectedSort: string;
  onSortChange: (sortKey: string) => void;
}

export default function SortFilter({ selectedSort, onSortChange }: SortFilterProps) {
  return (
    <div className="relative inline-block">
      <select
        value={selectedSort}
        onChange={(e) => onSortChange(e.target.value)}
        className="appearance-none bg-white border border-gray-300 rounded-lg px-4 py-2 pr-10 text-sm font-medium text-gray-700 cursor-pointer hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {sortOptions.map(option => (
          <option key={option.key} value={option.key}>
            {option.label}
          </option>
        ))}
      </select>
      <FiArrowUpDown className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 pointer-events-none" size={16} />
    </div>
  );
}
EOFSORT

# Pagination.tsx
cat > src/components/products/Pagination.tsx << 'EOFPAGE'
import { FiChevronLeft, FiChevronRight } from 'react-icons/fi';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  return (
    <div className="flex items-center justify-center space-x-2 mt-8">
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
      >
        <FiChevronLeft size={16} />
        <span>Previous</span>
      </button>
      
      <div className="flex items-center space-x-2">
        {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
          <button
            key={page}
            onClick={() => onPageChange(page)}
            className={`px-4 py-2 rounded-lg ${
              page === currentPage
                ? 'bg-blue-600 text-white'
                : 'border border-gray-300 hover:bg-gray-50'
            }`}
          >
            {page}
          </button>
        ))}
      </div>
      
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
      >
        <span>Next</span>
        <FiChevronRight size={16} />
      </button>
    </div>
  );
}
EOFPAGE

echo "✅ All remaining components updated"
