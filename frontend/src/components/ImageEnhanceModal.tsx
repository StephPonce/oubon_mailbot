import { useState } from 'react';
import {
  X,
  Sparkles,
  Loader2,
  Check,
  ArrowLeftRight,
  DollarSign,
  Info,
  Download,
} from 'lucide-react';

interface ImageEnhanceModalProps {
  product: {
    id: string;
    name: string;
    image_url?: string;
  };
  onClose: () => void;
  onUseEnhanced?: (enhancedUrl: string) => void;
}

export const ImageEnhanceModal: React.FC<ImageEnhanceModalProps> = ({
  product,
  onClose,
  onUseEnhanced,
}) => {
  const [loading, setLoading] = useState(false);
  const [enhancedUrl, setEnhancedUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showComparison, setShowComparison] = useState<'original' | 'enhanced' | 'split'>('split');
  const [processingTime, setProcessingTime] = useState<number | null>(null);

  const ENHANCEMENT_COST = 0.08; // $0.08 per image

  const handleEnhance = async () => {
    if (!product.image_url) {
      setError('No image available to enhance');
      return;
    }

    setLoading(true);
    setError(null);
    const startTime = Date.now();

    try {
      const response = await fetch('http://localhost:8001/api/images/enhance-product', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          product_id: product.id,
          image_url: product.image_url,
        }),
      });

      if (!response.ok) {
        throw new Error('Enhancement failed');
      }

      const data = await response.json();

      if (data.enhanced_url) {
        setEnhancedUrl(data.enhanced_url);
        setProcessingTime((Date.now() - startTime) / 1000);
      } else {
        throw new Error('No enhanced image returned');
      }
    } catch (err: any) {
      console.error('Enhancement failed:', err);
      setError(err.message || 'Failed to enhance image. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleUseEnhanced = () => {
    if (enhancedUrl && onUseEnhanced) {
      onUseEnhanced(enhancedUrl);
      onClose();
    }
  };

  const handleDownload = async (url: string, filename: string) => {
    try {
      const response = await fetch(url);
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white/95 backdrop-blur-xl rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-y-auto border border-white/20">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-white/10">
          <div>
            <h2 className="text-2xl font-bold text-primary flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-purple-600" />
              AI Image Enhancement
            </h2>
            <p className="text-tertiary mt-1 text-sm">
              Remove background and enhance product image with AI
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
          >
            <X className="w-5 h-5 text-tertiary" />
          </button>
        </div>

        {/* Product Info */}
        <div className="p-6 border-b border-white/10 bg-gradient-to-r from-purple-50 to-indigo-50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white rounded-lg shadow-sm">
              <Sparkles className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="font-medium text-primary">{product.name}</p>
              <p className="text-sm text-secondary">Product ID: {product.id}</p>
            </div>
          </div>
        </div>

        {/* Cost Info Banner */}
        <div className="p-4 bg-cyan-500/10 border-b border-blue-100">
          <div className="flex items-center gap-3">
            <DollarSign className="w-5 h-5 text-blue-600" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-blue-900">
                Enhancement Cost: ${ENHANCEMENT_COST.toFixed(2)}
              </p>
              <p className="text-xs text-cyan-400 mt-0.5">
                Powered by DALL-E 3 + rembg background removal
              </p>
            </div>
            {processingTime && (
              <div className="text-right">
                <p className="text-sm font-medium text-blue-900">
                  {processingTime.toFixed(1)}s
                </p>
                <p className="text-xs text-cyan-400">Processing time</p>
              </div>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="p-6">
          {!enhancedUrl && !loading && (
            <div className="text-center py-12">
              <div className="w-32 h-32 rounded-2xl bg-gradient-to-br from-purple-100 to-indigo-100 flex items-center justify-center mx-auto mb-6">
                {product.image_url ? (
                  <img
                    src={product.image_url}
                    alt={product.name}
                    className="w-full h-full object-cover rounded-2xl"
                  />
                ) : (
                  <Sparkles className="w-16 h-16 text-purple-600" />
                )}
              </div>

              <h3 className="text-lg font-semibold text-primary mb-2">
                Ready to enhance your product image?
              </h3>
              <p className="text-secondary mb-6 max-w-md mx-auto">
                Our AI will remove the background and enhance the image quality
                for better product presentation.
              </p>

              {product.image_url && (
                <button
                  onClick={handleEnhance}
                  className="px-6 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:opacity-90 transition flex items-center gap-2 mx-auto shadow-lg shadow-purple-500/25"
                >
                  <Sparkles className="w-5 h-5" />
                  Enhance Image - ${ENHANCEMENT_COST.toFixed(2)}
                </button>
              )}

              {!product.image_url && (
                <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg max-w-md mx-auto">
                  <p className="text-sm text-amber-300 flex items-center gap-2">
                    <Info className="w-4 h-4" />
                    No image available for this product
                  </p>
                </div>
              )}
            </div>
          )}

          {loading && (
            <div className="text-center py-16">
              <Loader2 className="w-16 h-16 animate-spin text-purple-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-primary mb-2">
                Enhancing your image...
              </h3>
              <p className="text-secondary">
                This may take a few seconds. Our AI is working its magic!
              </p>
              <div className="mt-6 max-w-md mx-auto">
                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-purple-600 to-indigo-600 rounded-full animate-pulse w-2/3"></div>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-200 rounded-lg mb-6">
              <p className="text-sm text-red-800 flex items-center gap-2">
                <X className="w-4 h-4" />
                {error}
              </p>
            </div>
          )}

          {enhancedUrl && product.image_url && (
            <div className="space-y-6">
              {/* View Toggle */}
              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={() => setShowComparison('original')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                    showComparison === 'original'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-100 text-secondary hover:bg-gray-200'
                  }`}
                >
                  Original
                </button>
                <button
                  onClick={() => setShowComparison('split')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2 ${
                    showComparison === 'split'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-100 text-secondary hover:bg-gray-200'
                  }`}
                >
                  <ArrowLeftRight className="w-4 h-4" />
                  Compare
                </button>
                <button
                  onClick={() => setShowComparison('enhanced')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition flex items-center gap-2 ${
                    showComparison === 'enhanced'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-100 text-secondary hover:bg-gray-200'
                  }`}
                >
                  <Sparkles className="w-4 h-4" />
                  Enhanced
                </button>
              </div>

              {/* Image Comparison */}
              <div className="relative rounded-xl overflow-hidden bg-gradient-to-br from-gray-50 to-gray-100 p-8">
                {showComparison === 'split' && (
                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-3">
                      <p className="text-sm font-medium text-secondary text-center">
                        Original
                      </p>
                      <div className="aspect-square bg-white rounded-lg shadow-md overflow-hidden border-2 border-white/10">
                        <img
                          src={product.image_url}
                          alt="Original"
                          className="w-full h-full object-contain"
                        />
                      </div>
                      <button
                        onClick={() => handleDownload(product.image_url!, `${product.id}-original.jpg`)}
                        className="w-full px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium text-secondary flex items-center justify-center gap-2 transition"
                      >
                        <Download className="w-4 h-4" />
                        Download
                      </button>
                    </div>
                    <div className="space-y-3">
                      <p className="text-sm font-medium text-purple-700 text-center flex items-center justify-center gap-1">
                        <Sparkles className="w-4 h-4" />
                        Enhanced
                      </p>
                      <div className="aspect-square bg-white rounded-lg shadow-md overflow-hidden border-2 border-purple-300">
                        <img
                          src={enhancedUrl}
                          alt="Enhanced"
                          className="w-full h-full object-contain"
                        />
                      </div>
                      <button
                        onClick={() => handleDownload(enhancedUrl, `${product.id}-enhanced.png`)}
                        className="w-full px-3 py-2 bg-purple-100 hover:bg-purple-200 rounded-lg text-sm font-medium text-purple-700 flex items-center justify-center gap-2 transition"
                      >
                        <Download className="w-4 h-4" />
                        Download
                      </button>
                    </div>
                  </div>
                )}

                {showComparison === 'original' && (
                  <div className="max-w-2xl mx-auto">
                    <p className="text-sm font-medium text-secondary text-center mb-3">
                      Original Image
                    </p>
                    <div className="aspect-square bg-white rounded-lg shadow-md overflow-hidden border-2 border-white/10">
                      <img
                        src={product.image_url}
                        alt="Original"
                        className="w-full h-full object-contain"
                      />
                    </div>
                  </div>
                )}

                {showComparison === 'enhanced' && (
                  <div className="max-w-2xl mx-auto">
                    <p className="text-sm font-medium text-purple-700 text-center mb-3 flex items-center justify-center gap-1">
                      <Sparkles className="w-4 h-4" />
                      Enhanced Image
                    </p>
                    <div className="aspect-square bg-white rounded-lg shadow-md overflow-hidden border-2 border-purple-300">
                      <img
                        src={enhancedUrl}
                        alt="Enhanced"
                        className="w-full h-full object-contain"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Enhancement Details */}
              <div className="bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg p-4 border border-purple-100">
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-sm text-secondary">Background</p>
                    <p className="text-lg font-semibold text-purple-600">Removed</p>
                  </div>
                  <div>
                    <p className="text-sm text-secondary">Quality</p>
                    <p className="text-lg font-semibold text-purple-600">Enhanced</p>
                  </div>
                  <div>
                    <p className="text-sm text-secondary">Format</p>
                    <p className="text-lg font-semibold text-purple-600">PNG</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        {enhancedUrl && (
          <div className="flex items-center justify-between p-6 border-t border-white/10  ">
            <button
              onClick={onClose}
              className="px-5 py-2.5 border border-white/10 rounded-lg hover:  transition font-medium text-secondary"
            >
              Keep Original
            </button>
            <button
              onClick={handleUseEnhanced}
              className="px-6 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:opacity-90 transition flex items-center gap-2 font-medium shadow-lg shadow-purple-500/25"
            >
              <Check className="w-5 h-5" />
              Use Enhanced Image
            </button>
          </div>
        )}

        {!enhancedUrl && !loading && (
          <div className="flex items-center justify-end p-6 border-t border-white/10  ">
            <button
              onClick={onClose}
              className="px-5 py-2.5 border border-white/10 rounded-lg hover:  transition font-medium text-secondary"
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageEnhanceModal;
