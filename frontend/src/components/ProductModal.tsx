import { useState } from 'react';
import axios from 'axios';

interface ProductModalProps {
  product: {
    id: string;
    name: string;
    price: number;
    cost: number;
    velocity_score: number;
    niche: string;
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
        `http://127.0.0.1:8000/api/dashboard/v2/products/${product.id}/analyze`
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
      const response = await axios.post('http://127.0.0.1:8000/api/dashboard/v2/claude/chat', {
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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6">
        {/* Header */}
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-2xl font-bold text-gray-900">{product.name}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            ✕
          </button>
        </div>

        {/* Product Info */}
        <div className="grid grid-cols-2 gap-4 mb-6 p-4 bg-gray-50 rounded">
          <div>
            <div className="text-sm text-gray-600">Price</div>
            <div className="text-xl font-bold text-green-600">${product.price.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Cost</div>
            <div className="text-xl font-bold">${product.cost.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Velocity</div>
            <div className="text-xl font-bold text-blue-600">{product.velocity_score}/100</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Niche</div>
            <div className="text-xl font-bold">{product.niche.replace('_', ' ')}</div>
          </div>
        </div>

        {/* AI Analysis Button */}
        {!analysis && (
          <button
            onClick={analyzeProduct}
            disabled={loading}
            className="w-full py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg font-bold hover:from-blue-700 hover:to-purple-700 disabled:opacity-50"
          >
            {loading ? '🤖 Claude is analyzing...' : '🤖 Analyze with Claude AI'}
          </button>
        )}

        {/* AI Analysis Results */}
        {analysis && (
          <div className="space-y-4">
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-bold">Claude AI Analysis</h3>
                <span className={`px-3 py-1 rounded font-bold ${
                  analysis.recommendation === 'STRONG_BUY' ? 'bg-green-500 text-white' :
                  analysis.recommendation === 'BUY' ? 'bg-blue-500 text-white' :
                  analysis.recommendation === 'HOLD' ? 'bg-yellow-500 text-white' :
                  'bg-red-500 text-white'
                }`}>
                  {analysis.recommendation}
                </span>
              </div>
              <div className="text-2xl font-bold text-purple-600 mb-2">
                Score: {analysis.score}/10
              </div>
              <div className="text-sm text-gray-600 mb-2">
                Success Prediction: {analysis.success_prediction}
              </div>
            </div>

            {/* Reasoning */}
            {analysis.reasoning && analysis.reasoning.length > 0 && (
              <div>
                <h4 className="font-bold mb-2">💡 Marketing Pitches & Angles:</h4>
                <ul className="space-y-1">
                  {analysis.reasoning.map((reason: string, i: number) => (
                    <li key={i} className="text-sm text-gray-700">• {reason}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Risks */}
            {analysis.risks && analysis.risks.length > 0 && (
              <div>
                <h4 className="font-bold mb-2">⚠️ Risks to Consider:</h4>
                <ul className="space-y-1">
                  {analysis.risks.map((risk: string, i: number) => (
                    <li key={i} className="text-sm text-gray-700">• {risk}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Full Analysis */}
            <div className="mt-4 p-4 bg-gray-50 rounded text-sm text-gray-700 max-h-60 overflow-y-auto whitespace-pre-wrap">
              {analysis.analysis}
            </div>

            <div className="text-xs text-gray-500 text-center">
              Source: {analysis.source} • {new Date(analysis.timestamp).toLocaleString()}
            </div>
          </div>
        )}

        {/* Product Chat */}
        <div className="mt-6 border-t pt-4">
          <h4 className="font-bold mb-2">💬 Ask Claude About This Product</h4>
          <div className="space-y-2 max-h-60 overflow-y-auto mb-3">
            {chatMessages.map((msg, i) => (
              <div key={i} className={`p-2 rounded ${
                msg.role === 'user'
                  ? 'bg-blue-100 text-right'
                  : 'bg-gray-100'
              }`}>
                <div className="text-xs text-gray-600 mb-1">
                  {msg.role === 'user' ? 'You' : 'Claude AI'}
                </div>
                <div className="text-sm">{msg.content}</div>
              </div>
            ))}
            {chatLoading && (
              <div className="p-2 rounded bg-gray-100">
                <div className="text-xs text-gray-600 mb-1">Claude AI</div>
                <div className="text-sm">Thinking...</div>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Ask anything about this product..."
              className="flex-1 px-3 py-2 border rounded"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendChatMessage()}
              disabled={chatLoading}
            />
            <button
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
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
