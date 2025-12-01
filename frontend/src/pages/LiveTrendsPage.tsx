import { useState, useEffect } from 'react';
import { TrendingUp, Twitter, Clock, Heart, MessageCircle, Repeat2, Hash } from 'lucide-react';

interface TwitterProduct {
  name: string;
  score: number;
  recommendation: string;
  source: string;
  details: {
    name: string;
    url: string;
    image_url: string | null;
    price: number;
    tweet_count: number;
    total_likes: number;
    total_retweets: number;
    total_replies: number;
    engagement_rate: number;
    sentiment: 'positive' | 'negative' | 'neutral';
    sentiment_score: number;
    source_hashtags: string[];
    sample_tweets: string[];
    influencer_mentions: string[];
    viral_score: number;
    buy_signal: string;
    source: string;
  };
}

export default function LiveTrendsPage() {
  const [products, setProducts] = useState<TwitterProduct[]>([]);
  const [loading, setLoading] = useState(false);
  const [niche, setNiche] = useState('smart_home');
  const [timeRange, setTimeRange] = useState('24h');
  const [maxProducts, setMaxProducts] = useState(10);

  const niches = [
    { value: 'smart_home', label: 'Smart Home' },
    { value: 'fitness', label: 'Fitness' },
    { value: 'beauty', label: 'Beauty' },
    { value: 'tech_gadgets', label: 'Tech Gadgets' },
    { value: 'home_decor', label: 'Home Decor' },
    { value: 'kitchen', label: 'Kitchen' },
  ];

  const timeRanges = [
    { value: '24h', label: 'Last 24 Hours' },
    { value: '7d', label: 'Last 7 Days' },
    { value: '30d', label: 'Last 30 Days' },
  ];

  const fetchViralProducts = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8001/research/twitter-viral', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche, max_products: maxProducts, time_range: timeRange }),
      });
      const data = await response.json();
      setProducts(data);
    } catch (error) {
      console.error('Error fetching viral products:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchViralProducts();
  }, []);

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'positive': return 'text-green-400';
      case 'negative': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return 'text-green-400';
    if (score >= 40) return 'text-yellow-400';
    return 'text-gray-400';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-violet-900 p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Twitter className="w-8 h-8 text-blue-400" />
          <h1 className="text-4xl font-bold text-white">Live Viral Trends</h1>
        </div>
        <p className="text-gray-300">Discover viral products trending on Twitter/X powered by xAI Grok</p>
      </div>

      {/* Filters */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="glass p-6 rounded-2xl">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Niche Selector */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Niche</label>
              <select
                value={niche}
                onChange={(e) => setNiche(e.target.value)}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                {niches.map((n) => (
                  <option key={n.value} value={n.value} className="bg-gray-800">
                    {n.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Time Range */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Time Range</label>
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                {timeRanges.map((t) => (
                  <option key={t.value} value={t.value} className="bg-gray-800">
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Max Products */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Max Results</label>
              <input
                type="number"
                value={maxProducts}
                onChange={(e) => setMaxProducts(Number(e.target.value))}
                min={1}
                max={50}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>

            {/* Search Button */}
            <div className="flex items-end">
              <button
                onClick={fetchViralProducts}
                disabled={loading}
                className="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-gray-600 text-white font-semibold py-2 px-6 rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Searching...
                  </>
                ) : (
                  <>
                    <TrendingUp className="w-4 h-4" />
                    Find Trends
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="max-w-7xl mx-auto">
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-400 mx-auto mb-4"></div>
            <p className="text-gray-300">Analyzing Twitter trends with xAI Grok...</p>
          </div>
        ) : products.length === 0 ? (
          <div className="glass p-12 rounded-2xl text-center">
            <Twitter className="w-16 h-16 text-gray-500 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-300 mb-2">No viral products found</h3>
            <p className="text-gray-400">Try adjusting your filters or search different niche</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {products.map((product, idx) => (
              <div key={idx} className="glass p-6 rounded-2xl hover:scale-[1.02] transition-transform">
                <div className="flex flex-col lg:flex-row gap-6">
                  {/* Product Info */}
                  <div className="flex-1">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <h3 className="text-2xl font-bold text-white mb-2">{product.details.name}</h3>
                        <div className="flex items-center gap-4 flex-wrap">
                          <span className="text-3xl font-bold text-blue-400">${product.details.price}</span>
                          <div className={`flex items-center gap-2 px-3 py-1 rounded-lg bg-white/10 ${getScoreColor(product.details.viral_score)}`}>
                            <TrendingUp className="w-4 h-4" />
                            <span className="font-semibold">{product.details.viral_score}/100</span>
                          </div>
                          <div className={`px-3 py-1 rounded-lg ${getSentimentColor(product.details.sentiment)} bg-white/10`}>
                            {product.details.sentiment} ({(product.details.sentiment_score * 100).toFixed(0)}%)
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Engagement Metrics */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                      <div className="bg-white/5 p-3 rounded-lg">
                        <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
                          <Twitter className="w-4 h-4" />
                          Tweets
                        </div>
                        <div className="text-xl font-bold text-white">{product.details.tweet_count}</div>
                      </div>
                      <div className="bg-white/5 p-3 rounded-lg">
                        <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
                          <Heart className="w-4 h-4" />
                          Likes
                        </div>
                        <div className="text-xl font-bold text-white">{product.details.total_likes.toLocaleString()}</div>
                      </div>
                      <div className="bg-white/5 p-3 rounded-lg">
                        <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
                          <Repeat2 className="w-4 h-4" />
                          Retweets
                        </div>
                        <div className="text-xl font-bold text-white">{product.details.total_retweets.toLocaleString()}</div>
                      </div>
                      <div className="bg-white/5 p-3 rounded-lg">
                        <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
                          <MessageCircle className="w-4 h-4" />
                          Engagement
                        </div>
                        <div className="text-xl font-bold text-white">{(product.details.engagement_rate * 100).toFixed(1)}%</div>
                      </div>
                    </div>

                    {/* Hashtags */}
                    {product.details.source_hashtags.length > 0 && (
                      <div className="mb-4">
                        <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
                          <Hash className="w-4 h-4" />
                          Trending Hashtags
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {product.details.source_hashtags.map((tag, i) => (
                            <span key={i} className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-sm">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Sample Tweets */}
                    {product.details.sample_tweets.length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-sm font-semibold text-gray-400 mb-2">Sample Tweets:</h4>
                        <div className="space-y-2">
                          {product.details.sample_tweets.slice(0, 2).map((tweet, i) => (
                            <div key={i} className="bg-white/5 p-3 rounded-lg border-l-2 border-blue-400">
                              <p className="text-gray-300 text-sm italic">"{tweet}"</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Influencer Mentions */}
                    {product.details.influencer_mentions.length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-sm font-semibold text-gray-400 mb-2">Mentioned by Influencers:</h4>
                        <div className="flex flex-wrap gap-2">
                          {product.details.influencer_mentions.map((influencer, i) => (
                            <span key={i} className="px-3 py-1 bg-purple-500/20 text-purple-300 rounded-full text-sm">
                              {influencer}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Buy Signal */}
                    <div className="mt-4 pt-4 border-t border-white/10">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm text-gray-400 mb-1">Buy Signal</div>
                          <div className="text-lg font-semibold text-white">{product.details.buy_signal}</div>
                        </div>
                        {product.details.url && (
                          <a
                            href={product.details.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-6 py-2 bg-blue-500 hover:bg-blue-600 text-white font-semibold rounded-lg transition-colors"
                          >
                            View Product
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Powered By */}
      <div className="max-w-7xl mx-auto mt-8 text-center">
        <p className="text-gray-400 text-sm">
          Powered by <span className="text-blue-400 font-semibold">xAI Grok</span> • Real-time Twitter/X analysis
        </p>
      </div>
    </div>
  );
}
