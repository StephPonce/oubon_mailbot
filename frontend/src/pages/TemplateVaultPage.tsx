import React, { useState, useEffect } from 'react';
import {
  Store,
  Search,
  Filter,
  Star,
  TrendingUp,
  Package,
  DollarSign,
  Download,
  Eye,
  Heart,
  ShoppingCart,
  Check,
  Sparkles,
  Tag,
  Users,
  Calendar,
  ArrowUpDown,
  Grid,
  List,
  X
} from 'lucide-react';

// Types
interface ActionTemplate {
  id: number;
  name: string;
  slug: string;
  short_description: string;
  category: string;
  tags: string[];
  niches: string[];
  is_free: boolean;
  price: number;
  uses_count: number;
  avg_rating: number;
  ratings_count: number;
  is_featured: boolean;
  actions_count: number;
  creator: {
    id: number;
    name: string;
  };
  created_at: string;
}

interface BrowseResponse {
  templates: ActionTemplate[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

const CATEGORIES = [
  { value: 'all', label: 'All Templates', icon: <Package className="w-4 h-4" /> },
  { value: 'pricing', label: 'Pricing', icon: <DollarSign className="w-4 h-4" /> },
  { value: 'launch', label: 'Launch', icon: <TrendingUp className="w-4 h-4" /> },
  { value: 'promotion', label: 'Promotion', icon: <Tag className="w-4 h-4" /> },
  { value: 'seasonal', label: 'Seasonal', icon: <Calendar className="w-4 h-4" /> },
  { value: 'advertising', label: 'Advertising', icon: <Sparkles className="w-4 h-4" /> },
  { value: 'email', label: 'Email', icon: <Heart className="w-4 h-4" /> },
  { value: 'recovery', label: 'Recovery', icon: <Users className="w-4 h-4" /> },
];

const SORT_OPTIONS = [
  { value: 'popular', label: 'Most Popular' },
  { value: 'rating', label: 'Highest Rated' },
  { value: 'newest', label: 'Newest First' },
  { value: 'price_low', label: 'Price: Low to High' },
  { value: 'price_high', label: 'Price: High to Low' },
];

export default function TemplateVaultPage() {
  const [templates, setTemplates] = useState<ActionTemplate[]>([]);
  const [featuredTemplates, setFeaturedTemplates] = useState<ActionTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [sortBy, setSortBy] = useState('popular');
  const [freeOnly, setFreeOnly] = useState(false);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    fetchFeaturedTemplates();
  }, []);

  useEffect(() => {
    fetchTemplates();
  }, [searchQuery, selectedCategory, sortBy, freeOnly, page]);

  const fetchFeaturedTemplates = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/templates/featured?limit=6');
      if (response.ok) {
        const data = await response.json();
        setFeaturedTemplates(data);
      }
    } catch (error) {
      console.error('Failed to fetch featured templates:', error);
    }
  };

  const fetchTemplates = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: '12',
        sort_by: sortBy,
        free_only: freeOnly.toString(),
      });

      if (searchQuery) params.append('search', searchQuery);
      if (selectedCategory !== 'all') params.append('category', selectedCategory);

      const response = await fetch(`http://localhost:8001/api/templates/browse?${params}`);
      if (response.ok) {
        const data: BrowseResponse = await response.json();
        setTemplates(data.templates);
        setTotalPages(data.pages);
      }
    } catch (error) {
      console.error('Failed to fetch templates:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderStars = (rating: number) => {
    return (
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`w-4 h-4 ${
              star <= rating
                ? 'fill-yellow-400 text-yellow-400'
                : 'text-gray-300'
            }`}
          />
        ))}
      </div>
    );
  };

  const renderTemplateCard = (template: ActionTemplate) => {
    return (
      <div
        key={template.id}
        className="glass rounded-xl p-5 hover:shadow-xl transition-all duration-200 hover:-translate-y-1 cursor-pointer border border-white/10"
        onClick={() => window.location.href = `/templates/${template.slug}`}
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              {template.is_featured && (
                <span className="px-2 py-0.5 rounded-full bg-gradient-to-r from-yellow-500/20 to-orange-500/20 text-yellow-300 text-[10px] font-semibold flex items-center gap-1">
                  <Sparkles className="w-3 h-3" />
                  FEATURED
                </span>
              )}
              <span className="px-2 py-0.5 rounded-full bg-cyan-500/20 text-blue-300 text-[10px] font-medium">
                {template.category.toUpperCase()}
              </span>
            </div>
            <h3 className="font-semibold text-white text-lg mb-1">{template.name}</h3>
            <p className="text-sm text-tertiary line-clamp-2">{template.short_description}</p>
          </div>
        </div>

        {/* Tags */}
        {template.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {template.tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="px-2 py-0.5 rounded-md bg-white/5 text-tertiary text-xs"
              >
                #{tag}
              </span>
            ))}
            {template.tags.length > 3 && (
              <span className="px-2 py-0.5 rounded-md bg-white/5 text-tertiary text-xs">
                +{template.tags.length - 3}
              </span>
            )}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 mb-3 py-3 border-y border-white/10">
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 mb-1">
              {renderStars(template.avg_rating)}
            </div>
            <p className="text-xs text-tertiary">{template.ratings_count} reviews</p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 mb-1">
              <Download className="w-4 h-4 text-purple-400" />
              <span className="font-semibold text-white">{template.uses_count}</span>
            </div>
            <p className="text-xs text-tertiary">uses</p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 mb-1">
              <Package className="w-4 h-4 text-blue-400" />
              <span className="font-semibold text-white">{template.actions_count}</span>
            </div>
            <p className="text-xs text-tertiary">actions</p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between">
          <div>
            {template.is_free ? (
              <span className="text-green-400 font-semibold text-lg">FREE</span>
            ) : (
              <span className="text-white font-semibold text-lg">${template.price}</span>
            )}
          </div>
          <button
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500/20 to-pink-500/20 hover:from-purple-500/30 hover:to-pink-500/30 text-purple-300 font-medium text-sm border border-purple-500/30 hover:border-purple-500/50 transition-all flex items-center gap-2"
            onClick={(e) => {
              e.stopPropagation();
              // Handle template action
            }}
          >
            <Eye className="w-4 h-4" />
            View Details
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent mb-2">
            Template Vault
          </h1>
          <p className="text-tertiary">
            Browse and purchase proven action templates from successful stores
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
            className="px-4 py-2 rounded-lg glass border border-white/10 hover:border-white/20 transition-colors"
          >
            {viewMode === 'grid' ? <List className="w-5 h-5" /> : <Grid className="w-5 h-5" />}
          </button>
          <button
            onClick={() => window.location.href = '/templates/create'}
            className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white font-semibold flex items-center gap-2 transition-all shadow-lg shadow-purple-500/25"
          >
            <Sparkles className="w-5 h-5" />
            Create Template
          </button>
        </div>
      </div>

      {/* Featured Templates */}
      {featuredTemplates.length > 0 && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <Sparkles className="w-6 h-6 text-yellow-400" />
            <h2 className="text-2xl font-bold text-white">Featured Templates</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {featuredTemplates.map(renderTemplateCard)}
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className="glass rounded-xl p-6 space-y-4">
        {/* Search Bar */}
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-tertiary" />
            <input
              type="text"
              placeholder="Search templates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 rounded-lg bg-black/20 border border-white/10 focus:border-purple-500/50 outline-none text-white placeholder-gray-400 transition-colors"
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`px-4 py-3 rounded-lg glass border transition-colors flex items-center gap-2 ${
              showFilters ? 'border-purple-500/50 bg-purple-500/10' : 'border-white/10'
            }`}
          >
            <Filter className="w-5 h-5" />
            Filters
          </button>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-white/10">
            {/* Sort */}
            <div>
              <label className="text-sm text-tertiary mb-2 block">Sort By</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full px-4 py-2 rounded-lg bg-black/20 border border-white/10 text-white outline-none focus:border-purple-500/50"
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Category */}
            <div>
              <label className="text-sm text-tertiary mb-2 block">Category</label>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="w-full px-4 py-2 rounded-lg bg-black/20 border border-white/10 text-white outline-none focus:border-purple-500/50"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Price Filter */}
            <div>
              <label className="text-sm text-tertiary mb-2 block">Price</label>
              <button
                onClick={() => setFreeOnly(!freeOnly)}
                className={`w-full px-4 py-2 rounded-lg border transition-colors ${
                  freeOnly
                    ? 'bg-green-500/20 border-green-500/50 text-green-300'
                    : 'bg-black/20 border-white/10 text-tertiary'
                }`}
              >
                {freeOnly ? '✓ ' : ''}Free Templates Only
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Templates Grid/List */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-white">
            {selectedCategory === 'all' ? 'All Templates' : CATEGORIES.find(c => c.value === selectedCategory)?.label}
          </h2>
          <p className="text-tertiary">{templates.length} templates found</p>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="glass rounded-xl p-5 animate-pulse">
                <div className="h-6 bg-white/10 rounded mb-3"></div>
                <div className="h-4 bg-white/10 rounded mb-2"></div>
                <div className="h-4 bg-white/10 rounded w-2/3"></div>
              </div>
            ))}
          </div>
        ) : templates.length === 0 ? (
          <div className="text-center py-20 glass rounded-xl">
            <Package className="w-16 h-16 text-secondary mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-white mb-2">No templates found</h3>
            <p className="text-tertiary mb-6">Try adjusting your filters or search query</p>
            <button
              onClick={() => {
                setSearchQuery('');
                setSelectedCategory('all');
                setFreeOnly(false);
              }}
              className="px-6 py-3 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 font-medium border border-purple-500/30 transition-all"
            >
              Clear Filters
            </button>
          </div>
        ) : (
          <div className={`grid ${viewMode === 'grid' ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3' : 'grid-cols-1'} gap-4`}>
            {templates.map(renderTemplateCard)}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-4 py-2 rounded-lg glass border border-white/10 hover:border-white/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>
          <div className="flex items-center gap-2">
            {[...Array(Math.min(5, totalPages))].map((_, i) => {
              const pageNum = i + 1;
              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={`w-10 h-10 rounded-lg font-medium transition-colors ${
                    page === pageNum
                      ? 'bg-purple-500 text-white'
                      : 'glass border border-white/10 hover:border-white/20 text-tertiary'
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="px-4 py-2 rounded-lg glass border border-white/10 hover:border-white/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
