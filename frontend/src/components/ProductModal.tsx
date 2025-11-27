import { useState } from 'react';
import axios from 'axios';
import { TrendingUp, ShoppingBag, Search, ExternalLink } from 'lucide-react';

interface ProductModalProps {
  product: {
    id: string;
    name: string;
    price: number;
    cost: number;
    velocity_score: number;
    niche: string;
    data_sources?: {
      aliexpress?: { available: boolean; orders?: number; url?: string };
      amazon?: { available: boolean; sales_rank?: number; url?: string };
      tiktok?: { available: boolean; views?: number; url?: string };
      google_trends?: { available: boolean; trend_score?: number };
    };
  };
  onClose: () => void;
}

export default function ProductModal({ product, onClose }: ProductModalProps) {
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  const analyzeProduct = async () => {
    setLoading(true);
    try {
      const response = await axios.post(
        `http://127.0.0.1:8001/api/dashboard/v2/products/${product.id}/analyze`
      );
      setAnalysis(response.data);
    } catch (error) {
      console.error('Analysis failed:', error);
      alert('Analysis failed - check console');
    } finally {
      setLoading(false);
    }
  };

  const sendChatMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;

    const userMessage = chatInput;
    setChatInput('');
    setChatLoading(true);

    // Add user message to chat
    const newMessages = [...chatMessages, { role: 'user', content: userMessage }];
    setChatMessages(newMessages);

    try {
      const response = await axios.post('http://127.0.0.1:8001/api/dashboard/v2/claude/chat', {
        message: userMessage,
        context: {
          product_name: product.name,
          product_price: product.price,
          product_cost: product.cost,
          velocity_score: product.velocity_score,
          profit_margin: (product as any).profit_margin,
          estimated_profit: (product as any).estimated_profit,
          niche: product.niche
        }
      });

      // Add Claude's response
      setChatMessages([...newMessages, {
        role: 'assistant',
        content: response.data.response
      }]);

    } catch (error) {
      console.error('Chat failed:', error);
      setChatMessages([...newMessages, {
        role: 'assistant',
        content: 'Sorry, I had trouble responding. Please try again.'
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center justify-center z-50 p-4">
      <div className="bg-white/5 border border-white/10 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 text-white">
        {/* Header */}
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-2xl font-bold text-white">{product.name}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            ✕
          </button>
        </div>

        {/* Product Info */}
        <div className="grid grid-cols-2 gap-4 mb-6 p-4 bg-white/5 rounded-xl border border-white/10">
          <div>
            <div className="text-sm text-gray-400">Price</div>
            <div className="text-xl font-bold text-green-400">${product.price.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Cost</div>
            <div className="text-xl font-bold text-gray-200">${product.cost.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Velocity</div>
            <div className="text-xl font-bold text-blue-400">{product.velocity_score}/100</div>
          </div>
          <div>
            <div className="text-sm text-gray-400">Niche</div>
            <div className="text-xl font-bold text-gray-200">{product.niche.replace('_', ' ')}</div>
          </div>
        </div>

        {/* AI Analysis Button */}
        {!analysis && (
          <button
            onClick={analyzeProduct}
            disabled={loading}
            className="w-full py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg font-bold hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 transition-all"
          >
            {loading ? '🤖 Claude is analyzing...' : '🤖 Analyze with Claude AI'}
          </button>
        )}

        {/* AI Analysis Results */}
        {analysis && (
          <div className="space-y-4">
            <div className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-bold">Claude AI Analysis</h3>
                <span className={`px-3 py-1 rounded font-bold text-sm ${
                  analysis.recommendation === 'STRONG_BUY' ? 'bg-green-500/80 text-white' :
                  analysis.recommendation === 'BUY' ? 'bg-blue-500/80 text-white' :
                  analysis.recommendation === 'HOLD' ? 'bg-yellow-500/80 text-white' :
                  'bg-red-500/80 text-white'
                }`}>
                  {analysis.recommendation}
                </span>
              </div>
              <div className="text-2xl font-bold text-purple-300 mb-2">
                Score: {analysis.score}/10
              </div>
              <div className="text-sm text-gray-300 mb-2">
                Success Prediction: {analysis.success_prediction}
              </div>
            </div>

            {/* Reasoning */}
            {analysis.reasoning && analysis.reasoning.length > 0 && (
              <div>
                <h4 className="font-bold mb-2 text-gray-200">💡 Marketing Pitches & Angles:</h4>
                <ul className="space-y-1">
                  {analysis.reasoning.map((reason: string, i: number) => (
                    <li key={i} className="text-sm text-gray-300">• {reason}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Risks */}
            {analysis.risks && analysis.risks.length > 0 && (
              <div>
                <h4 className="font-bold mb-2 text-gray-200">⚠️ Risks to Consider:</h4>
                <ul className="space-y-1">
                  {analysis.risks.map((risk: string, i: number) => (
                    <li key={i} className="text-sm text-gray-300">• {risk}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Full Analysis */}
            <div className="mt-4 p-4 bg-black/20 rounded text-sm text-gray-300 max-h-60 overflow-y-auto whitespace-pre-wrap border border-white/10">
              {analysis.analysis}
            </div>

            {/* Data Sources Section */}
            {product.data_sources && (
              <div className="mt-4 p-4 bg-white/5 rounded-xl border border-white/10">
                <h4 className="font-bold mb-3 flex items-center gap-2 text-gray-200">
                  <ExternalLink className="w-4 h-4" />
                  Data Sources & Verification
                </h4>
                <div className="space-y-2">
                  {product.data_sources.tiktok?.available && (
                    <div className="flex items-center justify-between p-2 bg-black/20 rounded-lg border border-white/10">
                      <div className="flex items-center gap-2">
                        <span className="text-[#FF0050] text-lg">♪</span>
                        <div>
                          <p className="text-sm font-medium text-gray-200">TikTok</p>
                          <p className="text-xs text-gray-400">{product.data_sources.tiktok.views?.toLocaleString() || 'N/A'} views</p>
                        </div>
                      </div>
                      {product.data_sources.tiktok.url && (
                        <a href={product.data_sources.tiktok.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline text-xs">
                          View →
                        </a>
                      )}
                    </div>
                  )}
                  {product.data_sources.amazon?.available && (
                    <div className="flex items-center justify-between p-2 bg-black/20 rounded-lg border border-white/10">
                      <div className="flex items-center gap-2">
                        <ShoppingBag className="w-4 h-4 text-[#FF9900]" />
                        <div>
                          <p className="text-sm font-medium text-gray-200">Amazon</p>
                          <p className="text-xs text-gray-400">Rank: {product.data_sources.amazon.sales_rank?.toLocaleString() || 'N/A'}</p>
                        </div>
                      </div>
                      {product.data_sources.amazon.url && (
                        <a href={product.data_sources.amazon.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline text-xs">
                          View →
                        </a>
                      )}
                    </div>
                  )}
                  {product.data_sources.google_trends?.available && (
                    <div className="flex items-center justify-between p-2 bg-black/20 rounded-lg border border-white/10">
                      <div className="flex items-center gap-2">
                        <Search className="w-4 h-4 text-[#4285F4]" />
                        <div>
                          <p className="text-sm font-medium text-gray-200">Google Trends</p>
                          <p className="text-xs text-gray-400">Score: {product.data_sources.google_trends.trend_score || 'N/A'}</p>
                        </div>
                      </div>
                    </div>
                  )}
                  {product.data_sources.aliexpress?.available && (
                    <div className="flex items-center justify-between p-2 bg-black/20 rounded-lg border border-white/10">
                      <div className="flex items-center gap-2">
                        <TrendingUp className="w-4 h-4 text-[#FF6A00]" />
                        <div>
                          <p className="text-sm font-medium text-gray-200">AliExpress</p>
                          <p className="text-xs text-gray-400">{product.data_sources.aliexpress.orders?.toLocaleString() || 'N/A'} orders</p>
                        </div>
                      </div>
                      {product.data_sources.aliexpress.url && (
                        <a href={product.data_sources.aliexpress.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline text-xs">
                          View →
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="text-xs text-gray-500 text-center">
              Source: {analysis.source} • {new Date(analysis.timestamp).toLocaleString()}
            </div>
          </div>
        )}

        {/* Product Chat */}
        <div className="mt-6 border-t border-white/10 pt-4">
          <h4 className="font-bold mb-2 text-gray-200">💬 Ask Claude About This Product</h4>
          <div className="space-y-2 max-h-60 overflow-y-auto mb-3 p-2 bg-black/20 rounded-lg border border-white/10">
            {chatMessages.map((msg, i) => (
              <div key={i} className={`p-3 rounded-lg ${
                msg.role === 'user'
                  ? 'bg-blue-500/30 text-right'
                  : 'bg-white/10'
              }`}>
                <div className="text-xs text-gray-400 mb-1">
                  {msg.role === 'user' ? 'You' : 'Claude AI'}
                </div>
                <div className="text-sm text-white">{msg.content}</div>
              </div>
            ))}
            {chatLoading && (
              <div className="p-3 rounded-lg bg-white/10">
                <div className="text-xs text-gray-400 mb-1">Claude AI</div>
                <div className="text-sm text-white">Thinking...</div>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Ask anything about this product..."
              className="flex-1 px-3 py-2 border border-white/20 bg-white/10 rounded-lg placeholder-gray-400"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendChatMessage()}
              disabled={chatLoading}
            />
            <button
              className="px-4 py-2 bg-blue-600/80 text-white rounded-lg hover:bg-blue-700/80 disabled:opacity-50 transition"
              onClick={sendChatMessage}
              disabled={chatLoading || !chatInput.trim()}
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
