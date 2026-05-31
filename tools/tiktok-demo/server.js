/**
 * Oubon Shop Automation — merchant control panel
 * ================================================
 *
 * Shopify dropshipping merchants connect their TikTok account, then
 * create promotional video campaigns for products they sell. Campaigns
 * can be saved as TikTok drafts or published directly to the connected
 * creator's profile.
 *
 * TikTok scopes used:
 *   - user.info.basic        identity (open_id, avatar, display name)
 *   - user.info.profile      verified status, profile URL
 *   - user.info.stats        follower / following / likes / video count
 *   - video.upload           save campaign video as a TikTok draft
 *   - video.publish          publish campaign video directly
 */

require('dotenv').config();
const express = require('express');
const session = require('express-session');
const axios = require('axios');
const multer = require('multer');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const app = express();
const upload = multer({ dest: path.join(__dirname, 'uploads/') });

const uploadsDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir, { recursive: true });

// --- Config ----------------------------------------------------------
const CLIENT_KEY      = process.env.TIKTOK_CLIENT_KEY      || '';
const CLIENT_SECRET   = process.env.TIKTOK_CLIENT_SECRET   || '';
const REDIRECT_URI    = process.env.TIKTOK_REDIRECT_URI    || 'http://localhost:3000/auth/tiktok/callback';
const API_BASE        = process.env.TIKTOK_API_BASE        || 'https://open.tiktokapis.com';
const AUTH_BASE       = process.env.TIKTOK_AUTH_BASE       || 'https://www.tiktok.com';
const SESSION_SECRET  = process.env.SESSION_SECRET         || 'change-me-in-env';
const PORT            = parseInt(process.env.PORT || '3000', 10);

const SCOPES = [
  'user.info.basic',
  'user.info.profile',
  'user.info.stats',
  'video.upload',
  'video.publish',
].join(',');

if (!CLIENT_KEY || !CLIENT_SECRET) {
  console.error('\n[FATAL] TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET must be set.');
  process.exit(1);
}

// --- Mock product catalog -------------------------------------------
// Hard-coded for the merchant view. In the real Ospra OS system these
// come from the linked Shopify storefront via the Admin API.
const PRODUCTS = [
  {
    id: 'p001',
    name: 'AuraGlow Sunset Lamp',
    price: 29.99,
    image: 'https://images.unsplash.com/photo-1513506003901-1e6a229e2d15?w=400&q=80&auto=format&fit=crop',
    tagline: 'Cinematic sunset projection for any room.',
    description: '360° rotating warm-light projector that turns any wall into a cinematic sunset. Plugs in via USB-C. Adjustable color temperature.',
  },
  {
    id: 'p002',
    name: 'ChillCloud Mini Humidifier',
    price: 18.49,
    image: 'https://images.unsplash.com/photo-1583394838336-acd977736f90?w=400&q=80&auto=format&fit=crop',
    tagline: 'Desk-sized humidifier with ambient LED.',
    description: 'Whisper-quiet 300ml ultrasonic humidifier. 7-color ambient LED. Auto-off when empty. USB-powered.',
  },
  {
    id: 'p003',
    name: 'GripFlex Magnetic Wallet',
    price: 24.00,
    image: 'https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=400&q=80&auto=format&fit=crop',
    tagline: 'MagSafe wallet + phone stand in one.',
    description: 'MagSafe-compatible card holder that flips out into a phone stand. Carbon fiber finish. Holds 3 cards.',
  },
  {
    id: 'p004',
    name: 'PocketPress Garment Steamer',
    price: 34.99,
    image: 'https://images.unsplash.com/photo-1532634922-8fe0b757fb13?w=400&q=80&auto=format&fit=crop',
    tagline: 'Travel-sized steamer that heats in 30 sec.',
    description: 'Handheld garment steamer. 30-second heat-up. 100ml tank for ~10 minutes of steam. USB-C rechargeable.',
  },
  {
    id: 'p005',
    name: 'NimbusPet Self-Cleaning Brush',
    price: 22.50,
    image: 'https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=400&q=80&auto=format&fit=crop',
    tagline: 'One-button hair release for cats & dogs.',
    description: 'Slicker brush with retractable bristles. One-button hair ejection. Comfortable for short and long-haired pets.',
  },
  {
    id: 'p006',
    name: 'BrewMate Travel Tumbler',
    price: 19.99,
    image: 'https://images.unsplash.com/photo-1572119865084-43c285814d63?w=400&q=80&auto=format&fit=crop',
    tagline: '12-hour hot, 24-hour cold, leak-proof.',
    description: '470ml stainless steel insulated tumbler. Double-wall vacuum insulation. Leak-proof magnetic lid. 8 colors.',
  },
];

const findProduct = (id) => PRODUCTS.find(p => p.id === id);

// --- Middleware ------------------------------------------------------
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
// Serve favicon.png + any other static assets from ./public so the demo
// pages can reference /favicon.png. This is required for TikTok app review
// — the reviewer checks that the same icon submitted to the TikTok portal
// also appears as the favicon on the connecting website. Without static
// serving, /favicon.png 404s and the icon-consistency check fails.
// (`path` is already imported at the top of this file.)
app.use(express.static(path.join(__dirname, 'public')));
app.use(session({
  secret: SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, maxAge: 24 * 60 * 60 * 1000 },
}));

// --- HTML layout -----------------------------------------------------
function page({ title, body, user, active }) {
  const navLink = (href, label, key) => {
    const cls = active === key ? 'active' : '';
    return `<a href="${href}" class="${cls}">${label}</a>`;
  };

  const userPill = user
    ? `
      <div class="header-user">
        <img class="header-avatar" src="${user.avatar_url || ''}" alt="" />
        <div class="header-user-meta">
          <div class="header-user-name">${user.display_name || 'Connected'}</div>
          <div class="header-user-reach">${(user.follower_count ?? 0).toLocaleString()} followers</div>
        </div>
      </div>
    `
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="icon" type="image/png" href="/favicon.png" />
  <link rel="shortcut icon" type="image/png" href="/favicon.png" />
  <title>${title} · Oubon Shop Automation</title>
  <style>
    :root {
      --bg: #0a0a0f;
      --card: #14141c;
      --card-elev: #1c1c26;
      --border: #2a2a3a;
      --accent: #25f4ee;
      --accent2: #fe2c55;
      --text: #f3f3f5;
      --muted: #9b9bb0;
      --good: #4ade80;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.5;
    }
    header {
      padding: 14px 32px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: var(--card);
    }
    header .brand { display: flex; align-items: center; gap: 12px; }
    /* Logo image — must match the icon submitted to the TikTok Developer
       Portal Basic Info (the cyan "O" PNG saved at ./public/favicon.png).
       Previously this was a CSS gradient with a literal "O" character,
       which caused an icon-mismatch rejection — the reviewer flagged that
       the on-site logo didn't match the portal icon or the favicon. */
    header .brand .logo {
      width: 32px; height: 32px; border-radius: 7px;
      display: block;
    }
    header h1 { margin: 0; font-size: 17px; }
    header nav { display: flex; gap: 4px; align-items: center; margin-left: 32px; }
    header nav a {
      color: var(--muted); text-decoration: none; padding: 8px 14px;
      border-radius: 6px; font-size: 14px;
    }
    header nav a:hover { background: rgba(255,255,255,0.05); color: var(--text); }
    header nav a.active { color: var(--text); background: rgba(37,244,238,0.1); }
    .header-right { display: flex; align-items: center; gap: 16px; margin-left: auto; }
    .header-user {
      display: flex; align-items: center; gap: 10px;
      padding: 4px 12px 4px 4px;
      background: var(--card-elev);
      border: 1px solid var(--border);
      border-radius: 99px;
    }
    .header-avatar { width: 32px; height: 32px; border-radius: 50%; }
    .header-user-name { font-size: 13px; font-weight: 600; }
    .header-user-reach { font-size: 11px; color: var(--muted); }
    main { max-width: 1100px; margin: 24px auto 0; padding: 0 32px 80px; }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 20px;
    }
    h2 { margin-top: 0; font-size: 22px; }
    h3 { margin-top: 24px; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; }
    .btn {
      display: inline-block;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      color: #000;
      padding: 11px 22px;
      border-radius: 8px;
      text-decoration: none;
      font-weight: 700;
      border: none;
      cursor: pointer;
      font-size: 14px;
    }
    .btn:disabled, .btn.disabled {
      opacity: 0.4; cursor: not-allowed;
      background: var(--card-elev); color: var(--muted);
    }
    .btn.secondary {
      background: var(--card-elev); color: var(--text);
      border: 1px solid var(--border);
    }
    .btn.sm { padding: 7px 14px; font-size: 13px; }
    .product-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
    }
    .product-card {
      background: var(--card-elev);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .product-card img {
      width: 100%; aspect-ratio: 4/3; object-fit: cover; display: block;
      background: var(--bg);
    }
    .product-card .body { padding: 16px; flex: 1; display: flex; flex-direction: column; }
    .product-card .name { font-weight: 700; font-size: 15px; margin-bottom: 4px; }
    .product-card .price { color: var(--accent); font-weight: 700; font-size: 16px; }
    .product-card .tagline { color: var(--muted); font-size: 13px; margin: 8px 0 12px; flex: 1; }
    .product-card .tt-link {
      font-size: 11px; color: var(--muted); text-decoration: none;
      padding: 6px 10px; background: var(--bg); border: 1px solid var(--border);
      border-radius: 6px; display: inline-block; margin-bottom: 10px;
    }
    .product-card .tt-link:hover { color: var(--accent); }
    .product-card .actions { display: flex; gap: 8px; }
    .grid-stats {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
    }
    .stat {
      background: var(--card-elev);
      padding: 14px;
      border-radius: 8px;
      border: 1px solid var(--border);
    }
    .stat .label {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .stat .value { font-size: 22px; font-weight: 700; margin-top: 4px; }
    .integration-row {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px;
      background: var(--card-elev);
      border-radius: 8px;
      border: 1px solid var(--border);
    }
    .avatar { width: 56px; height: 56px; border-radius: 50%; background: var(--border); }
    .verified {
      display: inline-block;
      background: rgba(37,244,238,0.15);
      color: var(--accent);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      margin-left: 6px;
    }
    .status-pill {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 99px;
      font-size: 12px;
      font-weight: 600;
    }
    .status-pill.live { background: rgba(74,222,128,0.15); color: var(--good); }
    .status-pill.draft { background: rgba(155,155,176,0.15); color: var(--muted); }
    .status-pill.connected { background: rgba(74,222,128,0.15); color: var(--good); }
    .form-row { margin-bottom: 16px; }
    .form-row label {
      display: block; color: var(--muted); font-size: 13px;
      margin-bottom: 6px; font-weight: 500;
    }
    .form-row input[type=file],
    .form-row input[type=text],
    .form-row textarea,
    .form-row select {
      background: var(--bg); border: 1px solid var(--border); color: var(--text);
      padding: 10px 12px; border-radius: 6px; width: 100%; font: inherit;
    }
    .form-row textarea { min-height: 80px; resize: vertical; }
    .button-row { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 24px; align-items: center; }
    .raw {
      background: #050507; padding: 14px; border-radius: 6px;
      font-family: 'SF Mono', Menlo, monospace; font-size: 12px;
      white-space: pre-wrap; word-break: break-word; color: var(--muted);
      max-height: 240px; overflow: auto;
    }
    .muted { color: var(--muted); font-size: 14px; }
    .small { font-size: 13px; }
    table.campaigns { width: 100%; border-collapse: collapse; }
    table.campaigns th, table.campaigns td {
      text-align: left; padding: 12px 8px; border-bottom: 1px solid var(--border);
      font-size: 14px;
    }
    table.campaigns th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
    table.campaigns tr:last-child td { border-bottom: none; }
    table.campaigns .campaign-product { display: flex; align-items: center; gap: 10px; }
    table.campaigns .campaign-product img { width: 36px; height: 36px; border-radius: 6px; object-fit: cover; }
    .flash {
      padding: 12px 16px; border-radius: 8px; margin-bottom: 16px;
      border: 1px solid;
    }
    .flash.ok { background: rgba(74,222,128,0.08); border-color: rgba(74,222,128,0.3); color: var(--good); }
    .flash.err { background: rgba(254,44,85,0.08); border-color: rgba(254,44,85,0.3); color: var(--accent2); }
    footer {
      border-top: 1px solid var(--border);
      padding: 20px 32px;
      color: var(--muted);
      font-size: 13px;
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      justify-content: space-between;
      align-items: center;
      background: var(--card);
      margin-top: 48px;
    }
    footer a { color: var(--accent); text-decoration: none; margin-left: 16px; }
    footer a:first-of-type { margin-left: 0; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <img class="logo" src="/favicon.png" alt="Oubon Shop Automation" />
      <h1>Oubon Shop Automation</h1>
    </div>
    ${user ? `
      <nav>
        ${navLink('/products', 'Products', 'products')}
        ${navLink('/campaigns', 'Campaigns', 'campaigns')}
        ${navLink('/settings/integrations', 'Settings', 'settings')}
      </nav>
    ` : ''}
    <div class="header-right">
      ${userPill}
      ${user
        ? `<a href="/logout" class="muted small" style="text-decoration: none;">Logout</a>`
        : `<a href="/auth/login" class="btn sm">Sign in with TikTok</a>`
      }
    </div>
  </header>
  <main>
    ${body}
  </main>
  <footer>
    <div>© 2026 Oubon Shop Automation. All rights reserved.</div>
    <div>
      <a href="/privacy">Privacy Policy</a>
      <a href="/terms">Terms of Service</a>
      <a href="/permissions">Permissions</a>
      <a href="mailto:sponce96@icloud.com">Contact</a>
    </div>
  </footer>
</body>
</html>`;
}

// --- Routes ----------------------------------------------------------

// Public landing page
app.get('/', (req, res) => {
  if (req.session.user) return res.redirect('/products');

  res.send(page({
    title: 'Sign in',
    body: `
      <div class="card" style="text-align: center; padding: 56px 32px;">
        <h2 style="font-size: 32px; margin-bottom: 12px;">
          TikTok posting on autopilot for your Shopify store.
        </h2>
        <p class="muted" style="font-size: 17px; max-width: 540px; margin: 0 auto 32px;">
          Oubon Shop Automation connects your TikTok account to your
          Shopify store, then drafts and publishes promotional videos
          for products you list — so you can spend time on the products,
          not the posting.
        </p>
        <a class="btn" href="/auth/login">Sign in with TikTok</a>
        <p class="muted" style="margin-top: 24px; font-size: 13px;">
          By signing in you agree to our
          <a href="/terms" style="color: var(--accent);">Terms</a> and
          <a href="/privacy" style="color: var(--accent);">Privacy Policy</a>.
        </p>
      </div>

      <div class="card">
        <h3 style="margin-top: 0;">How it works</h3>
        <ol style="color: var(--text); line-height: 1.8;">
          <li><strong>Sign in with TikTok.</strong> One-click OAuth links your TikTok creator account to your Oubon Shop dashboard.</li>
          <li><strong>Open your product catalog.</strong> Pick a product you want to promote.</li>
          <li><strong>Create a campaign.</strong> Upload a short promotional video, then choose: save it as a TikTok draft to review, or publish directly to your TikTok profile.</li>
          <li><strong>Track every campaign.</strong> Every video posted shows up in your Campaigns log with status, publish ID, and timestamp.</li>
        </ol>
      </div>
    `,
  }));
});

// OAuth start
app.get('/auth/login', (req, res) => {
  const state = crypto.randomBytes(16).toString('hex');
  req.session.oauth_state = state;

  const params = new URLSearchParams({
    client_key: CLIENT_KEY,
    response_type: 'code',
    scope: SCOPES,
    redirect_uri: REDIRECT_URI,
    state,
  });
  res.redirect(`${AUTH_BASE}/v2/auth/authorize/?${params.toString()}`);
});

// OAuth callback — also pre-fetches /v2/user/info/ so the header pill
// is populated everywhere immediately.
app.get('/auth/tiktok/callback', async (req, res) => {
  const { code, state, error, error_description } = req.query;

  if (error) {
    return res.send(page({
      title: 'Sign-in failed',
      body: `<div class="card"><h2>Sign-in failed</h2>
        <p class="err">${error}: ${error_description || ''}</p>
        <a class="btn secondary" href="/">Back to home</a></div>`,
    }));
  }
  if (!code) return res.status(400).send('Missing authorization code');
  if (!state || state !== req.session.oauth_state) {
    return res.status(400).send('State mismatch');
  }

  try {
    const tokenResp = await axios.post(
      `${API_BASE}/v2/oauth/token/`,
      new URLSearchParams({
        client_key: CLIENT_KEY,
        client_secret: CLIENT_SECRET,
        code,
        grant_type: 'authorization_code',
        redirect_uri: REDIRECT_URI,
      }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
    );

    const { access_token, refresh_token, open_id, scope, expires_in } = tokenResp.data;
    if (!access_token) {
      throw new Error('No access_token in response: ' + JSON.stringify(tokenResp.data));
    }

    req.session.tokens = { access_token, refresh_token, open_id, scope, expires_in };

    // Pre-fetch user info so the header pill is ready
    try {
      const fields = [
        'open_id', 'union_id', 'avatar_url', 'display_name',
        'bio_description', 'profile_deep_link', 'is_verified', 'username',
        'follower_count', 'following_count', 'likes_count', 'video_count',
      ].join(',');
      const u = await axios.get(`${API_BASE}/v2/user/info/?fields=${fields}`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      req.session.user = u.data?.data?.user || {};
      req.session.user_raw = u.data;
    } catch (e) {
      console.warn('[user.info pre-fetch] failed, will retry on first page:', e.message);
    }

    // Land on the product catalog — the real product surface.
    res.redirect('/products');
  } catch (e) {
    console.error('[OAuth] Token exchange failed:', e.response?.data || e.message);
    res.status(500).send(page({
      title: 'Sign-in failed',
      body: `<div class="card"><h2>Couldn't complete sign-in</h2>
        <pre class="raw">${JSON.stringify(e.response?.data || e.message, null, 2)}</pre>
        <a class="btn secondary" href="/">Back to home</a></div>`,
    }));
  }
});

app.get('/logout', (req, res) => {
  req.session.destroy(() => res.redirect('/'));
});

function requireAuth(req, res, next) {
  if (!req.session.tokens?.access_token) return res.redirect('/');
  next();
}

// Product catalog — the post-OAuth landing page.
// Each product card pulls in user.info.profile data: the profile_deep_link
// is rendered as the "View seller on TikTok" link so buyers can verify
// the seller's TikTok presence.
app.get('/products', requireAuth, (req, res) => {
  const user = req.session.user || {};
  const profileLink = user.profile_deep_link || '';
  const username = user.username || 'seller';

  const cards = PRODUCTS.map(p => `
    <div class="product-card">
      <img src="${p.image}" alt="${p.name}" loading="lazy" />
      <div class="body">
        <div class="name">${p.name}</div>
        <div class="price">$${p.price.toFixed(2)}</div>
        <div class="tagline">${p.tagline}</div>
        ${profileLink
          ? `<a class="tt-link" href="${profileLink}" target="_blank" rel="noopener">View seller @${username} on TikTok ↗</a>`
          : ''}
        <div class="actions">
          <a class="btn sm" href="/campaigns/new?product=${p.id}">Promote on TikTok</a>
          <a class="btn secondary sm" href="/products/${p.id}">Details</a>
        </div>
      </div>
    </div>
  `).join('');

  res.send(page({
    title: 'Products',
    user,
    active: 'products',
    body: `
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: end; margin-bottom: 8px;">
          <div>
            <h2 style="margin: 0;">Your Shopify Products</h2>
            <p class="muted" style="margin: 4px 0 0;">Pick a product to create a TikTok promotional campaign for it.</p>
          </div>
          <div class="status-pill connected">● TikTok connected</div>
        </div>
        <div class="product-grid" style="margin-top: 20px;">${cards}</div>
      </div>
    `,
  }));
});

// Single-product detail page.
app.get('/products/:id', requireAuth, (req, res) => {
  const user = req.session.user || {};
  const product = findProduct(req.params.id);
  if (!product) {
    return res.status(404).send(page({
      title: 'Product not found',
      user,
      active: 'products',
      body: `<div class="card"><h2>Product not found</h2><a class="btn secondary" href="/products">Back to catalog</a></div>`,
    }));
  }

  const profileLink = user.profile_deep_link || '';
  const username = user.username || 'seller';

  res.send(page({
    title: product.name,
    user,
    active: 'products',
    body: `
      <a href="/products" class="muted small" style="text-decoration: none;">← Back to products</a>
      <div class="card" style="margin-top: 12px;">
        <div style="display: grid; grid-template-columns: 320px 1fr; gap: 32px;">
          <img src="${product.image}" alt="${product.name}" style="width: 100%; aspect-ratio: 4/3; object-fit: cover; border-radius: 8px;" />
          <div>
            <h2 style="margin-top: 0;">${product.name}</h2>
            <div style="font-size: 22px; color: var(--accent); font-weight: 700; margin-bottom: 16px;">$${product.price.toFixed(2)}</div>
            <p>${product.description}</p>
            ${profileLink
              ? `<p class="small"><a href="${profileLink}" target="_blank" rel="noopener" style="color: var(--accent);">View seller @${username} on TikTok ↗</a></p>`
              : ''}
            <div class="button-row">
              <a class="btn" href="/campaigns/new?product=${product.id}">Promote on TikTok →</a>
            </div>
          </div>
        </div>
      </div>
    `,
  }));
});

// Campaign log — list of campaigns created in this session, with
// status driven by which scope was exercised.
app.get('/campaigns', requireAuth, (req, res) => {
  const user = req.session.user || {};
  const campaigns = req.session.campaigns || [];

  const rows = campaigns.length === 0
    ? `<tr><td colspan="5" class="muted" style="padding: 24px; text-align: center;">No campaigns yet. Pick a product from your catalog to create one.</td></tr>`
    : campaigns.slice().reverse().map(c => {
        const product = findProduct(c.product_id) || { name: c.product_id, image: '' };
        const statusPill = c.mode === 'publish'
          ? `<span class="status-pill live">● Live on @${user.username || 'creator'}</span>`
          : `<span class="status-pill draft">● Draft on TikTok</span>`;
        const scope = c.mode === 'publish' ? 'video.publish' : 'video.upload';
        return `
          <tr>
            <td>
              <div class="campaign-product">
                <img src="${product.image}" alt="" />
                <div>
                  <div style="font-weight: 600;">${product.name}</div>
                  <div class="muted" style="font-size: 12px;">${c.title || '(no caption)'}</div>
                </div>
              </div>
            </td>
            <td>${statusPill}</td>
            <td><code style="font-size: 11px;">${scope}</code></td>
            <td><code style="font-size: 11px;">${c.publish_id}</code></td>
            <td class="muted small">${new Date(c.created_at).toLocaleString()}</td>
          </tr>
        `;
      }).join('');

  res.send(page({
    title: 'Campaigns',
    user,
    active: 'campaigns',
    body: `
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: end; margin-bottom: 16px;">
          <div>
            <h2 style="margin: 0;">Campaigns</h2>
            <p class="muted" style="margin: 4px 0 0;">Every video you've posted to TikTok through Oubon Shop Automation.</p>
          </div>
          <a class="btn sm" href="/products">+ New from product catalog</a>
        </div>
        <table class="campaigns">
          <thead>
            <tr>
              <th>Product</th>
              <th>Status</th>
              <th>Scope</th>
              <th>Publish ID</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `,
  }));
});

// New campaign form. Pre-fills with the selected product if `?product=`
// is passed. Disables "Publish now" for accounts under 1k followers
// (this is where user.info.stats visibly gates the UI).
app.get('/campaigns/new', requireAuth, (req, res) => {
  const flash = req.session.flash;
  req.session.flash = null;

  const user = req.session.user || {};
  const followers = Number(user.follower_count ?? 0);
  const canDirectPublish = followers >= 1000;

  const product = req.query.product ? findProduct(req.query.product) : null;
  const defaultTitle = product ? `${product.name} — ${product.tagline}` : '';

  res.send(page({
    title: 'New Campaign',
    user,
    active: 'campaigns',
    body: `
      ${flash ? `<div class="flash ${flash.ok ? 'ok' : 'err'}">${flash.message}</div>` : ''}

      <a href="${product ? `/products/${product.id}` : '/products'}" class="muted small" style="text-decoration: none;">← Back</a>

      <div class="card" style="margin-top: 12px;">
        <h2 style="margin-bottom: 4px;">New Campaign${product ? ` · ${product.name}` : ''}</h2>
        <p class="muted">Upload a short promotional video. You can save it as a draft to review inside TikTok, or publish it directly to your profile.</p>

        ${product ? `
          <div class="integration-row" style="margin-top: 16px;">
            <img src="${product.image}" alt="" style="width: 56px; height: 56px; border-radius: 8px; object-fit: cover;" />
            <div style="flex: 1;">
              <div style="font-weight: 600;">${product.name}</div>
              <div class="muted small">$${product.price.toFixed(2)} · ${product.tagline}</div>
            </div>
          </div>
        ` : ''}

        <form method="post" action="/campaigns/new" enctype="multipart/form-data" style="margin-top: 24px;">
          <input type="hidden" name="product_id" value="${product ? product.id : ''}" />

          <div class="form-row">
            <label>Video file <span class="muted">(.mp4 or .mov, up to 50 MB)</span></label>
            <input type="file" name="video" accept="video/mp4,video/quicktime" required />
          </div>

          <div class="form-row">
            <label>Caption</label>
            <textarea name="title" placeholder="A short caption that will accompany your TikTok post.">${defaultTitle}</textarea>
          </div>

          <div class="form-row">
            <label>Privacy (applies to direct publishing only)</label>
            <select name="privacy_level">
              <option value="SELF_ONLY">Only me</option>
              <option value="MUTUAL_FOLLOW_FRIENDS">Mutual follow friends</option>
              <option value="PUBLIC_TO_EVERYONE">Public</option>
            </select>
          </div>

          <div class="button-row">
            <button class="btn secondary" type="submit" name="action" value="upload">
              Save to TikTok drafts
            </button>
            <button class="btn ${canDirectPublish ? '' : 'disabled'}" type="submit" name="action" value="publish" ${canDirectPublish ? '' : 'disabled'}>
              ${canDirectPublish ? 'Publish to TikTok now' : 'Publish to TikTok now (locked)'}
            </button>
          </div>

          <p class="muted small" style="margin-top: 16px;">
            ${canDirectPublish
              ? `Direct publishing is enabled for your account (${followers.toLocaleString()} followers).`
              : `Direct publishing is locked because @${user.username || 'your account'} has ${followers.toLocaleString()} followers. Accounts under 1,000 followers save drafts for review first. Reach 1k followers to unlock direct publish.`}
          </p>
        </form>
      </div>
    `,
  }));
});

// Handle the campaign POST — exercises video.upload or video.publish
// and appends a row to the session's campaigns array, which is what
// the /campaigns page renders.
app.post('/campaigns/new', requireAuth, upload.single('video'), async (req, res) => {
  const { access_token } = req.session.tokens;
  const { action, title = '', privacy_level = 'SELF_ONLY', product_id } = req.body;
  const file = req.file;

  if (!file) {
    req.session.flash = { ok: false, message: 'No video file was attached.' };
    return res.redirect(`/campaigns/new${product_id ? `?product=${product_id}` : ''}`);
  }

  const user = req.session.user || {};
  const followers = Number(user.follower_count ?? 0);
  if (action === 'publish' && followers < 1000) {
    try { fs.unlinkSync(file.path); } catch {}
    req.session.flash = { ok: false, message: 'Direct publishing is locked for accounts under 1,000 followers. Save as draft instead.' };
    return res.redirect(`/campaigns/new${product_id ? `?product=${product_id}` : ''}`);
  }

  const videoSize = fs.statSync(file.path).size;

  try {
    const isDirectPublish = action === 'publish';
    const initUrl = isDirectPublish
      ? `${API_BASE}/v2/post/publish/video/init/`
      : `${API_BASE}/v2/post/publish/inbox/video/init/`;

    const initPayload = isDirectPublish
      ? {
          post_info: {
            title: title || 'New product video',
            privacy_level,
            disable_duet: false,
            disable_comment: false,
            disable_stitch: false,
            video_cover_timestamp_ms: 1000,
          },
          source_info: {
            source: 'FILE_UPLOAD',
            video_size: videoSize,
            chunk_size: videoSize,
            total_chunk_count: 1,
          },
        }
      : {
          source_info: {
            source: 'FILE_UPLOAD',
            video_size: videoSize,
            chunk_size: videoSize,
            total_chunk_count: 1,
          },
        };

    const initResp = await axios.post(initUrl, initPayload, {
      headers: { Authorization: `Bearer ${access_token}`, 'Content-Type': 'application/json' },
    });

    const { publish_id, upload_url } = initResp.data?.data || {};
    if (!publish_id || !upload_url) {
      throw new Error('Init returned no publish_id or upload_url: ' + JSON.stringify(initResp.data));
    }

    const videoBuffer = fs.readFileSync(file.path);
    await axios.put(upload_url, videoBuffer, {
      headers: {
        'Content-Type': 'video/mp4',
        'Content-Length': videoSize.toString(),
        'Content-Range': `bytes 0-${videoSize - 1}/${videoSize}`,
      },
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
    });

    try { fs.unlinkSync(file.path); } catch {}

    // Append to campaign log
    req.session.campaigns = req.session.campaigns || [];
    req.session.campaigns.push({
      product_id: product_id || null,
      title,
      mode: isDirectPublish ? 'publish' : 'upload',
      publish_id,
      privacy_level: isDirectPublish ? privacy_level : null,
      created_at: Date.now(),
    });

    req.session.flash = {
      ok: true,
      message: isDirectPublish
        ? `Campaign published to @${user.username || 'your account'}. Publish ID: ${publish_id}. See your Campaigns log.`
        : `Campaign saved as a draft on TikTok. Publish ID: ${publish_id}. Open TikTok to finalize the post.`,
    };
    res.redirect('/campaigns');
  } catch (e) {
    try { fs.unlinkSync(file.path); } catch {}
    console.error(`[${action}] failed:`, e.response?.data || e.message);
    req.session.flash = {
      ok: false,
      message: `Campaign ${action === 'publish' ? 'publish' : 'draft'} failed: ${JSON.stringify(e.response?.data || e.message)}`,
    };
    res.redirect(`/campaigns/new${product_id ? `?product=${product_id}` : ''}`);
  }
});

// Settings → Integrations — secondary surface. Still shows the
// connected TikTok account in detail so users can verify the
// connection and see Reach metrics.
app.get('/settings/integrations', requireAuth, async (req, res) => {
  const { access_token } = req.session.tokens;

  // Refresh on demand
  try {
    const fields = [
      'open_id', 'union_id', 'avatar_url', 'display_name',
      'bio_description', 'profile_deep_link', 'is_verified', 'username',
      'follower_count', 'following_count', 'likes_count', 'video_count',
    ].join(',');
    const resp = await axios.get(`${API_BASE}/v2/user/info/?fields=${fields}`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const data = resp.data?.data?.user || {};
    req.session.user = data;
    req.session.user_raw = resp.data;

    const profileLink = data.profile_deep_link
      ? `<a href="${data.profile_deep_link}" target="_blank" rel="noopener" style="color: var(--accent); word-break: break-all;">${data.profile_deep_link}</a>`
      : '<span class="muted">Not set</span>';

    res.send(page({
      title: 'Settings · Integrations',
      user: data,
      active: 'settings',
      body: `
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h2 style="margin: 0;">Integrations</h2>
            <span class="status-pill connected">● Connected</span>
          </div>
          <p class="muted">Manage the third-party accounts linked to your Oubon Shop merchant profile.</p>

          <h3>TikTok</h3>
          <div class="integration-row">
            <img class="avatar" src="${data.avatar_url || ''}" alt="" />
            <div style="flex: 1;">
              <div style="font-size: 17px; font-weight: 600;">
                ${data.display_name || 'Connected account'}
                ${data.is_verified ? '<span class="verified">VERIFIED</span>' : ''}
              </div>
              <div class="muted">@${data.username || '(no username)'}</div>
              <div class="muted" style="font-size: 12px; margin-top: 4px;">open_id: ${data.open_id || ''}</div>
            </div>
            <a class="btn secondary sm" href="/logout">Disconnect</a>
          </div>

          <div style="margin-top: 16px; padding: 14px 16px; background: var(--card-elev); border-radius: 8px; border: 1px solid var(--border);">
            <div class="muted" style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Profile URL</div>
            <div style="margin-top: 4px;">${profileLink}</div>
            <div class="muted" style="font-size: 12px; margin-top: 8px;">
              Surfaced on your Products page as a "View seller on TikTok" link on every product card.
            </div>
          </div>

          <h3>Reach</h3>
          <div class="grid-stats">
            <div class="stat"><div class="label">Followers</div><div class="value">${(data.follower_count ?? 0).toLocaleString()}</div></div>
            <div class="stat"><div class="label">Following</div><div class="value">${(data.following_count ?? 0).toLocaleString()}</div></div>
            <div class="stat"><div class="label">Likes</div><div class="value">${(data.likes_count ?? 0).toLocaleString()}</div></div>
            <div class="stat"><div class="label">Videos</div><div class="value">${(data.video_count ?? 0).toLocaleString()}</div></div>
          </div>
          <p class="muted small" style="margin-top: 8px;">
            ${data.follower_count >= 1000
              ? 'Direct publish is unlocked for your account.'
              : 'Accounts under 1,000 followers save drafts before publishing. Direct publish unlocks at 1k.'}
          </p>
        </div>

        <details class="card">
          <summary class="muted">Raw API response (debug)</summary>
          <pre class="raw">${JSON.stringify(resp.data, null, 2)}</pre>
        </details>
      `,
    }));
  } catch (e) {
    console.error('[user.info] fetch failed:', e.response?.data || e.message);
    res.status(500).send(page({
      title: 'Couldn\'t load integrations',
      user: req.session.user,
      active: 'settings',
      body: `<div class="card"><h2>Couldn't load your TikTok account</h2>
        <pre class="raw">${JSON.stringify(e.response?.data || e.message, null, 2)}</pre>
        <a class="btn secondary" href="/products">Back to products</a></div>`,
    }));
  }
});

// --- Compliance pages -----------------------------------------------

app.get('/permissions', (req, res) => {
  res.send(page({
    title: 'Permissions',
    user: req.session.user,
    body: `
      <div class="card">
        <h2>Permissions Oubon Shop Automation Requests</h2>
        <p class="muted">When you sign in with TikTok, the following five scopes are requested.
          Each is used for a specific feature within the product, as described below.</p>

        <h3>Login Kit</h3>

        <div style="margin-bottom: 20px;">
          <strong><code>user.info.basic</code></strong>
          <p style="margin: 6px 0 0 0; color: var(--text);">
            Powers the connected-account pill in the top-right of every page (avatar +
            display name + reach). <code>open_id</code> is stored as the link between
            your Oubon Shop merchant profile and your TikTok account so subsequent
            campaign posts go to the right account.
          </p>
        </div>

        <div style="margin-bottom: 20px;">
          <strong><code>user.info.profile</code></strong>
          <p style="margin: 6px 0 0 0; color: var(--text);">
            Your TikTok profile URL is rendered on every product card in your Products
            page as a "View seller on TikTok" link so buyers can verify your TikTok
            presence. The <code>is_verified</code> badge is shown on the
            Settings → Integrations page.
          </p>
        </div>

        <div style="margin-bottom: 20px;">
          <strong><code>user.info.stats</code></strong>
          <p style="margin: 6px 0 0 0; color: var(--text);">
            Follower count is displayed in the connected-account pill on every page
            and on the Settings → Integrations page. It also gates the
            "Publish to TikTok now" button on the New Campaign page — accounts under
            1,000 followers default to draft mode (the button is disabled until reach
            crosses the threshold).
          </p>
        </div>

        <h3>Content Posting API</h3>

        <div style="margin-bottom: 20px;">
          <strong><code>video.upload</code></strong>
          <p style="margin: 6px 0 0 0; color: var(--text);">
            Powers the "Save to TikTok drafts" button on the New Campaign page. The video
            is uploaded to your TikTok inbox as a draft. The new campaign appears in
            your Campaigns log with status "Draft on TikTok" and the returned publish ID.
          </p>
        </div>

        <div style="margin-bottom: 20px;">
          <strong><code>video.publish</code></strong>
          <p style="margin: 6px 0 0 0; color: var(--text);">
            Powers the "Publish to TikTok now" button on the New Campaign page. The video
            is posted directly to your TikTok profile with the chosen caption and privacy
            setting. The new campaign appears in your Campaigns log with status
            "Live on @username" and the returned publish ID.
          </p>
        </div>

        <p class="muted" style="margin-top: 24px;">
          You can revoke this app's access at any time at
          <a href="https://www.tiktok.com/setting/connected-apps" target="_blank" rel="noopener" style="color: var(--accent);">tiktok.com/setting/connected-apps</a>.
        </p>
      </div>
    `,
  }));
});

app.get('/terms', (req, res) => {
  res.send(page({
    title: 'Terms of Service',
    user: req.session.user,
    body: `
      <div class="card">
        <h2>Terms of Service</h2>
        <p class="muted">Last updated: 2026-05-17</p>

        <h3>1. Acceptance</h3>
        <p>By using Oubon Shop Automation ("the Service"), you agree to these Terms.
        If you do not agree, do not use the Service.</p>

        <h3>2. The Service</h3>
        <p>The Service is a Shopify merchant tool that, with your explicit OAuth
        authorization, posts promotional videos to your connected TikTok account and
        reads identity, profile, and reach information from that account to surface
        your TikTok presence inside the Service.</p>

        <h3>3. TikTok integration</h3>
        <p>The Service requests the following TikTok scopes: <code>user.info.basic</code>,
        <code>user.info.profile</code>, <code>user.info.stats</code>,
        <code>video.upload</code>, <code>video.publish</code>. See the
        <a href="/permissions" style="color: var(--accent);">Permissions</a> page for
        what each scope does. You may revoke this authorization at any time from your
        TikTok account settings.</p>

        <h3>4. Acceptable use</h3>
        <p>You agree to post only content you own or have the right to distribute, and to
        comply with TikTok's
        <a href="https://www.tiktok.com/legal/community-guidelines" target="_blank" rel="noopener" style="color: var(--accent);">Community Guidelines</a>
        and
        <a href="https://www.tiktok.com/legal/terms-of-service" target="_blank" rel="noopener" style="color: var(--accent);">Terms of Service</a>.</p>

        <h3>5. No warranty</h3>
        <p>The Service is provided as-is, without warranty of any kind. We are not
        responsible for content posted through the Service or for any TikTok account
        action resulting from its use.</p>

        <h3>6. Termination</h3>
        <p>You may stop using the Service at any time. We may suspend access for abuse,
        security concerns, or violation of these Terms.</p>

        <h3>7. Contact</h3>
        <p>Questions: <a href="mailto:sponce96@icloud.com" style="color: var(--accent);">sponce96@icloud.com</a></p>
      </div>
    `,
  }));
});

app.get('/privacy', (req, res) => {
  res.send(page({
    title: 'Privacy Policy',
    user: req.session.user,
    body: `
      <div class="card">
        <h2>Privacy Policy</h2>
        <p class="muted">Last updated: 2026-05-17</p>

        <h3>1. Data we collect</h3>
        <p>When you connect your TikTok account, we receive — only with your explicit
        OAuth consent — the following from TikTok's <code>/v2/user/info/</code> endpoint:</p>
        <ul>
          <li><strong>Identity</strong> (<code>user.info.basic</code>): open_id, union_id, avatar URL, display name</li>
          <li><strong>Profile</strong> (<code>user.info.profile</code>): username, bio, profile URL, verified status</li>
          <li><strong>Reach</strong> (<code>user.info.stats</code>): follower / following / likes / video counts</li>
        </ul>
        <p>When you create a campaign, the video file you upload is sent to TikTok via
        the Content Posting API (<code>video.upload</code> or <code>video.publish</code>
        scope, depending on the button you click). We do not retain the video file after
        the upload completes.</p>

        <h3>2. How we use it</h3>
        <p>Identity, profile, and reach data are displayed to you in the connected-account
        pill, on the Products page, and on the Settings → Integrations page. We do not
        sell, share, or use this data for advertising.</p>

        <h3>3. Storage</h3>
        <p>OAuth access tokens are stored in your browser session only for the duration
        of your sign-in. Profile data fetched from TikTok is cached in memory for the
        same session. No third party receives your TikTok data from us.</p>

        <h3>4. Sharing</h3>
        <p>We share data only with TikTok itself (to authenticate and to post videos
        on your behalf). We do not share your TikTok data with any other third party.</p>

        <h3>5. Your rights</h3>
        <p>You may revoke this app's access at any time at
        <a href="https://www.tiktok.com/setting/connected-apps" target="_blank" rel="noopener" style="color: var(--accent);">tiktok.com/setting/connected-apps</a>.
        Revocation immediately stops the Service from making any further calls on your
        behalf. To request deletion of any session-cached data, email
        <a href="mailto:sponce96@icloud.com" style="color: var(--accent);">sponce96@icloud.com</a>.</p>

        <h3>6. Children</h3>
        <p>The Service is not intended for users under 13. Do not connect a TikTok
        account belonging to a minor.</p>

        <h3>7. Contact</h3>
        <p>Privacy questions: <a href="mailto:sponce96@icloud.com" style="color: var(--accent);">sponce96@icloud.com</a></p>
      </div>
    `,
  }));
});

app.get('/health', (req, res) => res.json({ ok: true, app: 'oubon-shop-automation' }));

// --- Start -----------------------------------------------------------
app.listen(PORT, () => {
  console.log(`\nOubon Shop Automation`);
  console.log(`---------------------`);
  console.log(`Server:        http://localhost:${PORT}`);
  console.log(`Redirect URI:  ${REDIRECT_URI}`);
  console.log(`TikTok scopes: ${SCOPES}`);
  console.log(`Open the URL above to sign in.\n`);
});
