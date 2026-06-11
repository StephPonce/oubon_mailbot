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
 * In-flight request deduplication map.
 * Keyed by full request URL. If a call is already in-flight for a URL,
 * new callers receive the same promise instead of firing a duplicate request.
 *
 * Currently used by discoverProducts — discovery is the slowest endpoint
 * (multi-source parallel fetch) and users frequently double-click Retry or
 * rapidly switch niches, triggering 3x concurrent hammering and rate-limit
 * cascades on CJ/Apify.
 */
const _inflightDiscovery = new Map();

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
   * Uses: GET /api/discovery/quick/{niche}?count=10&include_ai_images=true&include_sentiment=true
   *
   * @param {object} params - Discovery parameters
   * @param {string} params.niche - Product niche/category
   * @param {number} params.count - Number of products to fetch
   * @param {boolean} params.includeAiImages - Generate AI images for top products (~$0.04/image)
   * @param {boolean} params.includeSentiment - Enrich with X/Twitter + Reddit sentiment
   *   (adds up to ~6s first load; powers sentiment_score and source badges).
   *   Default true. Cached results carry the sentiment flag so subsequent loads are fast.
   */
  async discoverProducts(params = {}) {
    const niche = params.niche || 'smart_home';
    // Backend hard cap is 100 (le=100 in /api/discovery/quick). The actual
    // per-tier ceiling (10 NEST → 100 STRATO) is enforced server-side in
    // unified_discovery_routes._tier_from_payload + clamp_request_count, so
    // we just send what the caller asks for and let the backend clamp + tag
    // tier_meta.clamped on the response. Sending more than the user's tier
    // allows is harmless — the backend trims and we surface the upgrade nudge.
    const count = Math.min(params.count || params.limit || 20, 100);
    // AI image generation is MANUAL CLICK ONLY (per CLAUDE.md standing rule).
    // Stability AI ~$0.06 per image; running it on every cold discovery
    // call was burning budget AND making the call too slow for the browser.
    // Default OFF; user clicks "Enhance" per product to invoke. Caller can
    // still pass includeAiImages=true explicitly if needed (e.g. tests).
    const includeAiImages = params.includeAiImages === true;
    const includeSentiment = params.includeSentiment !== false; // sentiment ON — fast + cheap
    // Captions are LAZY-LOADED. Reason: caption generation hits Claude
    // ~10x in series under rate-limit, adding 6-12s to every cold load.
    // The dashboard doesn't render captions on the card until the user
    // expands the product, so we don't need them on first paint.
    // Callers that DO want them eagerly can pass includeCaptions: true.
    // When false here, the backend skips caption generation entirely;
    // the product card lazy-fetches per-product via generateCaption()
    // when the user opens the detail panel.
    const includeCaptions = params.includeCaptions === true;
    const url = `${API_BASE_URL}/api/discovery/quick/${niche}?count=${count}&include_ai_images=${includeAiImages}&include_sentiment=${includeSentiment}&include_captions=${includeCaptions}`;

    // ---------- REQUEST DEDUPLICATION ----------
    // If an identical request is already in-flight, return the same promise
    // instead of firing a duplicate. Prevents the 3x concurrent hammering we
    // saw in the uvicorn logs (Retry clicks + rapid niche switches).
    if (_inflightDiscovery.has(url)) {
      console.log('[API] discoverProducts DEDUP — reusing in-flight request:', url);
      return _inflightDiscovery.get(url);
    }

    const promise = (async () => {
      try {
        console.log('[API] discoverProducts URL:', url);
        // Use authService.fetch so the Bearer token is attached automatically.
        // Without auth the backend treats us as anonymous (current_user=None
        // in unified_discovery_routes) and defaults the tier to NEST, capping
        // every Stratosphere user at 10 products. Discovered the hard way.
        // authService.fetch also handles token refresh + 401 redirect.
        const response = await authService.fetch(url);

        if (!response.ok) {
          // Backend returns 503 with detailed diagnostics when no real products available.
          let errorBody = null;
          try {
            errorBody = await response.json();
          } catch (_) {
            errorBody = { error: `HTTP ${response.status} ${response.statusText}` };
          }
          console.error('[API] discoverProducts HTTP error:', response.status, errorBody);

          // Return structured error so UI can display real reason instead of silent empty.
          return {
            __error: true,
            status: response.status,
            error: errorBody?.detail?.error || errorBody?.error || `HTTP ${response.status}`,
            discovery_error: errorBody?.detail?.discovery_error,
            diagnostics: errorBody?.detail?.diagnostics,
            hint: errorBody?.detail?.hint,
            products: []
          };
        }

        const data = await response.json();
        console.log('[API] discoverProducts response:', {
          success: data.success,
          count: data.count,
          from_cache: data.from_cache,
          is_fallback: data.is_fallback,
          tier_meta: data.tier_meta,
          products_length: (data.products || data.data || []).length
        });

        // If backend used ALLOW_DEMO_FALLBACK (dev mode), pass the warning through.
        if (data.is_fallback) {
          console.warn('[API] Backend returned demo products (dev fallback):', data.warning);
        }

        // Surface tier clamp events so upgrade nudges in the UI don't require
        // another round-trip. data.tier_meta is {tier, per_request_ceiling,
        // requested, clamped} when the backend applied a per-request ceiling.
        if (data.tier_meta?.clamped) {
          console.info(
            `[API] Tier clamp: requested ${data.tier_meta.requested} products, ` +
            `${data.tier_meta.tier} tier caps at ${data.tier_meta.per_request_ceiling}`
          );
        }

        // Normalize: return an array on success with `tier_meta` attached as a
        // non-enumerable property so callers that iterate don't see it, but the
        // discovery UI can still read `result.tier_meta` for upgrade nudges.
        const products = data.products || data.data || [];
        if (data.tier_meta) {
          Object.defineProperty(products, 'tier_meta', {
            value: data.tier_meta,
            enumerable: false,
            writable: false,
          });
        }
        return products;
      } catch (error) {
        console.error('[API] discoverProducts network error:', error);
        return {
          __error: true,
          status: 0,
          error: error.message || 'Network error reaching discovery API',
          hint: 'Backend may be down. Check that uvicorn is running on the configured port.',
          products: []
        };
      } finally {
        // Release the dedup slot whether success or failure, so the NEXT
        // retry/niche switch triggers a fresh request.
        _inflightDiscovery.delete(url);
      }
    })();

    _inflightDiscovery.set(url, promise);
    return promise;
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
      // authService.post auto-attaches Bearer + handles refresh/401
      // (image enhancement spends Stability budget — must be authenticated)
      return await authService.post('/api/discovery/enhance-images', {
        products,
        max_images: maxImages,
      }).then(data => data.products || products);
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
    // /api/dashboard/v2/products requires auth — was 401-ing because the
    // bare fetch sent no Bearer token. Same root cause as discoverProducts.
    // Errors propagate (task #51b): swallowing them as [] made outages look
    // like "no products". Background callers that want silence add .catch().
    const data = await authService.get('/api/dashboard/v2/products', { per_page: limit });
    return data.products || data.data || data || [];
  }
  
  /**
   * Get trending products
   * Uses: GET /research/trending
   */
  async getTrendingProducts(niche = null) {
    try {
      // Try research endpoint first
      const response = await fetch(`${API_BASE_URL}/research/trending?limit=10`);
      const data = await response.json();
      return data.products || data.trends || data.data || data || [];
    } catch (error) {
      console.error('getTrendingProducts error, falling back to discovery:', error);
      // Fallback to quick discovery; if that also fails, the error propagates
      // to the caller (task #51b) instead of masquerading as an empty list.
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
      throw error; // surface to the caller (task #51b)
    }
  }
  
  /**
   * Get products from database with filters
   * Uses: GET /api/dashboard/v2/products
   */
  async getDatabaseProducts(params = {}) {
    try {
      // Authenticated route — see getProductRecommendations comment above.
      const cleaned = {};
      if (params.niche) cleaned.niche = params.niche;
      if (params.per_page) cleaned.per_page = params.per_page;
      if (params.page) cleaned.page = params.page;
      const data = await authService.get('/api/dashboard/v2/products', cleaned);
      return data.products || data.data || data || [];
    } catch (error) {
      console.error('getDatabaseProducts error:', error);
      throw error; // surface to the caller (task #51b)
    }
  }
  
  /**
   * Get data sources status
   * Uses: GET /research/sources
   */
  async getDataSources() {
    const response = await fetch(`${API_BASE_URL}/research/sources`);
    return response.json();
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
  // Backend mounts the actions router at `/api/actions/*` (see
  // ospra_os/api/actions_routes.py:42). Frontend was previously calling
  // `/api/ai/actions/*` — a stale prefix from an earlier iteration that
  // 404-spammed the console for days. Action verbs were also misaligned
  // (accept→approve, decline→skip, propose→POST /api/actions).

  async getPendingActions(filters = {}) {
    return authService.get('/api/actions', filters);
  }

  async getActionStats() {
    return authService.get('/api/actions/stats');
  }

  async acceptAction(actionId) {
    return authService.post(`/api/actions/${actionId}/approve`);
  }

  async declineAction(actionId, reason) {
    return authService.post(`/api/actions/${actionId}/skip`, { reason });
  }

  async proposeAction(action) {
    // Backend uses POST /api/actions to create new actions (not /propose).
    return authService.post('/api/actions', action);
  }
  
  // ===========================================================================
  // AI IMAGE GENERATION & ENHANCEMENT
  // ===========================================================================

  /**
   * Enhance a single product image (background removal + clean background)
   * Uses Stability AI - AUTHENTICATED endpoint
   *
   * @param {string} imageUrl - URL of the product image
   * @param {string} niche - Product category for background selection
   * @param {string} backgroundStyle - Optional override (clean_white, soft_gray, etc.)
   * @returns {object} { success, enhanced_image_url, error, ... }
   */
  async enhanceImage(imageUrl, niche = 'smart_home', backgroundStyle = null, productId = null) {
    try {
      const result = await authService.post('/api/images/enhance', {
        image_url: String(imageUrl || ''),
        niche: String(niche || 'smart_home'),
        background_style: backgroundStyle ? String(backgroundStyle) : null,
        add_shadow: true,
        product_id: productId ? String(productId) : null
      });
      return result;
    } catch (error) {
      console.error('enhanceImage error:', error);
      // Safely extract error message to avoid circular reference issues
      const errorMsg = typeof error === 'string' ? error :
                       (error?.message || String(error) || 'Enhancement failed');
      return { success: false, error: errorMsg };
    }
  }

  /**
   * Get cached enhanced images for a product
   * Returns cached URLs if product was previously enhanced
   */
  async getCachedEnhancedImages(productId) {
    try {
      const result = await authService.get(`/api/images/cached/${productId}`);
      return result;
    } catch (error) {
      console.error('getCachedEnhancedImages error:', error);
      return { success: false, cached: false, enhanced_urls: [] };
    }
  }

  /**
   * Check which images are cached on disk (pre-flight cache check)
   * Use this before batch enhancement to avoid unnecessary API calls
   *
   * @param {array} imageUrls - Array of image URLs to check
   * @returns {object} { cached: {url: cachedUrl}, not_cached: [urls], cached_count: n }
   */
  async checkImageCache(imageUrls) {
    try {
      const result = await authService.post('/api/images/check-cache', {
        image_urls: imageUrls.map(url => String(url || ''))
      });
      return result;
    } catch (error) {
      console.error('checkImageCache error:', error);
      return { cached: {}, not_cached: imageUrls, cached_count: 0 };
    }
  }

  /**
   * Smart cache recovery - try to match URLs to existing cached files
   * Uses multiple hash variants to find matches even when URLs have changed
   *
   * @param {array} imageUrls - Array of image URLs to check
   * @param {string} productId - Product ID to associate matches with
   * @returns {object} { matches: [...], no_match: [...] }
   */
  async smartCacheRecovery(imageUrls, productId = null) {
    try {
      const result = await authService.post('/api/images/smart-cache-recovery', {
        image_urls: imageUrls.map(url => String(url || '')),
        product_id: productId ? String(productId) : null
      });
      return result;
    } catch (error) {
      console.error('smartCacheRecovery error:', error);
      return { success: false, matches: [], no_match: imageUrls };
    }
  }

  /**
   * Enhance multiple product images in batch
   * Processes up to 20 images concurrently - AUTHENTICATED endpoint
   *
   * @param {array} images - Array of { url, id?, title?, niche? }
   * @param {string} defaultNiche - Default niche for all images
   * @param {number} maxConcurrent - Max parallel requests (1-5)
   * @returns {object} { total, successful, failed, results: [...] }
   */
  async enhanceBatchImages(images, defaultNiche = 'smart_home', maxConcurrent = 3) {
    try {
      const result = await authService.post('/api/images/enhance/batch', {
        images: images.map(img => ({
          url: typeof img === 'string' ? img : (img.url || img.image_url),
          id: img.id || null,
          title: img.title || null,
          niche: img.niche || defaultNiche
        })),
        niche: defaultNiche,
        max_concurrent: Math.min(Math.max(maxConcurrent, 1), 5)
      });
      return result;
    } catch (error) {
      console.error('enhanceBatchImages error:', error);
      // Safely extract error message to avoid circular reference issues
      const errorMsg = typeof error === 'string' ? error :
                       (error?.message || String(error) || 'Batch enhancement failed');
      return {
        total: images.length,
        successful: 0,
        failed: images.length,
        results: images.map(img => ({
          success: false,
          error: errorMsg,
          original_url: typeof img === 'string' ? img : (img.url || img.image_url)
        }))
      };
    }
  }

  /**
   * Generate AI product image for Oubon Shop aesthetic (legacy)
   */
  async generateProductImage(productTitle, niche = 'smart_home', originalImageUrl = null) {
    try {
      // Authenticated — image generation spends Stability budget per call.
      return await authService.post('/api/images/generate', {
        product_title: productTitle,
        niche,
        original_image_url: originalImageUrl,
        tags: [niche],
        force_regenerate: false,
      });
    } catch (error) {
      console.error('generateProductImage error:', error);
      return { success: false, ai_image_url: originalImageUrl };
    }
  }

  /**
   * Get AI image service status (checks if Stability API key is configured)
   */
  async getImageServiceStatus() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/images/status`);
      return response.json();
    } catch (error) {
      return { available: false };
    }
  }

  /**
   * Get available background styles for image enhancement
   */
  async getBackgroundStyles() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/images/backgrounds`);
      return response.json();
    } catch (error) {
      return { styles: {}, niche_defaults: {} };
    }
  }
  
  // ===========================================================================
  // PRODUCT ANALYSIS (AI-powered)
  // ===========================================================================
  
  /**
   * Get full AI analysis for a product.
   * Calls POST /api/oi/analyze-product (requires auth).
   *
   * @param {object} product - The product object from discovery
   * @returns {Promise<{success: boolean, analysis?: object, source?: string, error?: string}>}
   */
  async analyzeProduct(product, forceRefresh = false) {
    try {
      const data = await authService.post('/api/oi/analyze-product', {
        product_id: product.id,
        product_title: product.title,
        // Bypass the backend's 15-min in-memory cache when the user
        // explicitly clicks Refresh. Auto-loads on panel-open leave
        // forceRefresh=false so they keep hitting the cache.
        force_refresh: forceRefresh === true,
        product_data: {
          niche: product.niche,
          cost_price: product.cost_price,
          suggested_price: product.suggested_price,
          profit: product.profit,
          oi_score: product.oi_score,
          demand_score: product.demand_score,
          trend_score: product.trend_score,
          sentiment_score: product.sentiment_score,
          sales_count: product.sales_count,
          rating: product.rating,
          source: product.source,
          data_sources: product.data_sources,
          scores_estimated: product.scores_estimated,
        }
      });
      return data;
    } catch (error) {
      console.error('[API] analyzeProduct error:', error);
      return { success: false, error: error.message || 'Analysis failed' };
    }
  }

  /**
   * Fetch verbatim Amazon review TEXT for a single product (Phase K
   * on-demand). Server-side cache is keyed by ASIN with a 24h TTL, so
   * repeated calls on the same listing within a day reuse one Apify
   * fetch (and don't re-bill).
   *
   * Pass the full discovery product dict — the route reads
   * ``amazon_evidence.top_matches[0]`` to find the ASIN. Response
   * shape:
   *   { success, available, asin?, review_count_returned?,
   *     average_rating?, verified_share?, reviews?: [...], cached?,
   *     reason?: 'no_amazon_match' | 'amazon_review_text_connector_unavailable' | ... }
   *
   * Frontend should render a clean "no Amazon reviews available" state
   * when ``available`` is false. The ``cached`` flag is purely
   * informational (useful for a small "served from cache" hint).
   */
  async fetchAmazonReviewText(product, maxReviews = 15) {
    try {
      // Send only the fields the route actually reads so we don't push
      // megabytes of payload up the wire on click.
      const data = await authService.post('/api/oi/amazon-reviews', {
        product_data: {
          title: product.title,
          name: product.name,
          amazon_evidence: product.amazon_evidence,
        },
        max_reviews: maxReviews,
      });
      return data;
    } catch (error) {
      console.error('[API] fetchAmazonReviewText error:', error);
      return { success: false, available: false, error: error.message || 'Fetch failed' };
    }
  }

  // ---------------------------------------------------------------------------
  // Shopify OAuth (store connection)
  // ---------------------------------------------------------------------------

  /**
   * Kick off Shopify OAuth for a shop domain. Returns
   * { authorization_url, shop_domain, state }. Caller should redirect
   * `window.location` to the authorization_url.
   *
   * Pass either `mystore` or `mystore.myshopify.com` — backend normalizes.
   */
  async initiateShopifyOAuth(shopDomain) {
    return await authService.post('/api/shopify/oauth/initiate', {
      shop_domain: shopDomain,
    });
  }

  /**
   * List connected Shopify stores for the current user. Returns
   * { connected: bool, stores: [...] }.
   */
  async getShopifyStores() {
    try {
      const data = await authService.get('/api/shopify/oauth/status');
      return data;
    } catch (err) {
      console.error('[API] getShopifyStores error:', err);
      return { connected: false, stores: [], error: err.message };
    }
  }

  /**
   * Disconnect a Shopify store (revokes our access token, marks the
   * store inactive locally, queues a webhook unsubscribe).
   */
  async disconnectShopifyStore(storeId) {
    return await authService.post('/api/shopify/oauth/disconnect', {
      store_id: storeId,
    });
  }

  /**
   * Generate SEO-optimized product caption.
   * Calls POST /api/oi/generate-caption (requires auth).
   */
  // Task #38: ask Claude for 3-5 differentiated marketing angles for a
  // saturated product. Backend gates on saturation_score >= 0.6 by default
  // — pass {force: true} to override (e.g. user explicitly clicks
  // "Generate anyway" on a low-saturation product). Returns
  // { success, angles: [...], saturation_score, error?, message? }.
  async generateMarketingAngles(product, opts = {}) {
    try {
      const data = await authService.post('/api/oi/generate-marketing-angles', {
        product_id: String(product.product_id || product.id || ''),
        product_title: product.title || product.name || '',
        product_niche: product.niche || 'smart_home',
        product_description: product.description || product.title || '',
        saturation_score: product.saturation_score,
        brand_voice: opts.brandVoice || 'professional',
        target_audience: opts.targetAudience || 'general',
        num_angles: Math.max(1, Math.min(5, opts.numAngles ?? 3)),
        force: !!opts.force,
      });
      return data;
    } catch (error) {
      console.error('[API] generateMarketingAngles error:', error);
      return {
        success: false,
        error: 'request_failed',
        message: error?.message || 'Network error',
      };
    }
  }

  async generateCaption(productTitle, niche, price, tags = null) {
    try {
      // Send the actual product tags when available — the previous
      // ``tags: [niche]`` form gave Claude only the category label, so
      // every caption in a niche shared the same "Tags:" line and
      // converged on the same template wording. Frontend callers
      // should now pass ``product.tags`` (or extracted title tokens).
      const realTags = Array.isArray(tags) && tags.length > 0
        ? tags.filter(Boolean).slice(0, 12)
        : [niche];
      const data = await authService.post('/api/oi/generate-caption', {
        product_title: productTitle,
        product_niche: niche,
        price: parseFloat(price) || 0,
        tags: realTags
      });
      if (data.success && data.caption) {
        return { success: true, caption: data.caption };
      }
      // Fallback to chat if endpoint returned no caption
      return this._generateCaptionViaChat(productTitle, niche, price);
    } catch (error) {
      console.error('[API] generateCaption error:', error);
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
  
  /**
   * Deploy a single product to Shopify.
   *
   * Task #21 (Apr 2026): the backend `/api/deploy/product` endpoint expects
   * `{ product, niche, shopify_store_id?, options? }` — NOT `{ product_id }`.
   * The previous signature of this function just sent an ID, which caused
   * a 422 ValidationError on every deploy attempt (both AliExpress AND CJ).
   *
   * New signature takes the full normalized product object and extracts the
   * supplier fields the backend schema requires. Works for AliExpress AND
   * CJ Dropshipping — the backend schema is now source-agnostic.
   */
  async deployProduct(product, options = {}) {
    const { caption, ...deployOptions } = options;

    // Build payload matching backend SourceProduct schema.
    // CJ products use `all_images`; AliExpress uses a mix. We send both so
    // the backend can pick whichever is populated.
    //
    // Self-learning hookup: round-trip winner_provenance so the backend's
    // /api/deploy/product can write a RecommendationOutcome row with full
    // attribution. Without this, the feedback loop sees deploys from the
    // Products page as "uncategorized" and can't credit the winner-source
    // (Meta / TikTok Shop / Amazon Movers / Etsy) that surfaced the pick.
    const productPayload = {
      title: product.title || product.name,
      description: product.description || caption || product.title || product.name,
      features: product.features || product.tags || [],
      category: product.category || product.niche || null,
      price: product.cost_price || product.price || product.supplier_cost || 0,
      images: product.all_images || (product.image_url ? [product.image_url] : []),
      all_images: product.all_images || null,
      source: product.source || 'aliexpress',
      // Winner attribution (populated by backend's winner-first sourcing
      // path in /api/discovery/quick) — flows back so /api/deploy/product
      // can record per-source self-learning attribution. `source` stays as
      // the routing key ('aliexpress' / 'cj_dropshipping'); winner_source
      // and winner_provenance carry the "which winner surfaced this" info.
      winner_source: product.winner_source || null,
      winner_provenance: product.winner_provenance || null,
      // Supplier identifiers we already have at discovery time — needed
      // for the local Product row creation downstream.
      product_id: product.product_id || product.cj_pid || null,
      supplier_url: product.product_url || product.url || product.affiliate_url || null,
      cost_price: product.cost_price || product.price || null,
      suggested_price: product.suggested_price || product.retail_price || null,
    };

    return authService.post('/api/deploy/product', {
      product: productPayload,
      niche: product.niche || 'general',
      options: {
        // Pass caption through for downstream content-gen if the backend
        // wants to honor it (currently unused; kept for future hook).
        caption,
        ...deployOptions,
      },
    });
  }

  async bulkDeploy(products, options = {}) {
    const productsPayload = (products || []).map(p => ({
      title: p.title || p.name,
      description: p.description || p.title || p.name,
      features: p.features || p.tags || [],
      category: p.category || p.niche || null,
      price: p.cost_price || p.price || p.supplier_cost || 0,
      images: p.all_images || (p.image_url ? [p.image_url] : []),
      all_images: p.all_images || null,
      source: p.source || 'aliexpress',
    }));

    return authService.post('/api/deploy/bulk', {
      products: productsPayload,
      niche: (products && products[0]?.niche) || 'general',
      options,
    });
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
    // The /api/rate-limit/discovery/status endpoint doesn't exist on the
    // backend (verified May 2026). Frontend was 404-spamming the console.
    // Until a real backend route is wired (TierRateLimiter.get_user_status
    // could be exposed), we short-circuit here so the UI gets a sensible
    // ∞-defaults object without firing a network call.
    //
    // For Stratosphere this is always ∞ anyway (per TIER_RATE_LIMITS),
    // and for lower tiers the cap is wall-clock based (per-day reset)
    // rather than something the UI needs to render in real time.
    const tier = authService.getTier();
    return {
      tier,
      daily_remaining: '∞',
      daily_limit: '∞',
      min_interval_minutes: tier === 'stratosphere' ? 0.5 : 30,
      _stub: true,
    };
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
  
  async upgradeTier(tier, interval = 'monthly') {
    return authService.post('/api/user/upgrade', { tier, interval });
  }

  async getTierInfo() {
    return authService.get('/api/user/tier');
  }

  /**
   * All products the user has deployed to Shopify.
   * Returns { total, deployments }. Used by the onboarding checklist.
   */
  async getDeployments() {
    return authService.get('/api/dashboard/v2/deployments');
  }

  // ===========================================================================
  // DATA & PRIVACY (GDPR self-serve)
  // ===========================================================================
  // These endpoints are powered by ospra_os/api/account_routes.py and share
  // the same backend service module (ospra_os/security/gdpr.py) used by the
  // Shopify GDPR webhooks — so the export/delete a user triggers from the
  // UI is identical to what Shopify gets when it pings customers/data_request
  // or shop/redact.

  async getDataSummary() {
    return authService.get('/api/account/data-summary');
  }

  async exportMyData() {
    return authService.get('/api/account/data-export');
  }

  async deleteMyData({ confirmEmail, deleteConnectedStores = true } = {}) {
    return authService.post('/api/account/data-delete', {
      confirm_email: confirmEmail,
      delete_connected_stores: deleteConnectedStores,
    });
  }
}

// Singleton export
export const api = new OspraAPI();

// Re-export API_BASE_URL for components that need to resolve image URLs
export { API_BASE_URL };

export default api;
