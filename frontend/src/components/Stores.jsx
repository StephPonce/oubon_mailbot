/**
 * Connected Stores page — /settings/stores
 *
 * The OAuth flow:
 *   1. User types `mystore` (or `mystore.myshopify.com`) and clicks Connect.
 *   2. We POST /api/shopify/oauth/initiate → returns authorization_url.
 *   3. We redirect the browser to that URL (Shopify's permission screen).
 *   4. User approves on Shopify; Shopify redirects to
 *      ${BACKEND}/api/shopify/oauth/callback?code=…&state=…
 *   5. Backend exchanges code for access token, persists the store, then
 *      redirects to ${FRONTEND}/settings/stores?connected=<shop> (or
 *      ?error=<reason> if anything went wrong).
 *   6. This page reads the URL params and shows a success/error banner.
 *
 * Backend route group: ospra_os/api/shopify_oauth_routes.py
 *   POST /api/shopify/oauth/initiate
 *   GET  /api/shopify/oauth/callback   (Shopify hits this directly)
 *   GET  /api/shopify/oauth/status     (this page polls)
 *   POST /api/shopify/oauth/disconnect
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Store, Plus, ExternalLink, Loader2, CheckCircle, AlertCircle, Trash2 } from 'lucide-react';
import { PageLayout } from './Layout';
import { api } from '../services/api';

// Tiny normalizer matching the backend (`mystore` → `mystore.myshopify.com`).
// Shown in the input hint and used for client-side validation only — the
// backend re-normalizes server-side.
function normalizeShopDomain(raw) {
  const s = (raw || '').trim().toLowerCase();
  if (!s) return '';
  if (s.endsWith('.myshopify.com')) return s;
  return `${s}.myshopify.com`;
}

function Stores() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [shopInput, setShopInput] = useState('');
  const [connecting, setConnecting] = useState(false);
  const [stores, setStores] = useState([]);
  const [loadingStores, setLoadingStores] = useState(true);
  const [banner, setBanner] = useState(null); // { kind: 'success' | 'error', text: string }

  // ── On mount: parse callback redirect params + fetch existing stores ────
  useEffect(() => {
    const connected = searchParams.get('connected');
    const error = searchParams.get('error');
    if (connected) {
      setBanner({
        kind: 'success',
        text: `Connected ${connected} successfully. Live metrics will start flowing within a minute.`,
      });
      // Clear the param so a refresh doesn't re-show the toast.
      searchParams.delete('connected');
      setSearchParams(searchParams, { replace: true });
    } else if (error) {
      const map = {
        configuration_error: "Shopify isn't configured on this server. Set SHOPIFY_PARTNER_CLIENT_ID and SHOPIFY_PARTNER_CLIENT_SECRET in .env, then restart.",
        invalid_signature: 'Shopify rejected the callback signature. Make sure SHOPIFY_PARTNER_CLIENT_SECRET in .env matches the one in your Partner Dashboard.',
        invalid_state: 'OAuth state mismatch (CSRF protection). Try connecting again from this page.',
        token_exchange_failed: "Couldn't exchange the auth code for an access token. Check that the redirect URI in your Shopify app matches http://localhost:8001/api/shopify/oauth/callback exactly.",
        network_error: 'Network error talking to Shopify. Try again in a moment.',
      };
      setBanner({ kind: 'error', text: map[error] || `Connection failed: ${error}` });
      searchParams.delete('error');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const loadStores = useCallback(async () => {
    setLoadingStores(true);
    try {
      const data = await api.getShopifyStores();
      setStores(Array.isArray(data?.stores) ? data.stores : []);
    } catch (err) {
      console.error('Failed to load stores:', err);
    } finally {
      setLoadingStores(false);
    }
  }, []);

  useEffect(() => { loadStores(); }, [loadStores]);

  // ── Connect: POST /initiate, then window.location to authorization_url ──
  const handleConnect = useCallback(async (e) => {
    e?.preventDefault();
    const normalized = normalizeShopDomain(shopInput);
    if (!normalized) {
      setBanner({ kind: 'error', text: 'Enter your Shopify store domain (e.g. my-store.myshopify.com).' });
      return;
    }

    setConnecting(true);
    setBanner(null);
    try {
      const result = await api.initiateShopifyOAuth(normalized);
      const url = result?.authorization_url;
      if (!url) {
        throw new Error(result?.detail || result?.error || 'Server did not return an authorization URL');
      }
      // Hand off to Shopify's consent screen. The browser will return to
      // /settings/stores with ?connected=<shop> or ?error=<reason>.
      window.location.href = url;
    } catch (err) {
      setBanner({
        kind: 'error',
        text: err?.message?.includes('configuration')
          ? 'Shopify credentials are missing on the backend. Add SHOPIFY_PARTNER_CLIENT_ID and SHOPIFY_PARTNER_CLIENT_SECRET to .env, restart, then try again.'
          : `Could not start OAuth: ${err?.message || 'unknown error'}`,
      });
      setConnecting(false);
    }
  }, [shopInput]);

  const handleDisconnect = useCallback(async (storeId, shopDomain) => {
    if (!window.confirm(`Disconnect ${shopDomain}? Live metrics will stop. You can reconnect later.`)) return;
    try {
      await api.disconnectShopifyStore(storeId);
      setBanner({ kind: 'success', text: `Disconnected ${shopDomain}.` });
      await loadStores();
    } catch (err) {
      setBanner({ kind: 'error', text: `Disconnect failed: ${err?.message || err}` });
    }
  }, [loadStores]);

  const previewDomain = shopInput ? normalizeShopDomain(shopInput) : '';

  return (
    <PageLayout
      title="Connected Stores"
      subtitle="Connect a Shopify store to see live metrics instead of demo data"
    >
      {/* ── Banner ───────────────────────────────────────────────────────── */}
      {banner && (
        <div
          className={`mb-6 rounded-xl px-4 py-3 border flex items-start gap-3 ${
            banner.kind === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
              : 'bg-red-500/10 border-red-500/30 text-red-200'
          }`}
        >
          {banner.kind === 'success' ? (
            <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          )}
          <div className="text-sm leading-relaxed">{banner.text}</div>
        </div>
      )}

      {/* ── Connect-a-store card ────────────────────────────────────────── */}
      <div className="mb-8 rounded-2xl bg-white/5 border border-white/10 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center">
            <Store className="w-5 h-5 text-emerald-300" />
          </div>
          <div>
            <h3 className="text-white font-semibold">Connect a Shopify store</h3>
            <p className="text-white/50 text-sm">OAuth via your Partner App. Tokens are encrypted at rest.</p>
          </div>
        </div>

        <form onSubmit={handleConnect} className="space-y-3">
          <label className="block">
            <span className="text-white/60 text-xs">Store domain</span>
            <div className="mt-1 flex gap-2">
              <input
                type="text"
                value={shopInput}
                onChange={(e) => setShopInput(e.target.value)}
                placeholder="my-store"
                disabled={connecting}
                className="flex-1 px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white placeholder-white/30 focus:outline-none focus:border-purple-500/60 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={connecting || !shopInput.trim()}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-600 to-cyan-600 text-white font-semibold hover:from-emerald-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-all"
              >
                {connecting ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Redirecting…</>
                ) : (
                  <><Plus className="w-4 h-4" /> Connect</>
                )}
              </button>
            </div>
            {previewDomain && (
              <p className="mt-1 text-xs text-white/40">
                Will connect: <span className="text-cyan-300">{previewDomain}</span>
              </p>
            )}
          </label>
        </form>

        <p className="mt-4 text-xs text-white/40 leading-relaxed">
          You'll be sent to Shopify's permission screen. After approving, you'll
          land back here. Make sure your Partner App's redirect URL includes{' '}
          <code className="text-white/60">http://localhost:8001/api/shopify/oauth/callback</code>.
        </p>
      </div>

      {/* ── Connected stores list ───────────────────────────────────────── */}
      <div className="rounded-2xl bg-white/5 border border-white/10 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold">Your connected stores</h3>
          <button
            onClick={loadStores}
            className="text-xs text-white/50 hover:text-white/80"
          >
            Refresh
          </button>
        </div>

        {loadingStores ? (
          <div className="py-8 text-center text-white/50">
            <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Loading stores…
          </div>
        ) : stores.length === 0 ? (
          <div className="py-8 text-center text-white/40 text-sm">
            No stores connected yet. Connect one above to see live metrics.
          </div>
        ) : (
          <ul className="divide-y divide-white/10">
            {stores.map((s) => (
              <li key={s.id || s.shop_domain} className="py-3 flex items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    <a
                      href={`https://${s.shop_domain}/admin`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-white/90 hover:text-cyan-300 font-medium truncate flex items-center gap-1"
                    >
                      {s.shop_domain}
                      <ExternalLink className="w-3 h-3 opacity-50" />
                    </a>
                  </div>
                  <div className="mt-0.5 text-xs text-white/40 flex flex-wrap gap-x-3">
                    {s.connected_at && <span>Connected {new Date(s.connected_at).toLocaleDateString()}</span>}
                    {s.scopes_count != null && <span>{s.scopes_count} scopes</span>}
                    {s.is_active === false && <span className="text-amber-400">Inactive</span>}
                  </div>
                </div>
                <button
                  onClick={() => handleDisconnect(s.id, s.shop_domain)}
                  className="text-xs px-2 py-1 rounded-md text-red-300/80 hover:bg-red-500/10 hover:text-red-200 flex items-center gap-1 transition-all"
                  title="Disconnect this store"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Disconnect
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </PageLayout>
  );
}

export default Stores;
