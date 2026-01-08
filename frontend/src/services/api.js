/**
 * OSPRA INTELLIGENCE - API SERVICE (ENHANCED)
 * ============================================
 * 
 * Centralized API client for all Ospra endpoints.
 * Integrates with auth service for authenticated requests.
 * 
 * Enhanced with:
 * - Rich context Oi chat
 * - Interaction tracking
 * - Feedback submission
 * - Real-time alerts
 * - Alert actions
 * 
 * @author OspraOS
 * @date January 2025
 */

import { authService, API_BASE_URL } from './auth';

/**
 * Base API class with error handling
 */
class OspraAPI {
  
  // ===========================================================================
  // HEALTH & STATUS
  // ===========================================================================
  
  async getHealth() {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.json();
  }
  
  async getIntelligenceStatus() {
    const response = await fetch(`${API_BASE_URL}/debug/intelligence`);
    return response.json();
  }
  
  // ===========================================================================
  // OI CHAT - ENHANCED WITH FULL CONTEXT
  // ===========================================================================
  
  /**
   * Simple chat (backward compatible)
   */
  async chat(message, context = {}) {
    return authService.post('/api/oi/chat', { 
      message, 
      dashboard_context: context.dashboard_context || null,
      context_refresh: context.context_refresh || false,
      execute_actions: context.execute_actions !== false,
    });
  }
  
  /**
   * Chat with full dashboard context
   * This is the preferred method - gives Oi full visibility
   * 
   * @param {string} message - User's message
   * @param {object} options - Chat options
   * @param {object} options.dashboard_context - Full dashboard state
   * @param {string} options.conversation_id - Conversation ID for continuity
   * @param {boolean} options.execute_actions - Whether to execute detected actions
   * @param {boolean} options.context_refresh - Force refresh backend context
   */
  async chatWithContext(message, options = {}) {
    const payload = {
      message,
      dashboard_context: options.dashboard_context || null,
      conversation_id: options.conversation_id || null,
      execute_actions: options.execute_actions !== false,
      context_refresh: options.context_refresh || false,
    };
    
    return authService.post('/api/oi/chat', payload);
  }
  
  /**
   * Get Oi's current context (what it knows)
   */
  async getOiContext(refresh = false) {
    return authService.get('/api/oi/context', { refresh, include_insights: true });
  }
  
  /**
   * Get Oi's memory about the user
   */
  async getOiMemory() {
    return authService.get('/api/oi/memory');
  }
  
  /**
   * Clear Oi's memory
   */
  async clearOiMemory() {
    return authService.delete('/api/oi/memory');
  }
  
  /**
   * Get conversation summary
   */
  async getOiConversation() {
    return authService.get('/api/oi/conversation');
  }
  
  /**
   * Clear conversation history
   */
  async clearOiConversation() {
    return authService.post('/api/oi/conversation/clear');
  }
  
  // ===========================================================================
  // OI ALERTS - Real-time notifications from Oi
  // ===========================================================================
  
  /**
   * Get all alerts for the user
   * 
   * @param {object} filters - Optional filters
   * @param {string} filters.status - Filter by status: 'unread', 'read', 'all'
   * @param {string} filters.priority - Filter by priority: 'high', 'medium', 'low'
   * @param {string} filters.type - Filter by type: 'trending_product', 'price_drop', etc.
   * @param {number} filters.limit - Max alerts to return
   */
  async getOiAlerts(filters = {}) {
    return authService.get('/api/oi/alerts', filters);
  }
  
  /**
   * Mark an alert as read
   */
  async markAlertRead(alertId) {
    return authService.post(`/api/oi/alerts/${alertId}/read`);
  }
  
  /**
   * Mark all alerts as read
   */
  async markAllAlertsRead() {
    return authService.post('/api/oi/alerts/read-all');
  }
  
  /**
   * Dismiss/delete an alert
   */
  async dismissAlert(alertId) {
    return authService.delete(`/api/oi/alerts/${alertId}`);
  }
  
  /**
   * Execute an action from an alert
   * 
   * @param {string} alertId - Alert ID
   * @param {string} action - Action to execute (e.g., 'deploy', 'add_to_watchlist', 'approve')
   * @param {object} params - Additional action parameters
   */
  async executeAlertAction(alertId, action, params = {}) {
    return authService.post(`/api/oi/alerts/${alertId}/action`, {
      action,
      params,
    });
  }
  
  /**
   * Get alert preferences/settings
   */
  async getAlertPreferences() {
    return authService.get('/api/oi/alerts/preferences');
  }
  
  /**
   * Update alert preferences
   * 
   * @param {object} preferences - Alert settings
   * @param {boolean} preferences.enabled - Enable/disable alerts
   * @param {string[]} preferences.types - Alert types to receive
   * @param {string} preferences.min_priority - Minimum priority ('low', 'medium', 'high')
   * @param {boolean} preferences.email_notifications - Send email for high priority
   * @param {object} preferences.quiet_hours - Quiet hours settings
   */
  async updateAlertPreferences(preferences) {
    return authService.put('/api/oi/alerts/preferences', preferences);
  }
  
  // ===========================================================================
  // OI LEARNING & FEEDBACK
  // ===========================================================================
  
  /**
   * Track a user interaction for Oi's learning system
   * 
   * Types: page_view, product_view, product_select, product_deploy, 
   *        search, filter, oi_chat, action, feedback, alert_action
   * 
   * @param {object} interaction - Interaction data
   * @param {string} interaction.type - Type of interaction
   * @param {object} interaction.data - Interaction-specific data
   * @param {string} interaction.timestamp - ISO timestamp
   */
  async trackInteraction(interaction) {
    try {
      return await authService.post('/api/oi/learn', {
        timestamp: interaction.timestamp || new Date().toISOString(),
        type: interaction.type,
        data: interaction.data || {},
      });
    } catch (error) {
      // Silent fail - tracking is non-critical
      console.debug('Interaction tracking failed:', error);
      return { status: 'error' };
    }
  }
  
  /**
   * Submit feedback on an Oi response
   * 
   * @param {object} feedback - Feedback data
   * @param {string} feedback.message_id - ID of the message
   * @param {boolean} feedback.helpful - Was the response helpful?
   * @param {string} feedback.comment - Optional comment
   * @param {object} feedback.context - Dashboard context when feedback given
   */
  async submitOiFeedback(feedback) {
    return authService.post('/api/oi/feedback', {
      message_id: feedback.message_id,
      helpful: feedback.helpful,
      comment: feedback.comment || null,
      context: feedback.context || null,
    });
  }
  
  /**
   * Get personalized recommendations from Oi
   */
  async getOiRecommendations() {
    return authService.get('/api/oi/recommendations');
  }
  
  /**
   * Get user insights (learned patterns)
   */
  async getOiInsights() {
    return authService.get('/api/oi/insights');
  }
  
  // ===========================================================================
  // OI ACTIONS
  // ===========================================================================
  
  /**
   * Execute a quick action via Oi
   */
  async executeOiAction(action, params = {}, confirmed = false) {
    return authService.post('/api/oi/action', {
      action,
      params,
      confirmed,
    });
  }
  
  /**
   * List available Oi actions
   */
  async listOiActions() {
    const response = await fetch(`${API_BASE_URL}/api/oi/actions`);
    return response.json();
  }
  
  /**
   * Check Oi health status
   */
  async getOiHealth() {
    const response = await fetch(`${API_BASE_URL}/api/oi/health`);
    return response.json();
  }
  
  // ===========================================================================
  // NATURAL LANGUAGE PARSING
  // ===========================================================================
  
  async parseCommand(text, execute = false) {
    try {
      return await authService.post('/api/nl/parse', { text, execute });
    } catch {
      return { success: false, parsed: null };
    }
  }
  
  async quickParse(command) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/nl/quick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
      });
      return response.json();
    } catch {
      return { success: false };
    }
  }
  
  async getCommandExamples() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/nl/examples`);
      if (!response.ok) return { examples: [] };
      return response.json();
    } catch {
      return { examples: [] };
    }
  }
  
  // ===========================================================================
  // PRODUCT DISCOVERY - Using actual working endpoints
  // ===========================================================================
  
  /**
   * Quick product discovery by niche (WORKING)
   * Uses: GET /api/discovery/quick/{niche}?count=10&include_ai_images=true
   * 
   * @param {object} params - Discovery parameters
   * @param {string} params.niche - Product niche/category
   * @param {number} params.count - Number of products to fetch
   * @param {boolean} params.includeAiImages - Generate AI images for top products (~$0.04/image)
   */
  async discoverProducts(params = {}) {
    const niche = params.niche || 'smart_home';
    const count = params.count || params.limit || 10;
    const includeAiImages = params.includeAiImages !== false; // Enable AI images by default
    try {
      const url = `${API_BASE_URL}/api/discovery/quick/${niche}?count=${count}&include_ai_images=${includeAiImages}`;
      const response = await fetch(url);
      const data = await response.json();
      // Normalize response format
      return data.products || data.data || data || [];
    } catch (error) {
      console.error('discoverProducts error:', error);
      return [];
    }
  }
  
  /**
   * Enhance products with AI-generated images
   * POST /api/discovery/enhance-images
   * 
   * @param {array} products - Products to enhance
   * @param {number} maxImages - Max images to generate (default 5)
   */
  async enhanceProductsWithAiImages(products, maxImages = 5) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/discovery/enhance-images`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ products, max_images: maxImages })
      });
      const data = await response.json();
      return data.products || products;
    } catch (error) {
      console.error('enhanceProductsWithAiImages error:', error);
      return products;
    }
  }
  
  /**
   * Get product analysis
   */
  async getProductAnalysis(productId) {
    return authService.get(`/api/products/${productId}/analysis`);
  }
  
  /**
   * Get recommended products from database
   * Uses: GET /api/dashboard/v2/products
   */
  async getProductRecommendations(limit = 10) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/dashboard/v2/products?per_page=${limit}`);
      const data = await response.json();
      return data.products || data.data || data || [];
    } catch (error) {
      console.error('getProductRecommendations error:', error);
      return [];
    }
  }
  
  /**
   * Get trending products
   * Uses: GET /research/trending
   */
  async getTrendingProducts(niche = null) {
    try {
      // Try research endpoint first
      const url = niche 
        ? `${API_BASE_URL}/research/trending?limit=10`
        : `${API_BASE_URL}/research/trending?limit=10`;
      const response = await fetch(url);
      const data = await response.json();
      return data.products || data.trends || data.data || data || [];
    } catch (error) {
      console.error('getTrendingProducts error:', error);
      // Fallback to quick discovery
      return this.discoverProducts({ niche: niche || 'trending', count: 10 });
    }
  }
  
  /**
   * Search products across sources
   * Uses: POST /research/find-products
   */
  async searchProducts(query, sources = ['aliexpress', 'cj']) {
    try {
      const response = await fetch(`${API_BASE_URL}/research/find-products`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query, 
          sources,
          niche: query,
          limit: 20
        })
      });
      const data = await response.json();
      return data.products || data.data || data || [];
    } catch (error) {
      console.error('searchProducts error:', error);
      return [];
    }
  }
  
  /**
   * Get products from database with filters
   * Uses: GET /api/dashboard/v2/products
   */
  async getDatabaseProducts(params = {}) {
    try {
      const queryParams = new URLSearchParams();
      if (params.niche) queryParams.append('niche', params.niche);
      if (params.per_page) queryParams.append('per_page', params.per_page);
      if (params.page) queryParams.append('page', params.page);
      
      const response = await fetch(`${API_BASE_URL}/api/dashboard/v2/products?${queryParams}`);
      const data = await response.json();
      return data.products || data.data || data || [];
    } catch (error) {
      console.error('getDatabaseProducts error:', error);
      return [];
    }
  }
  
  /**
   * Get data sources status
   * Uses: GET /research/sources
   */
  async getDataSources() {
    try {
      const response = await fetch(`${API_BASE_URL}/research/sources`);
      return response.json();
    } catch (error) {
      console.error('getDataSources error:', error);
      return { sources: [] };
    }
  }
  
  // ===========================================================================
  // AUTOPILOT
  // ===========================================================================
  
  async getAutopilotStatus() {
    return authService.get('/api/autopilot/status');
  }
  
  async getAutopilotConfig() {
    return authService.get('/api/autopilot/config');
  }
  
  async enableAutopilot() {
    return authService.post('/api/autopilot/enable');
  }
  
  async disableAutopilot() {
    return authService.post('/api/autopilot/disable');
  }
  
  async pauseAutopilot() {
    return authService.post('/api/autopilot/pause');
  }
  
  async applyPreset(preset) {
    return authService.post(`/api/autopilot/presets/${preset}`);
  }
  
  async updateAutopilotConfig(config) {
    return authService.put('/api/autopilot/config', config);
  }
  
  async getAutopilotSummary() {
    return authService.get('/api/autopilot/summary');
  }
  
  async getAutopilotActions(limit = 10) {
    return authService.get('/api/autopilot/actions', { limit });
  }
  
  // ===========================================================================
  // AI ACTIONS
  // ===========================================================================
  
  async getPendingActions(filters = {}) {
    return authService.get('/api/ai/actions', filters);
  }
  
  async getActionStats() {
    return authService.get('/api/ai/actions/stats/summary');
  }
  
  async acceptAction(actionId) {
    return authService.post(`/api/ai/actions/${actionId}/accept`);
  }
  
  async declineAction(actionId, reason) {
    return authService.post(`/api/ai/actions/${actionId}/decline`, { reason });
  }
  
  async proposeAction(action) {
    return authService.post('/api/ai/actions/propose', action);
  }
  
  // ===========================================================================
  // AI IMAGE GENERATION
  // ===========================================================================
  
  /**
   * Generate AI product image for Oubon Shop aesthetic
   */
  async generateProductImage(productTitle, niche = 'smart_home', originalImageUrl = null) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/images/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_title: productTitle,
          niche: niche,
          original_image_url: originalImageUrl,
          tags: [niche],
          force_regenerate: false
        })
      });
      return response.json();
    } catch (error) {
      console.error('generateProductImage error:', error);
      return { success: false, ai_image_url: originalImageUrl };
    }
  }
  
  /**
   * Get AI image service status
   */
  async getImageServiceStatus() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/images/status`);
      return response.json();
    } catch (error) {
      return { available: false };
    }
  }
  
  // ===========================================================================
  // PRODUCT ANALYSIS (AI-powered)
  // ===========================================================================
  
  /**
   * Get full AI analysis for a product
   */
  async analyzeProduct(productData) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/products/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(productData)
      });
      return response.json();
    } catch (error) {
      console.error('analyzeProduct error:', error);
      return { success: false };
    }
  }
  
  /**
   * Generate SEO-optimized product caption
   */
  async generateCaption(productTitle, niche, price) {
    try {
      // Use dedicated caption endpoint
      const response = await fetch(`${API_BASE_URL}/api/oi/generate-caption`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_title: productTitle,
          product_niche: niche,
          price: parseFloat(price) || 0,
          tags: [niche]
        })
      });
      const data = await response.json();
      if (data.success && data.caption) {
        return { success: true, caption: data.caption };
      }
      // Fallback to chat if endpoint fails
      return this._generateCaptionViaChat(productTitle, niche, price);
    } catch (error) {
      console.error('generateCaption error:', error);
      return this._generateCaptionViaChat(productTitle, niche, price);
    }
  }

  async _generateCaptionViaChat(productTitle, niche, price) {
    try {
      const response = await this.chat(
        `Generate a professional, SEO-optimized Shopify product description for: "${productTitle}"

Requirements:
- For a smart home / home goods store called Oubon Shop
- Include 3-4 bullet points of key features
- Add emotional triggers and urgency
- Include relevant keywords for SEO
- Price: ${price}
- Keep it under 150 words
- Format with emojis for social media use
- End with a call to action

Return ONLY the caption, no explanations.`,
        { dashboard_context: { current_page: 'products', selected_product: { name: productTitle, niche: niche } } }
      );
      return {
        success: true,
        caption: response.message || response.response || this._fallbackCaption(productTitle, niche, price)
      };
    } catch (error) {
      return {
        success: false,
        caption: this._fallbackCaption(productTitle, niche, price)
      };
    }
  }

  _fallbackCaption(productTitle, niche, price) {
    // PROFESSIONAL fallback - NO emojis, NO hashtags
    // Matches Oubon Shop's premium brand positioning
    const cleanNiche = (niche || 'smart home').replace(/_/g, ' ');
    const cleanTitle = productTitle
      .replace(/\b(hot sale|new|2024|2025|premium|quality|best|cheap)\b/gi, '')
      .replace(/\s+/g, ' ')
      .trim();
    
    return `${cleanTitle}

Elevate your ${cleanNiche} experience with this thoughtfully designed essential. Built with quality materials and backed by our satisfaction guarantee.

Free shipping on orders over $50. 30-day hassle-free returns.

Price: ${parseFloat(price).toFixed(2)}`;
  }
  
  // ===========================================================================
  // DEPLOYMENT
  // ===========================================================================
  
  async deployProduct(productId, options = {}) {
    return authService.post('/api/deploy/product', { product_id: productId, ...options });
  }
  
  async bulkDeploy(productIds, options = {}) {
    return authService.post('/api/deploy/bulk', { product_ids: productIds, ...options });
  }
  
  async getDeploymentStatus(deploymentId) {
    return authService.get(`/api/deploy/${deploymentId}/status`);
  }
  
  // ===========================================================================
  // TRENDS & ANALYTICS
  // ===========================================================================
  
  async getEcommerceTrends() {
    return authService.get('/api/trends/ecommerce');
  }
  
  async getNicheTrends(niche) {
    return authService.get('/api/trends/niche', { niche });
  }
  
  async getMarketAnalysis(productId) {
    return authService.get(`/api/analysis/market/${productId}`);
  }
  
  // ===========================================================================
  // RATE LIMITS & USAGE
  // ===========================================================================
  
  async getRateLimitStatus() {
    const tier = authService.getTier();
    const response = await fetch(
      `${API_BASE_URL}/api/rate-limit/discovery/status?tier=${tier}`
    );
    return response.json();
  }
  
  async getUsageDashboard() {
    return authService.get('/api/usage/dashboard');
  }
  
  // ===========================================================================
  // STORES
  // ===========================================================================
  
  async getConnectedStores() {
    return authService.get('/api/stores');
  }
  
  async connectShopifyStore(shopDomain) {
    return authService.post('/api/stores/shopify/connect', { shop_domain: shopDomain });
  }
  
  async getStoreStatus(storeId) {
    return authService.get(`/api/stores/${storeId}/status`);
  }
  
  // ===========================================================================
  // USER PROFILE & SETTINGS
  // ===========================================================================
  
  async getProfile() {
    return authService.get('/api/user/profile');
  }
  
  async updateProfile(data) {
    const response = await authService.fetch('/api/user/profile', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
    return response.json();
  }
  
  async getSettings() {
    return authService.get('/api/user/settings');
  }
  
  async updateSettings(settings) {
    const response = await authService.fetch('/api/user/settings', {
      method: 'PATCH',
      body: JSON.stringify(settings),
    });
    return response.json();
  }
  
  async upgradeTier(tier) {
    return authService.post('/api/user/upgrade', { tier });
  }
  
  async getTierInfo() {
    return authService.get('/api/user/tier');
  }
}

// Singleton export
export const api = new OspraAPI();

export default api;
