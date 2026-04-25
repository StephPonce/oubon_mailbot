/**
 * Analytics — thin frontend wrapper around PostHog (task #38).
 *
 * Design goals:
 *   - Zero hard dependency. If `posthog-js` isn't installed (or fails
 *     to import for any reason), every exported method is a clean
 *     no-op. The app still runs; analytics just isn't recorded.
 *   - Init only when both VITE_POSTHOG_KEY and VITE_POSTHOG_HOST are
 *     set in env. No silent calls home if the user hasn't configured it.
 *   - Identify on login, reset on logout. The AuthProvider wires those.
 *   - Capture key user actions tied to cost decisions (e.g. how often
 *     people click the "Fetch real Amazon reviews" button — answers
 *     "is this feature pulling its weight?")
 *
 * Backend PostHog wiring (server-side events) lives in
 * ospra_os/observability/posthog_client.py and is unchanged by this.
 */

let _posthog = null;
let _initialized = false;
let _initPromise = null;

const POSTHOG_KEY = import.meta?.env?.VITE_POSTHOG_KEY;
const POSTHOG_HOST = import.meta?.env?.VITE_POSTHOG_HOST || 'https://us.i.posthog.com';

/**
 * Lazy-initialize the PostHog SDK. Idempotent — safe to call repeatedly;
 * only the first call does real work.
 *
 * If `posthog-js` isn't installed OR no VITE_POSTHOG_KEY is set, this
 * resolves cleanly and every subsequent capture() call is a no-op.
 */
export async function initAnalytics() {
  if (_initialized) return _posthog;
  if (_initPromise) return _initPromise;

  if (!POSTHOG_KEY) {
    _initialized = true;
    return null;
  }

  _initPromise = (async () => {
    try {
      // Dynamic import so the bundle doesn't break if posthog-js is
      // missing from node_modules (the user hasn't run `npm install`
      // since the dep was added to package.json).
      const mod = await import('posthog-js');
      const posthog = mod.default || mod;
      posthog.init(POSTHOG_KEY, {
        api_host: POSTHOG_HOST,
        // Privacy-friendly defaults: no autocapture of raw DOM events,
        // no session recording. Capture only what we explicitly send.
        autocapture: false,
        disable_session_recording: true,
        capture_pageview: true,
        capture_pageleave: true,
        person_profiles: 'identified_only',
      });
      _posthog = posthog;
      _initialized = true;
      return posthog;
    } catch (err) {
      // posthog-js not installed or init failed. Silently degrade.
      // We log once at debug level so devs can find this if they
      // expected analytics to be live.
      if (typeof console !== 'undefined' && console.debug) {
        console.debug('[analytics] PostHog unavailable, no-op mode:', err?.message || err);
      }
      _initialized = true;
      return null;
    }
  })();

  return _initPromise;
}

/**
 * Identify the current user. Call on login.
 *
 * @param {{id: string|number, email?: string, tier?: string}} user
 */
export async function identifyUser(user) {
  await initAnalytics();
  if (!_posthog || !user || !user.id) return;
  try {
    _posthog.identify(String(user.id), {
      email: user.email,
      tier: user.tier,
    });
  } catch (err) {
    // Never let analytics break the auth flow.
  }
}

/**
 * Reset the analytics user. Call on logout.
 */
export async function resetUser() {
  await initAnalytics();
  if (!_posthog) return;
  try {
    _posthog.reset();
  } catch (err) {
    // ignore
  }
}

/**
 * Capture a named event with optional properties.
 *
 * Use sparingly — events flow into a paid PostHog plan after a
 * threshold. Reserve this for actions that answer real questions
 * (cost-decision events, conversion-funnel events). Avoid logging
 * "user moved mouse" style noise.
 *
 * @param {string} event - snake_case event name
 * @param {object} [props] - optional event properties
 */
export async function capture(event, props = {}) {
  await initAnalytics();
  if (!_posthog || !event) return;
  try {
    _posthog.capture(event, props);
  } catch (err) {
    // ignore
  }
}

/**
 * Server-side feature flags via PostHog. Returns ``false`` (the safe
 * default) when analytics is unavailable.
 *
 * @param {string} flag - feature flag key
 * @returns {Promise<boolean>}
 */
export async function isFeatureEnabled(flag) {
  await initAnalytics();
  if (!_posthog || !flag) return false;
  try {
    return Boolean(_posthog.isFeatureEnabled(flag));
  } catch (err) {
    return false;
  }
}

// Convenience event names used by the components. Keep this list short —
// it's the public contract analytics consumers depend on. Adding a new
// event = adding a constant here = adding a row to the analytics
// dashboard.
export const EVENTS = Object.freeze({
  // Discovery
  DISCOVERY_STARTED: 'discovery_started',
  DISCOVERY_COMPLETED: 'discovery_completed',

  // AI analysis (existing /api/oi/analyze-product)
  AI_ANALYSIS_REQUESTED: 'ai_analysis_requested',
  AI_ANALYSIS_REFRESHED: 'ai_analysis_refreshed',

  // Phase K — the cost-controlled on-demand fetch. Tracking this
  // answers "is the on-click fetch pulling its weight?"
  AMAZON_REVIEWS_FETCH_REQUESTED: 'amazon_reviews_fetch_requested',
  AMAZON_REVIEWS_FETCH_SUCCEEDED: 'amazon_reviews_fetch_succeeded',
  AMAZON_REVIEWS_FETCH_NO_DATA: 'amazon_reviews_fetch_no_data',
  AMAZON_REVIEWS_FETCH_FAILED: 'amazon_reviews_fetch_failed',

  // Auth
  LOGIN_SUCCEEDED: 'login_succeeded',
  LOGOUT: 'logout',
});

export default {
  initAnalytics,
  identifyUser,
  resetUser,
  capture,
  isFeatureEnabled,
  EVENTS,
};
