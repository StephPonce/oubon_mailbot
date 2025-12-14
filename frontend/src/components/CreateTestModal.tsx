import React, { useState } from 'react';
import axios from 'axios';
import { X, DollarSign, FileText, Image as ImageIcon, ArrowRight, ArrowLeft } from 'lucide-react';

const API_BASE = 'http://localhost:8001';

interface CreateTestModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTestCreated: () => void;
}

type TestType = 'price' | 'title' | 'description' | 'image' | null;

export const CreateTestModal: React.FC<CreateTestModalProps> = ({ isOpen, onClose, onTestCreated }) => {
  const [step, setStep] = useState(1);
  const [testType, setTestType] = useState<TestType>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    productId: '',
    storeId: '1',
    testName: '',
    durationDays: 14,
    minSampleSize: 100,
    autoImplementWinner: false,

    // Price test fields
    currentPrice: '',
    testPrices: ['', ''],

    // Title test fields
    currentTitle: '',
    variantTitles: ['', ''],

    // Description test fields
    currentDescription: '',
    variantDescriptions: ['', ''],

    // Image test fields
    currentImageUrl: '',
    variantImageUrls: ['', '']
  });

  const resetForm = () => {
    setStep(1);
    setTestType(null);
    setError(null);
    setFormData({
      productId: '',
      storeId: '1',
      testName: '',
      durationDays: 14,
      minSampleSize: 100,
      autoImplementWinner: false,
      currentPrice: '',
      testPrices: ['', ''],
      currentTitle: '',
      variantTitles: ['', ''],
      currentDescription: '',
      variantDescriptions: ['', ''],
      currentImageUrl: '',
      variantImageUrls: ['', '']
    });
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleTestTypeSelect = (type: TestType) => {
    setTestType(type);
    setStep(2);
  };

  const addVariant = (field: 'testPrices' | 'variantTitles' | 'variantDescriptions' | 'variantImageUrls') => {
    setFormData(prev => ({
      ...prev,
      [field]: [...prev[field], '']
    }));
  };

  const removeVariant = (field: 'testPrices' | 'variantTitles' | 'variantDescriptions' | 'variantImageUrls', index: number) => {
    setFormData(prev => ({
      ...prev,
      [field]: prev[field].filter((_, i) => i !== index)
    }));
  };

  const updateVariant = (field: 'testPrices' | 'variantTitles' | 'variantDescriptions' | 'variantImageUrls', index: number, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: prev[field].map((v, i) => i === index ? value : v)
    }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);

    try {
      let endpoint = '';
      let payload: any = {
        product_id: formData.productId,
        store_id: formData.storeId,
        test_name: formData.testName || undefined,
        duration_days: formData.durationDays,
        min_sample_size: formData.minSampleSize,
        auto_implement_winner: formData.autoImplementWinner
      };

      switch (testType) {
        case 'price':
          endpoint = '/api/abtesting/tests/price';
          payload = {
            ...payload,
            current_price: parseFloat(formData.currentPrice),
            test_prices: formData.testPrices.filter(p => p).map(p => parseFloat(p))
          };
          break;

        case 'title':
          endpoint = '/api/abtesting/tests/title';
          payload = {
            ...payload,
            current_title: formData.currentTitle,
            variant_titles: formData.variantTitles.filter(t => t)
          };
          break;

        case 'description':
          endpoint = '/api/abtesting/tests/description';
          payload = {
            ...payload,
            current_description: formData.currentDescription,
            variant_descriptions: formData.variantDescriptions.filter(d => d)
          };
          break;

        case 'image':
          endpoint = '/api/abtesting/tests/image';
          payload = {
            ...payload,
            current_image_url: formData.currentImageUrl,
            variant_image_urls: formData.variantImageUrls.filter(u => u)
          };
          break;
      }

      await axios.post(`${API_BASE}${endpoint}`, payload);
      onTestCreated();
      handleClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create test');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-white/10 sticky top-0 bg-white flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-primary">
              {step === 1 ? 'Create A/B Test' : `Create ${testType} Test`}
            </h2>
            <p className="text-secondary mt-1">
              {step === 1 ? 'Choose a test type to get started' : 'Configure your test parameters'}
            </p>
          </div>
          <button onClick={handleClose} className="text-tertiary hover:text-secondary">
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-4 bg-red-500/10 border border-red-200 rounded-lg text-red-700">
              {error}
            </div>
          )}

          {step === 1 && (
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => handleTestTypeSelect('price')}
                className="p-6 border-2 border-white/10 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all text-left group"
              >
                <DollarSign className="w-10 h-10 text-purple-600 mb-3 group-hover:scale-110 transition-transform" />
                <h3 className="font-semibold text-primary text-lg mb-2">Price Test</h3>
                <p className="text-sm text-secondary">
                  Test different price points to maximize revenue and conversions
                </p>
              </button>

              <button
                onClick={() => handleTestTypeSelect('title')}
                className="p-6 border-2 border-white/10 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all text-left group"
              >
                <FileText className="w-10 h-10 text-purple-600 mb-3 group-hover:scale-110 transition-transform" />
                <h3 className="font-semibold text-primary text-lg mb-2">Title Test</h3>
                <p className="text-sm text-secondary">
                  Test product titles to improve click-through rates
                </p>
              </button>

              <button
                onClick={() => handleTestTypeSelect('description')}
                className="p-6 border-2 border-white/10 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all text-left group"
              >
                <FileText className="w-10 h-10 text-purple-600 mb-3 group-hover:scale-110 transition-transform" />
                <h3 className="font-semibold text-primary text-lg mb-2">Description Test</h3>
                <p className="text-sm text-secondary">
                  Test different descriptions to increase conversion rates
                </p>
              </button>

              <button
                onClick={() => handleTestTypeSelect('image')}
                className="p-6 border-2 border-white/10 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all text-left group"
              >
                <ImageIcon className="w-10 h-10 text-purple-600 mb-3 group-hover:scale-110 transition-transform" />
                <h3 className="font-semibold text-primary text-lg mb-2">Image Test</h3>
                <p className="text-sm text-secondary">
                  Test product images to boost visual appeal and sales
                </p>
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6">
              {/* Basic Settings */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-primary">Basic Settings</h3>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-secondary mb-1">
                      Product ID *
                    </label>
                    <input
                      type="text"
                      value={formData.productId}
                      onChange={(e) => setFormData(prev => ({ ...prev, productId: e.target.value }))}
                      className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      placeholder="product-123"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-secondary mb-1">
                      Store ID *
                    </label>
                    <input
                      type="text"
                      value={formData.storeId}
                      onChange={(e) => setFormData(prev => ({ ...prev, storeId: e.target.value }))}
                      className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-secondary mb-1">
                    Test Name (optional)
                  </label>
                  <input
                    type="text"
                    value={formData.testName}
                    onChange={(e) => setFormData(prev => ({ ...prev, testName: e.target.value }))}
                    className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    placeholder="Leave blank for auto-generated name"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-secondary mb-1">
                      Duration (days)
                    </label>
                    <input
                      type="number"
                      value={formData.durationDays}
                      onChange={(e) => setFormData(prev => ({ ...prev, durationDays: parseInt(e.target.value) }))}
                      className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      min="1"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-secondary mb-1">
                      Min Sample Size
                    </label>
                    <input
                      type="number"
                      value={formData.minSampleSize}
                      onChange={(e) => setFormData(prev => ({ ...prev, minSampleSize: parseInt(e.target.value) }))}
                      className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      min="10"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="autoImplement"
                    checked={formData.autoImplementWinner}
                    onChange={(e) => setFormData(prev => ({ ...prev, autoImplementWinner: e.target.checked }))}
                    className="w-4 h-4 text-purple-600 border-white/10 rounded focus:ring-purple-500"
                  />
                  <label htmlFor="autoImplement" className="text-sm text-secondary">
                    Auto-implement winner when test ends
                  </label>
                </div>
              </div>

              {/* Test-Specific Fields */}
              <div className="space-y-4 pt-6 border-t border-white/10">
                <h3 className="text-lg font-semibold text-primary">
                  {testType === 'price' && 'Price Variants'}
                  {testType === 'title' && 'Title Variants'}
                  {testType === 'description' && 'Description Variants'}
                  {testType === 'image' && 'Image Variants'}
                </h3>

                {testType === 'price' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-secondary mb-1">
                        Current Price (Control) *
                      </label>
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-tertiary">$</span>
                        <input
                          type="number"
                          step="0.01"
                          value={formData.currentPrice}
                          onChange={(e) => setFormData(prev => ({ ...prev, currentPrice: e.target.value }))}
                          className="w-full pl-8 pr-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                          placeholder="29.99"
                          required
                        />
                      </div>
                    </div>

                    {formData.testPrices.map((price, index) => (
                      <div key={index} className="flex gap-2">
                        <div className="flex-1 min-w-0">
                          <label className="block text-sm font-medium text-secondary mb-1">
                            Test Price {index + 1} *
                          </label>
                          <div className="relative">
                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-tertiary">$</span>
                            <input
                              type="number"
                              step="0.01"
                              value={price}
                              onChange={(e) => updateVariant('testPrices', index, e.target.value)}
                              className="w-full pl-8 pr-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                              placeholder="24.99"
                              required
                            />
                          </div>
                        </div>
                        {formData.testPrices.length > 1 && (
                          <button
                            onClick={() => removeVariant('testPrices', index)}
                            className="mt-7 px-3 py-2 text-red-600 hover:bg-red-500/10 rounded-lg"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    ))}

                    <button
                      onClick={() => addVariant('testPrices')}
                      className="w-full py-2 border-2 border-dashed border-white/10 rounded-lg text-secondary hover:border-purple-500 hover:text-purple-600 transition-colors"
                    >
                      + Add Another Price
                    </button>
                  </>
                )}

                {testType === 'title' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-secondary mb-1">
                        Current Title (Control) *
                      </label>
                      <input
                        type="text"
                        value={formData.currentTitle}
                        onChange={(e) => setFormData(prev => ({ ...prev, currentTitle: e.target.value }))}
                        className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                        placeholder="Smart Watch with Fitness Tracker"
                        required
                      />
                    </div>

                    {formData.variantTitles.map((title, index) => (
                      <div key={index} className="flex gap-2">
                        <div className="flex-1 min-w-0">
                          <label className="block text-sm font-medium text-secondary mb-1">
                            Variant Title {index + 1} *
                          </label>
                          <input
                            type="text"
                            value={title}
                            onChange={(e) => updateVariant('variantTitles', index, e.target.value)}
                            className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                            placeholder="Premium Fitness Smart Watch"
                            required
                          />
                        </div>
                        {formData.variantTitles.length > 1 && (
                          <button
                            onClick={() => removeVariant('variantTitles', index)}
                            className="mt-7 px-3 py-2 text-red-600 hover:bg-red-500/10 rounded-lg"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    ))}

                    <button
                      onClick={() => addVariant('variantTitles')}
                      className="w-full py-2 border-2 border-dashed border-white/10 rounded-lg text-secondary hover:border-purple-500 hover:text-purple-600 transition-colors"
                    >
                      + Add Another Title
                    </button>
                  </>
                )}

                {testType === 'description' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-secondary mb-1">
                        Current Description (Control) *
                      </label>
                      <textarea
                        value={formData.currentDescription}
                        onChange={(e) => setFormData(prev => ({ ...prev, currentDescription: e.target.value }))}
                        className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                        rows={4}
                        placeholder="Track your fitness goals with this advanced smart watch..."
                        required
                      />
                    </div>

                    {formData.variantDescriptions.map((description, index) => (
                      <div key={index} className="flex gap-2">
                        <div className="flex-1 min-w-0">
                          <label className="block text-sm font-medium text-secondary mb-1">
                            Variant Description {index + 1} *
                          </label>
                          <textarea
                            value={description}
                            onChange={(e) => updateVariant('variantDescriptions', index, e.target.value)}
                            className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                            rows={4}
                            placeholder="Experience ultimate fitness tracking..."
                            required
                          />
                        </div>
                        {formData.variantDescriptions.length > 1 && (
                          <button
                            onClick={() => removeVariant('variantDescriptions', index)}
                            className="mt-7 px-3 py-2 text-red-600 hover:bg-red-500/10 rounded-lg"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    ))}

                    <button
                      onClick={() => addVariant('variantDescriptions')}
                      className="w-full py-2 border-2 border-dashed border-white/10 rounded-lg text-secondary hover:border-purple-500 hover:text-purple-600 transition-colors"
                    >
                      + Add Another Description
                    </button>
                  </>
                )}

                {testType === 'image' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-secondary mb-1">
                        Current Image URL (Control) *
                      </label>
                      <input
                        type="url"
                        value={formData.currentImageUrl}
                        onChange={(e) => setFormData(prev => ({ ...prev, currentImageUrl: e.target.value }))}
                        className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                        placeholder="https://example.com/product-image-1.jpg"
                        required
                      />
                    </div>

                    {formData.variantImageUrls.map((url, index) => (
                      <div key={index} className="flex gap-2">
                        <div className="flex-1 min-w-0">
                          <label className="block text-sm font-medium text-secondary mb-1">
                            Variant Image URL {index + 1} *
                          </label>
                          <input
                            type="url"
                            value={url}
                            onChange={(e) => updateVariant('variantImageUrls', index, e.target.value)}
                            className="w-full px-3 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                            placeholder="https://example.com/product-image-2.jpg"
                            required
                          />
                        </div>
                        {formData.variantImageUrls.length > 1 && (
                          <button
                            onClick={() => removeVariant('variantImageUrls', index)}
                            className="mt-7 px-3 py-2 text-red-600 hover:bg-red-500/10 rounded-lg"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    ))}

                    <button
                      onClick={() => addVariant('variantImageUrls')}
                      className="w-full py-2 border-2 border-dashed border-white/10 rounded-lg text-secondary hover:border-purple-500 hover:text-purple-600 transition-colors"
                    >
                      + Add Another Image
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-white/10 sticky bottom-0 bg-white">
          <div className="flex justify-between gap-2">
            {step === 1 ? (
              <button
                onClick={handleClose}
                className="px-6 py-2 border border-white/10 rounded-lg hover:  transition-colors"
              >
                Cancel
              </button>
            ) : (
              <button
                onClick={() => setStep(1)}
                className="flex items-center gap-2 px-6 py-2 border border-white/10 rounded-lg hover:  transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
            )}

            {step === 2 && (
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="flex items-center gap-2 px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Creating...' : 'Create Test'}
                {!loading && <ArrowRight className="w-4 h-4" />}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
